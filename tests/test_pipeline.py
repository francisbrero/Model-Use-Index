"""End-to-end over a synthetic corpus: backfill -> normalize -> classify.

Covers the properties that only appear once the layers are composed — dedup
feeding pricing, arcs and remainder conserving value, and cost living on
exactly one grain. Fixtures are hand-written and obviously synthetic
(invariant 6).
"""

import json

import pytest

from mui.collect.transcript import backfill
from mui.db import connect, migrate
from mui.enrich.pipeline import enrich
from mui.normalize.pipeline import rebuild
from mui.normalize.pricing import Registry, UnknownModelError

SESSION = "SYNTH-e2e"
CWD = "/synthetic/Documents/Acme/Widget"


def assistant(
    msg_id,
    *,
    blocks=1,
    skill=None,
    ts="2026-01-01T00:00:00.000Z",
    model="claude-opus-5",
    output=100,
    req="req",
):
    """One API response, written as `blocks` content-block records.

    Each block repeats the SAME usage object — which is exactly why naive
    summing overstates by ~91% (invariant 10).
    """
    out = []
    for i in range(blocks):
        out.append(
            {
                "type": "assistant",
                "sessionId": SESSION,
                "uuid": f"{msg_id}-block-{i}",
                "requestId": f"{req}-{msg_id}",
                "timestamp": ts,
                "cwd": CWD,
                "version": "2.1.245",
                **({"attributionSkill": skill} if skill else {}),
                "message": {
                    "id": msg_id,
                    "model": model,
                    "usage": {
                        "input_tokens": 1000,
                        # A partial streaming snapshot lands first, the final count
                        # later — so first-seen UNDERCOUNTS output.
                        "output_tokens": output if i == blocks - 1 else 1,
                        "cache_creation_input_tokens": 2000,
                        "cache_read_input_tokens": 5000,
                    },
                },
            }
        )
    return out


def prompt(text, ts):
    return {
        "type": "user",
        "sessionId": SESSION,
        "uuid": f"p-{ts}",
        "timestamp": ts,
        "cwd": CWD,
        "message": {"content": text},
    }


@pytest.fixture
def corpus(tmp_path):
    records = [
        prompt("start", "2026-01-01T00:00:00.000Z"),
        *assistant("m1", blocks=3, ts="2026-01-01T00:00:01.000Z"),
        prompt("run the release", "2026-01-01T00:01:00.000Z"),
        *assistant("m2", skill="release-prod", ts="2026-01-01T00:01:01.000Z"),
        *assistant("m3", skill="release-prod", ts="2026-01-01T00:01:02.000Z"),
        *assistant("m4", ts="2026-01-01T00:01:03.000Z"),
        *assistant("m5", skill="fix-issue", ts="2026-01-01T00:02:00.000Z"),
        *assistant("m6", ts="2026-01-01T00:02:01.000Z"),
    ]
    path = tmp_path / "projects" / "-synthetic-Acme-Widget"
    path.mkdir(parents=True)
    (path / f"{SESSION}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n"
    )
    return tmp_path / "projects"


@pytest.fixture
def store(tmp_path, corpus):
    conn = connect(tmp_path / "store.db")
    migrate(conn)
    backfill(conn, corpus)
    rebuild(conn, Registry.load(conn))
    return conn


def test_dedup_collapses_content_blocks(store):
    """8 assistant records collapse to 6 API responses.

    `m1` is written as three content-block records repeating one usage object —
    the shape that makes naive summing overstate by ~91%.
    """
    raw = sum(
        json.loads(p)["type"] == "assistant"
        for (p,) in store.execute("SELECT payload FROM raw_event")
    )
    calls = store.execute("SELECT COUNT(*) FROM api_call").fetchone()[0]
    assert raw == 8
    assert calls == 6


def test_dedup_takes_max_output_not_first_seen(store):
    """First-seen would record the 1-token streaming snapshot instead of 100."""
    output = store.execute(
        "SELECT output_tokens FROM api_call WHERE message_id = 'm1'"
    ).fetchone()[0]
    assert output == 100


def test_all_four_token_fields_are_priced(store):
    """Cache traffic is ~93% of Opus notional value. Pricing only input and
    output would miss almost all of it; pricing cache_read at the input rate
    would be a 10x error on the largest line item."""
    row = store.execute(
        "SELECT input_tokens, output_tokens, cache_creation_tokens, "
        "cache_read_tokens, notional_list_value_usd FROM api_call "
        "WHERE message_id = 'm1'"
    ).fetchone()
    expected = (1000 * 15.0 + 100 * 75.0 + 2000 * 18.75 + 5000 * 1.5) / 1e6
    assert row["notional_list_value_usd"] == pytest.approx(expected)


def test_arcs_and_remainder_conserve_value_exactly(store):
    """Every call is claimed exactly once. This is the assertion invariant 10
    is really about, and the one that catches a regression into the rejected
    anchor-to-session-end rule."""
    units = store.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM work_unit"
    ).fetchone()[0]
    calls = store.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM api_call"
    ).fetchone()[0]
    assert units == pytest.approx(calls)


def test_no_api_call_belongs_to_two_arcs(store):
    overlaps = store.execute(
        "SELECT COUNT(*) FROM (SELECT turn_index FROM api_call "
        "GROUP BY session_id, turn_index HAVING COUNT(DISTINCT work_unit_id) > 1)"
    ).fetchone()[0]
    assert overlaps == 0


def test_the_arc_runs_to_the_next_anchor_not_to_session_end(store):
    """`u10-next-anchor-v1`. Under W1's rejected baseline the release arc would
    swallow the fix-issue work too, double-counting it."""
    row = store.execute(
        "SELECT start_turn, end_turn FROM work_unit WHERE anchor_skill = 'release-prod'"
    ).fetchone()
    # m2, m3 (tagged) + m4 (untagged, before the next anchor) — but NOT m5/m6.
    assert row["end_turn"] - row["start_turn"] == 2


def test_the_unattributable_remainder_is_a_labelled_row(store):
    """7.4% of Opus notional value at full scale. Never silently dropped."""
    row = store.execute(
        "SELECT kind, notional_list_value_usd FROM work_unit "
        "WHERE kind = 'unattributable'"
    ).fetchone()
    assert row is not None
    assert row["notional_list_value_usd"] > 0


def test_prompt_units_carry_no_dollar_column(store):
    """`work_unit` is the SOLE cost-bearing grain. Two tables that each sum to
    the corpus is a 2x double-count waiting for an ad-hoc Datasette join."""
    columns = {r[1] for r in store.execute("PRAGMA table_info(prompt_unit)").fetchall()}
    assert not any("usd" in c or "value" in c for c in columns)


def test_prompt_units_exist_and_are_far_fewer_than_user_records(store):
    count = store.execute("SELECT COUNT(*) FROM prompt_unit").fetchone()[0]
    assert count == 2


def test_project_family_groups_worktrees(store):
    family = store.execute("SELECT DISTINCT project_family FROM work_unit").fetchone()[
        0
    ]
    assert family == "Widget"


def test_classification_and_verdicts_are_written(store):
    enrich(store, activity_map={"release-prod": "automation"})
    row = store.execute(
        "SELECT c.ai_activity, c.work_type, v.justification "
        "FROM classification c JOIN verdict v ON v.work_unit_id = c.unit_id "
        "WHERE c.unit_grain = 'work_unit' AND c.ai_activity = 'automation'"
    ).fetchone()
    assert row["ai_activity"] == "automation"
    assert row["work_type"] == "Agentic"


def test_every_classification_is_marked_provisional(store):
    enrich(store, activity_map={})
    versions = {
        r[0]
        for r in store.execute("SELECT DISTINCT classifier_version FROM classification")
    }
    assert versions and all("provisional" in v for v in versions)


def test_no_underprovisioned_verdict_is_reachable(store):
    """Absent BY CONSTRUCTION, not because it is rare — the slice builds no
    outcome_signal table. Since it overrides every other verdict, its absence
    biases every number toward over-provisioned, which `v_caveats` states."""
    enrich(store, activity_map={})
    verdicts = {
        r[0] for r in store.execute("SELECT DISTINCT justification FROM verdict")
    }
    assert "Underprovisioned" not in verdicts


def test_caveats_are_rows_not_prose(store):
    """They must survive a `SELECT *`, because Datasette is the UI and there is
    no page to write prose on."""
    caveats = {r[0] for r in store.execute("SELECT caveat FROM v_caveats")}
    assert {
        "no_headroom",
        "no_underprovisioned",
        "provisional_classification",
    } <= caveats


def test_an_unregistered_model_fails_loudly(store):
    """A silent tier default would corrupt every tier_delta, and the corruption
    would look like a finding rather than a bug."""
    registry = Registry.load(store)
    with pytest.raises(UnknownModelError):
        registry.resolve("some-model-we-have-never-seen")


def test_synthetic_records_resolve_but_are_not_billable(store):
    """Kept so rate-limit records need no filter (invariant 10b), excluded from
    tier arithmetic so the ordinal scale stays total."""
    registry = Registry.load(store)
    rate = registry.resolve("<synthetic>")
    assert rate.usd_in == 0.0
    billable = store.execute(
        "SELECT is_billable FROM model_registry WHERE model_pattern = '<synthetic>'"
    ).fetchone()[0]
    assert billable == 0


def test_rebuild_is_idempotent(store):
    """Derived tables are rebuilt wholesale from raw_event — that is the
    recovery story (invariant 2b)."""
    before = store.execute("SELECT COUNT(*) FROM work_unit").fetchone()[0]
    rebuild(store, Registry.load(store))
    after = store.execute("SELECT COUNT(*) FROM work_unit").fetchone()[0]
    assert before == after


def test_a_model_matching_two_patterns_is_resolved_once(store):
    """`claude-haiku-4-5-20251001` matches BOTH `claude-haiku-4-5*` and
    `claude-haiku-4*`.

    A SQL glob join against `model_registry` therefore returns two rows for
    every such call, doubling its weight in the arc's tier vote — measured at
    5,214 joined rows against 2,607 real calls. Resolution is
    longest-pattern-first and lives in exactly one place, `Registry.resolve`.
    """
    registry = Registry.load(store)
    rate = registry.resolve("claude-haiku-4-5-20251001")
    assert rate.pattern == "claude-haiku-4-5*", "most specific pattern wins"
    assert rate.tier == "small"


def test_registry_prefers_the_longest_matching_pattern(store):
    registry = Registry.load(store)
    assert registry.resolve("claude-haiku-4-5-20251001").pattern == "claude-haiku-4-5*"
    assert registry.resolve("claude-haiku-4-0").pattern == "claude-haiku-4*"


def test_version_pinned_ids_resolve_like_their_unpinned_form(store):
    """PRD §6.3 — `claude-opus-5@20250514` and `claude-opus-5` are one tier."""
    registry = Registry.load(store)
    assert registry.resolve("claude-opus-5").tier == "frontier"
    assert registry.resolve("claude-opus-5-20260101").tier == "frontier"
