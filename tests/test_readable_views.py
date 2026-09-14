"""The readable views — legibility without leaking content.

`v_work_unit_summary` and `v_verdict_readable` exist because a correct number
nobody can read is a number nobody acts on. They are presentation only: every
field is derived from data already captured and already normalised, and the
summary describes the SHAPE of a work unit, never its content.

That last property is the one worth testing. A summary is exactly the kind of
field that invites "just include the first prompt" later, which would put
prompt text into the artefact that gets backed up and opened in Datasette
(invariant 6).
"""

import json
import re

import pytest

from mui.collect.transcript import backfill
from mui.db import connect, migrate
from mui.enrich.pipeline import enrich
from mui.normalize.pipeline import rebuild
from mui.normalize.pricing import Registry

SESSION = "SYNTH-readable"
CWD = "/synthetic/Documents/Acme/Widget"
SECRET = "acme-acquisition-supersecret"


def _assistant(msg_id, ts, *, skill=None, tools=(), text=""):
    content = []
    if text:
        content.append({"type": "text", "text": text})
    for name, tool_input in tools:
        content.append({"type": "tool_use", "name": name, "input": tool_input})
    return {
        "type": "assistant",
        "sessionId": SESSION,
        "uuid": f"u-{msg_id}",
        "requestId": f"r-{msg_id}",
        "timestamp": ts,
        "cwd": CWD,
        "gitBranch": f"feature/{SECRET}",
        "version": "2.1.245",
        **({"attributionSkill": skill} if skill else {}),
        "message": {
            "id": msg_id,
            "model": "claude-opus-5",
            "content": content,
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_creation_input_tokens": 2000,
                "cache_read_input_tokens": 9000,
            },
        },
    }


@pytest.fixture
def store(tmp_path):
    records = [
        {
            "type": "user",
            "sessionId": SESSION,
            "uuid": "p-0",
            "timestamp": "2026-01-01T00:00:00.000Z",
            "cwd": CWD,
            "message": {"content": f"please fix the broken {SECRET} importer"},
        },
        _assistant(
            "m1",
            "2026-01-01T00:00:10.000Z",
            skill="release-prod",
            text=f"the {SECRET} build failed, let me fix it",
            tools=[
                ("Bash", {"command": f"pytest tests/{SECRET}.py"}),
                ("Bash", {"command": "pytest -x"}),
                ("Edit", {"file_path": f"/x/src/{SECRET}.py"}),
                ("Task", {"description": "delegate"}),
            ],
        ),
        _assistant(
            "m2",
            "2026-01-01T02:30:00.000Z",
            skill="release-prod",
            tools=[("Bash", {"command": "git push"})],
        ),
    ]
    projects = tmp_path / "projects" / "-synthetic-Acme-Widget"
    projects.mkdir(parents=True)
    (projects / f"{SESSION}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n"
    )

    conn = connect(tmp_path / "store.db")
    migrate(conn)
    backfill(conn, tmp_path / "projects")
    rebuild(conn, Registry.load(conn))
    enrich(conn, activity_map={"release-prod": "automation"})
    return conn


def test_the_summary_reads_as_a_sentence(store):
    row = store.execute(
        "SELECT summary FROM v_work_unit_summary WHERE routine = 'release-prod'"
    ).fetchone()
    summary = row["summary"]
    assert summary.startswith("release-prod")
    assert "turns" in summary
    assert "·" in summary, "the parts are separated for scanning"


def test_the_summary_never_carries_captured_content(store):
    """The property this module exists for.

    The fixture threads a distinctive string through every surface a summary
    could plausibly reach for — the prompt, the assistant's prose, a file path,
    a command body and the branch name. None of it may appear.
    """
    rows = store.execute(
        "SELECT summary, routine, project_family, git_branch_kind "
        "FROM v_work_unit_summary"
    ).fetchall()
    assert rows

    for row in rows:
        blob = " ".join(str(v) for v in dict(row).values())
        assert SECRET not in blob
        assert "acquisition" not in blob
        assert "supersecret" not in blob
        assert "/synthetic" not in blob, "no path fragments"
        assert "please fix" not in blob, "no prompt text"


def test_the_verdict_view_never_carries_captured_content(store):
    rows = store.execute("SELECT * FROM v_verdict_readable").fetchall()
    assert rows
    for row in rows:
        blob = " ".join(str(v) for v in dict(row).values())
        assert SECRET not in blob
        assert "please fix" not in blob


def test_bash_verbs_in_the_summary_come_from_the_allowlist(store):
    """`pytest tests/<secret>.py` must contribute `pytest` and nothing else."""
    summary = store.execute(
        "SELECT summary FROM v_work_unit_summary WHERE routine = 'release-prod'"
    ).fetchone()["summary"]
    verbs = re.search(r"\(([^)]*)\)", summary)
    assert verbs, "the verb group should be present"
    for verb in verbs.group(1).split("/"):
        assert verb in {"pytest", "git"}, f"unexpected token in summary: {verb}"


def test_top_verbs_are_capped_at_three(store):
    """An uncapped list prints every verb a long arc ever touched, which is
    noise rather than shape."""
    rows = store.execute("SELECT top_verbs FROM v_work_unit_verbs").fetchall()
    for row in rows:
        if row["top_verbs"]:
            assert len(row["top_verbs"].split("/")) <= 3


def test_the_verdict_view_explains_itself(store):
    """A verdict nobody can read is a verdict nobody acts on. The reasoning
    must name the rule that fired, so a row is defensible without the PRD open.
    """
    row = store.execute(
        "SELECT verdict, reasoning, evidence FROM v_verdict_readable LIMIT 1"
    ).fetchone()
    assert row["verdict"]
    assert row["reasoning"], "every verdict states why"
    assert row["evidence"], "and what the score was built from"
    if row["verdict"] == "Overprovisioned":
        assert "expects" in row["reasoning"]


def test_every_readable_view_labels_value_and_status(store):
    """Invariant 5 and R2 survive the presentation layer — this is exactly
    where a label gets dropped for being 'obvious'."""
    for view in ("v_work_unit_summary", "v_verdict_readable", "v_summary"):
        row = store.execute(f"SELECT * FROM {view} LIMIT 1").fetchone()
        blob = " ".join(str(v) for v in dict(row).values()).lower()
        assert "notional list value" in blob, f"{view} drops the value label"
        assert "provisional" in blob, f"{view} drops the provisional label"


def test_the_summary_reports_a_rate_limit_hit(store):
    """Limit hits are the only on-disk evidence of an allowance boundary
    (invariant 10b), so they belong in the line rather than in a sub-query."""
    store.execute(
        "UPDATE api_call SET error_kind = 'rate_limit' "
        "WHERE id = (SELECT id FROM api_call LIMIT 1)"
    )
    store.commit()
    summaries = [
        r["summary"] for r in store.execute("SELECT summary FROM v_work_unit_summary")
    ]
    assert any("HIT LIMIT" in s for s in summaries)


def test_v_summary_groups_by_pool_and_never_sums_across(store):
    """Invariant 4 in the presentation layer: a percentage of 'the pool' must
    be a percentage of ONE pool."""
    rows = store.execute("SELECT allowance_pool, pct_of_pool FROM v_summary").fetchall()
    assert rows
    assert all(r["allowance_pool"] for r in rows), "pool is never NULL"
    total = sum(r["pct_of_pool"] for r in rows)
    assert total == pytest.approx(100.0, abs=1.0)


def test_the_overprovisioned_figure_is_labelled_an_upper_bound(store):
    """R2: it assumes the cheaper tier finishes in the same tokens, and it will
    not. A dashboard that promises a saving and delivers less destroys the
    credibility of everything else on the page."""
    row = store.execute(
        "SELECT overprovisioned_caveat FROM v_summary LIMIT 1"
    ).fetchone()
    assert "upper bound" in row["overprovisioned_caveat"].lower()
