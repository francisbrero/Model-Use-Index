"""U10 — the anchor-to-arc bounding rule, locked against the golden fixture.

The rule (`u10-next-anchor-v1`): a routine's arc runs from its `attributionSkill`
anchor to the next anchor of *any* skill, else to session end. See milestones
§2 U10 for the candidate scoring and why the two intuitive refinements
(idle-gap, `cwd`/`gitBranch` change) lose on evidence.

The rejected candidates are implemented here too, deliberately. The register's
load-bearing claim is comparative — the W1 baseline double-counts $13,118 of
Opus notional list value while this rule double-counts nothing — and a claim
that only one rule is in the module is a claim no test can check.

There is no `src/mui` yet (nothing is built — MS §1), so this is the reference
implementation the normaliser must reproduce. When `normalize/work_unit.py`
lands, import from it here and delete the local copies.

Every dollar figure in this module and its fixture is NOTIONAL LIST VALUE
(invariant 5).
"""

import json
import pathlib
from collections import Counter

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "anchor_shapes"

SESSION_IDS = [
    "SYNTH-single",
    "SYNTH-two-distinct",
    "SYNTH-two-same",
    "SYNTH-pre-anchor",
    "SYNTH-idle-gap",
    "SYNTH-tag-hole",
    "SYNTH-long-run-then-anchor",
    "SYNTH-out-of-order",
]


# --------------------------------------------------------------------------
# Dedup — invariant 10. One turn per unique API response.
# --------------------------------------------------------------------------


def dedup(records):
    """Collapse content-block records to unique API responses, keyed by
    (message.id, requestId), taking max per usage field.

    Claude Code writes one assistant record per content block, each repeating
    the same `usage` object, and within a group `output_tokens` may differ — a
    partial streaming snapshot is written before the final count. So max per
    field, never first-seen (undercounts output) and never last-by-file-order.

    Fields that are *not* usage counts are reconciled across the group rather
    than taken from whichever block happened to land first: `attributionSkill`
    and `isSidechain` may be present on some blocks of a response and absent
    from others, and first-seen would make the result depend on file order.
    """
    groups, order = {}, []
    for position, record in enumerate(records):
        message = record["message"]
        usage = message["usage"]
        key = (message["id"], record.get("requestId"))
        fields = {
            "input": usage.get("input_tokens") or 0,
            "output": usage.get("output_tokens") or 0,
            "cache_write": usage.get("cache_creation_input_tokens") or 0,
            "cache_read": usage.get("cache_read_input_tokens") or 0,
        }
        if key not in groups:
            groups[key] = {
                "session": record["sessionId"],
                "skill": record.get("attributionSkill") or None,
                "sidechain": bool(record.get("isSidechain")),
                "timestamp": record.get("timestamp"),
                "position": position,
                "usage": fields,
            }
            order.append(key)
            continue
        group = groups[key]
        for field, value in fields.items():
            if value > group["usage"][field]:
                group["usage"][field] = value
        # any-of, not first-seen: a group is a sidechain turn if any block says so
        group["sidechain"] = group["sidechain"] or bool(record.get("isSidechain"))
        if group["skill"] is None and record.get("attributionSkill"):
            group["skill"] = record["attributionSkill"]
    return [groups[key] for key in order]


def to_sessions(records):
    """Group deduplicated turns by session, ordered by (timestamp, file
    position). Order is part of the rule, not an accident of file layout: the
    arc boundary is 'the next anchor', which is only meaningful in time."""
    by_session = {}
    for turn in dedup(records):
        by_session.setdefault(turn["session"], []).append(turn)
    for turns in by_session.values():
        turns.sort(key=lambda t: (t["timestamp"] or "", t["position"]))
    return by_session


# --------------------------------------------------------------------------
# Pricing — invariant 10 §2. Four fields, priced separately.
# --------------------------------------------------------------------------


def notional_list_value(usage, rates):
    """USD notional list value for one turn. Cache traffic is the majority of
    real spend, so all four fields are priced; `cache_read` at the input rate
    would be a 10x error on the largest line item."""
    return (
        usage["input"] * rates["input"]
        + usage["output"] * rates["output"]
        + usage["cache_write"] * rates["cache_write"]
        + usage["cache_read"] * rates["cache_read"]
    ) / 1e6


def arc_value(turns, arc, rates):
    span = turns[arc["start"] : arc["end"] + 1]
    return sum(notional_list_value(t["usage"], rates) for t in span)


# --------------------------------------------------------------------------
# Arc bounding — the U10 rule and the candidates it beat.
# --------------------------------------------------------------------------


def anchor_runs(turns):
    """Contiguous runs of the same attributionSkill -> (start, tag_end, skill).

    A tag run with a hole (`a, None, a`) splits into two runs, so it is
    indistinguishable from a genuine re-invocation. Accepted: the register
    treats re-invocation as a boundary anyway, so both readings agree.
    """
    runs, i, n = [], 0, len(turns)
    while i < n:
        skill = turns[i]["skill"]
        # `not skill` rather than `is None`: an empty tag is not an anchor.
        # Defensive only — over 81,982 assistant records the field is either
        # absent or a real value; "" and null never occur (checked 2026-09-09).
        # Deliberately untested: a fixture for it would assert a shape the
        # transcript writer does not produce (invariant 7 — parse defensively,
        # but don't pretend to have evidence you lack).
        if not skill:
            i += 1
            continue
        j = i
        while j + 1 < n and turns[j + 1]["skill"] == skill:
            j += 1
        runs.append((i, j, skill))
        i = j + 1
    return runs


def arcs(turns):
    """`u10-next-anchor-v1`. Anchor -> next anchor of any skill, else session
    end. Returns [{skill, start, end}] with `end` inclusive."""
    runs = anchor_runs(turns)
    out = []
    for k, (start, _tag_end, skill) in enumerate(runs):
        end = runs[k + 1][0] - 1 if k + 1 < len(runs) else len(turns) - 1
        out.append({"skill": skill, "start": start, "end": end})
    return out


def arcs_w1_baseline(turns):
    """W1's rejected baseline: every anchor runs to session end. Kept so the
    register's $13,118 double-count claim is executable rather than asserted."""
    return [
        {"skill": skill, "start": start, "end": len(turns) - 1}
        for start, _tag_end, skill in anchor_runs(turns)
    ]


def arcs_tagged_only(turns):
    """The naive rule: only the tagged turns. Undercounts by an order of
    magnitude (invariant 11) — 9.0% of Opus value attributed against 92.6%."""
    return [
        {"skill": skill, "start": start, "end": tag_end}
        for start, tag_end, skill in anchor_runs(turns)
    ]


def unattributable(turns):
    """Turn indices in no arc: work before a session's first anchor, or every
    turn when the session has no anchor at all."""
    runs = anchor_runs(turns)
    return list(range(runs[0][0])) if runs else list(range(len(turns)))


def claimed_counts(turns, rule):
    """How many arcs claim each turn index. 1 everywhere is correct; >1 is a
    double-count; 0 means the turn is in the remainder."""
    counts = Counter()
    for arc in rule(turns):
        counts.update(range(arc["start"], arc["end"] + 1))
    return counts


# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def expected():
    return json.loads((FIXTURES / "expected.json").read_text())


@pytest.fixture(scope="module")
def rates(expected):
    return expected["rates_notional_list_value_usd_per_1m"]["opus"]


@pytest.fixture(scope="module")
def sessions():
    records = [
        json.loads(line)
        for line in (FIXTURES / "anchor_shapes.jsonl").read_text().splitlines()
        if line.strip()
    ]
    return to_sessions(records)


def test_every_fixture_session_is_expected(sessions, expected):
    assert set(sessions) == set(expected["sessions"]) == set(SESSION_IDS)


@pytest.mark.parametrize("session_id", SESSION_IDS)
def test_arc_boundaries_match_golden(sessions, expected, session_id):
    turns = sessions[session_id]
    want = expected["sessions"][session_id]
    got = arcs(turns)
    assert [{k: a[k] for k in ("skill", "start", "end")} for a in got] == [
        {k: a[k] for k in ("skill", "start", "end")} for a in want["arcs"]
    ]
    assert unattributable(turns) == want["pre_anchor"]


@pytest.mark.parametrize("session_id", SESSION_IDS)
def test_arc_notional_list_value_matches_golden(sessions, expected, rates, session_id):
    """Makes the $1,447 +/- 5% regression target's arithmetic executable at
    fixture scale: four-field pricing over the rule's own arc boundaries."""
    turns = sessions[session_id]
    want = expected["sessions"][session_id]
    for got, wanted in zip(arcs(turns), want["arcs"], strict=True):
        assert arc_value(turns, got, rates) == pytest.approx(
            wanted["notional_list_value_usd"]
        )


@pytest.mark.parametrize("session_id", SESSION_IDS)
def test_remainder_notional_list_value_matches_golden(
    sessions, expected, rates, session_id
):
    """The unattributable remainder is 7.4% of Opus value at full scale and
    must be a labelled number, never silently dropped."""
    turns = sessions[session_id]
    want = expected["sessions"][session_id]
    got = sum(
        notional_list_value(turns[i]["usage"], rates) for i in unattributable(turns)
    )
    assert got == pytest.approx(want["unattributable_notional_list_value_usd"])


@pytest.mark.parametrize("session_id", SESSION_IDS)
def test_arcs_plus_remainder_equals_session_total(
    sessions, expected, rates, session_id
):
    """Conservation: the arcs and the remainder account for the session exactly
    once. This is the assertion invariant 10 is really about."""
    turns = sessions[session_id]
    want = expected["sessions"][session_id]
    total = sum(arc_value(turns, a, rates) for a in arcs(turns)) + sum(
        notional_list_value(turns[i]["usage"], rates) for i in unattributable(turns)
    )
    assert total == pytest.approx(want["session_total_notional_list_value_usd"])
    assert total == pytest.approx(
        sum(notional_list_value(t["usage"], rates) for t in turns)
    )


@pytest.mark.parametrize("session_id", SESSION_IDS)
def test_no_turn_is_double_counted(sessions, session_id):
    turns = sessions[session_id]
    doubled = [i for i, c in claimed_counts(turns, arcs).items() if c > 1]
    assert not doubled, f"turns attributed to more than one arc: {doubled}"


@pytest.mark.parametrize("session_id", SESSION_IDS)
def test_no_turn_is_dropped(sessions, session_id):
    turns = sessions[session_id]
    counts = claimed_counts(turns, arcs)
    covered = Counter(unattributable(turns)) + counts
    assert Counter(covered) == Counter(range(len(turns))), (
        "every turn must be in exactly one arc or in the remainder"
    )


def test_w1_baseline_double_counts_where_this_rule_does_not(sessions, rates):
    """The register's load-bearing comparison, made executable.

    At full scale, `anchor -> session end` double-counts $13,118 of Opus
    notional list value because 110 of 137 anchored sessions carry more than
    one anchor. Here: on the multi-anchor sessions the baseline overcounts and
    the U10 rule conserves.
    """
    multi_anchor = ["SYNTH-two-distinct", "SYNTH-two-same"]
    for session_id in multi_anchor:
        turns = sessions[session_id]
        session_total = sum(notional_list_value(t["usage"], rates) for t in turns)

        baseline = arcs_w1_baseline(turns)
        assert max(claimed_counts(turns, arcs_w1_baseline).values()) > 1, (
            f"{session_id} must expose the baseline's overlap"
        )
        baseline_total = sum(arc_value(turns, a, rates) for a in baseline)
        assert baseline_total > session_total, (
            "the W1 baseline must overstate the session it is summed over"
        )

        assert max(claimed_counts(turns, arcs).values()) == 1
        assert sum(arc_value(turns, a, rates) for a in arcs(turns)) == pytest.approx(
            session_total
        )


def test_tagged_only_rule_undercounts(sessions, rates):
    """Invariant 11: the tag alone cannot cost a routine. On SYNTH-single the
    tag covers 2 of 5 turns, so the naive rule sees a fraction of the arc."""
    turns = sessions["SYNTH-single"]
    naive = sum(arc_value(turns, a, rates) for a in arcs_tagged_only(turns))
    ruled = sum(arc_value(turns, a, rates) for a in arcs(turns))
    assert naive < ruled


def test_arc_survives_a_six_day_idle_gap(sessions):
    """SYNTH-idle-gap holds a 6-day gap *inside* one arc — a release routine
    waiting on CI. Real /release-prod arcs contain gaps up to 8,605 minutes, so
    an idle-time boundary would cut here and lose the tail."""
    turns = sessions["SYNTH-idle-gap"]
    (arc,) = arcs(turns)
    assert arc["end"] == len(turns) - 1


def test_boundary_is_the_next_runs_start_not_its_tag_end(sessions):
    """The one assertion that pins the rule's central expression.

    `SYNTH-long-run-then-anchor` is the only session here whose *non-final*
    anchor run spans more than one turn, so it is the only one where
    `runs[k+1].start` and `runs[k+1].tag_end` differ. Everywhere else the two
    are numerically identical and a mutation between them is invisible — real
    anchor runs are median 15 turns, so this shape is the normal case rather
    than an edge case.
    """
    turns = sessions["SYNTH-long-run-then-anchor"]
    runs = anchor_runs(turns)
    assert [(start, tag_end) for start, tag_end, _ in runs] == [(0, 2), (4, 5)], (
        "the fixture must contain a multi-turn run followed by another anchor"
    )
    first, second = arcs(turns)
    # boundary = next run's START - 1 (3), not its tag_end (5)
    assert first["end"] == 3
    assert second["start"] == 4
    assert max(claimed_counts(turns, arcs).values()) == 1


def test_turns_are_ordered_by_timestamp_not_file_order(sessions):
    """`SYNTH-out-of-order` is written to the file as O2, O0, O1. Read in file
    order the anchor lands at index 1 and turn 0 falls wrongly into the
    remainder; in timestamp order the arc covers the whole session."""
    turns = sessions["SYNTH-out-of-order"]
    assert [t["timestamp"] for t in turns] == sorted(t["timestamp"] for t in turns), (
        "turns must be sorted into chronological order"
    )
    assert [t["position"] for t in turns] != sorted(t["position"] for t in turns), (
        "the fixture must actually be out of file order, or this proves nothing"
    )
    (arc,) = arcs(turns)
    assert (arc["start"], arc["end"]) == (0, len(turns) - 1)
    assert unattributable(turns) == []


def test_dedup_key_includes_request_id(sessions):
    """Invariant 10 names the key as (message.id, requestId) specifically — not
    `uuid`, not the record. A retry reuses the message.id under a new
    requestId, so dropping requestId would silently merge two real API
    responses into one and undercount."""
    base = {
        "type": "assistant",
        "sessionId": "SYNTH-retry",
        "timestamp": "2026-01-10T10:00:00Z",
        "message": {
            "id": "msg_synth_retry",
            "model": "claude-opus-4-synthetic",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 1000,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }
    records = [{**base, "requestId": rid} for rid in ("req_a", "req_b")]
    assert len(dedup(records)) == 2, (
        "same message.id, different requestId — two responses"
    )
    same = [{**base, "requestId": "req_a"}, {**base, "requestId": "req_a"}]
    assert len(dedup(same)) == 1


@pytest.mark.parametrize("field", ["attributionSkill", "isSidechain"])
@pytest.mark.parametrize("order", [("first", "second"), ("second", "first")])
def test_non_usage_fields_are_reconciled_across_a_duplicate_group(field, order):
    """A group is tagged, or is a sidechain turn, if *any* of its content blocks
    says so. First-seen would make the result depend on file order — the same
    trap as `output_tokens`, on a field that moves an arc boundary rather than
    just a label."""
    value = "synth-release" if field == "attributionSkill" else True
    base = {
        "type": "assistant",
        "sessionId": "SYNTH-recon",
        "requestId": "req_recon",
        "timestamp": "2026-01-06T10:00:00Z",
        "message": {
            "id": "msg_synth_recon",
            "model": "claude-opus-4-synthetic",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 10,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }
    carrying = {**base, field: value}
    bare = dict(base)
    records = [carrying if slot == "first" else bare for slot in order]
    (turn,) = dedup(records)
    key = "skill" if field == "attributionSkill" else "sidechain"
    assert turn[key] == value, f"{field} lost when carried by the {order} block"


def test_a_hole_in_a_tag_run_fragments_the_arc(sessions):
    """`a, None, a` within one skill splits into two arcs — the same result as a
    genuine re-invocation, so the two are indistinguishable here.

    Accepted, because the register treats re-invocation as a boundary anyway and
    both readings agree on where the boundary falls. Pinned by a test rather
    than left in a docstring because the failure is silent and expensive: if
    Claude Code ever drops the tag mid-run, arcs fragment and per-routine cost
    shatters into pieces that each look like a cheap separate invocation.
    """
    turns = sessions["SYNTH-tag-hole"]
    assert [t["skill"] for t in turns] == [
        "synth-release",
        None,
        "synth-release",
        None,
    ], "the fixture must actually contain a hole in the tag run"
    result = arcs(turns)
    assert len(result) == 2, "a hole splits the run — documented and accepted"
    assert {a["skill"] for a in result} == {"synth-release"}
    # value is still conserved across the fragments, which is what stops a hole
    # from silently losing money even though it does mis-shape the arcs
    assert max(claimed_counts(turns, arcs).values()) == 1


def test_same_skill_reinvocation_is_a_boundary(sessions):
    """Two invocations of one routine are two arcs, not one merged arc."""
    result = arcs(sessions["SYNTH-two-same"])
    assert len(result) == 2
    assert {a["skill"] for a in result} == {"synth-release"}


@pytest.mark.parametrize("session_id", SESSION_IDS)
def test_sidechain_value_is_counted_once_inside_its_arc(
    sessions, expected, rates, session_id
):
    """Invariant 10 §6 / U8: sidechain turns bill into the parent session, so a
    routine's arc already includes its subagent cost. Correct — but it must not
    also be counted alongside, so the arc total is asserted to contain it
    exactly once rather than to exclude or duplicate it."""
    turns = sessions[session_id]
    want = expected["sessions"][session_id]
    inside = sum(
        notional_list_value(t["usage"], rates)
        for i, t in enumerate(turns)
        if t["sidechain"] and any(a["start"] <= i <= a["end"] for a in arcs(turns))
    )
    assert inside == pytest.approx(want["sidechain_inside_arc_notional_list_value_usd"])
    counts = claimed_counts(turns, arcs)
    for i, turn in enumerate(turns):
        if turn["sidechain"]:
            assert counts[i] <= 1, "sidechain turn attributed to two arcs"


def test_sidechain_flag_is_reconciled_across_a_duplicate_group():
    """A group is a sidechain turn if *any* of its content blocks says so —
    first-seen would make the flag depend on file order."""
    base = {
        "type": "assistant",
        "sessionId": "SYNTH-recon",
        "requestId": "req_recon",
        "timestamp": "2026-01-06T10:00:00Z",
        "message": {
            "id": "msg_synth_recon",
            "model": "claude-opus-4-synthetic",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 10,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }
    for order in ([False, True], [True, False]):
        records = [{**base, "isSidechain": flag} for flag in order]
        (turn,) = dedup(records)
        assert turn["sidechain"] is True, f"order {order} lost the flag"


def test_dedup_takes_max_output_across_a_streaming_group(sessions):
    """Invariant 10: a partial streaming snapshot is written before the final
    count. First-seen dedup would record 500 and undercount output."""
    turns = sessions["SYNTH-idle-gap"]
    assert len(turns) == 4, "the duplicate content-block record must collapse"
    assert turns[1]["usage"]["output"] == 2000
    assert turns[1]["usage"]["cache_read"] == 20000


def test_fixture_rate_table_has_the_documented_structure(rates):
    """Fixture integrity: the relative structure is the part that must hold."""
    assert rates["cache_read"] == pytest.approx(rates["input"] * 0.1)
    assert rates["output"] == pytest.approx(rates["input"] * 5)
    assert rates["cache_write"] == pytest.approx(rates["input"] * 1.25)


def test_pricing_function_charges_cache_read_at_a_tenth_of_input(rates):
    """Pricing `cache_read` at the input rate is a 10x error on the largest
    real line item (57.9% of Opus value). Asserted against
    `notional_list_value` itself, not just against the rate table."""
    cache_heavy = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 20000}
    as_input = {"input": 20000, "output": 0, "cache_write": 0, "cache_read": 0}
    assert notional_list_value(cache_heavy, rates) == pytest.approx(
        notional_list_value(as_input, rates) * 0.1
    )
    # and each field is charged, not silently dropped
    for field in ("input", "output", "cache_write", "cache_read"):
        usage = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
        usage[field] = 1000
        assert notional_list_value(usage, rates) > 0, f"{field} is not priced"
