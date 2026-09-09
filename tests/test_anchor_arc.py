"""U10 — the anchor-to-arc bounding rule, locked against the golden fixture.

The rule (`u10-next-anchor-v1`): a routine's arc runs from its `attributionSkill`
anchor to the next anchor of *any* skill, else to session end. See milestones
§2 U10 for why the two intuitive refinements (idle-gap, cwd/branch change) lose.

There is no `src/mui` yet (nothing is built — MS §1), so the rule lives here as
the reference implementation the normaliser must reproduce. When
`normalize/work_unit.py` lands, import it here and delete the local copy.
"""

import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "anchor_shapes"


def dedup(records):
    """Invariant 10: one turn per unique API response, keyed by
    (message.id, requestId), max per usage field."""
    groups, order = {}, []
    for r in records:
        msg = r["message"]
        u = msg["usage"]
        key = (msg["id"], r.get("requestId"))
        fields = {
            "input": u.get("input_tokens") or 0,
            "output": u.get("output_tokens") or 0,
            "cache_write": u.get("cache_creation_input_tokens") or 0,
            "cache_read": u.get("cache_read_input_tokens") or 0,
        }
        if key not in groups:
            groups[key] = {
                "session": r["sessionId"],
                "skill": r.get("attributionSkill"),
                "sidechain": bool(r.get("isSidechain")),
                "usage": fields,
            }
            order.append(key)
        else:
            g = groups[key]
            for k, v in fields.items():
                if v > g["usage"][k]:
                    g["usage"][k] = v
            if g["skill"] is None and r.get("attributionSkill"):
                g["skill"] = r["attributionSkill"]
    return [groups[k] for k in order]


def anchor_runs(turns):
    """Contiguous runs of the same attributionSkill -> (start, end, skill)."""
    runs, i, n = [], 0, len(turns)
    while i < n:
        skill = turns[i]["skill"]
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
    """The U10 rule. Returns [{skill, start, end}], end inclusive."""
    runs = anchor_runs(turns)
    out = []
    for k, (start, tag_end, skill) in enumerate(runs):
        end = runs[k + 1][0] - 1 if k + 1 < len(runs) else len(turns) - 1
        out.append({"skill": skill, "start": start, "end": max(end, tag_end)})
    return out


def unattributable(turns):
    """Turn indices belonging to no arc: work before a session's first anchor,
    or every turn when the session has no anchor at all."""
    runs = anchor_runs(turns)
    return list(range(runs[0][0])) if runs else list(range(len(turns)))


@pytest.fixture(scope="module")
def sessions():
    records = [
        json.loads(line)
        for line in (FIXTURES / "anchor_shapes.jsonl").read_text().splitlines()
        if line.strip()
    ]
    by_session = {}
    for turn in dedup(records):
        by_session.setdefault(turn["session"], []).append(turn)
    return by_session


@pytest.fixture(scope="module")
def expected():
    return json.loads((FIXTURES / "expected.json").read_text())


def test_every_fixture_session_is_expected(sessions, expected):
    assert set(sessions) == set(expected["sessions"])


@pytest.mark.parametrize(
    "session_id",
    [
        "SYNTH-single",
        "SYNTH-two-distinct",
        "SYNTH-two-same",
        "SYNTH-pre-anchor",
        "SYNTH-idle-gap",
    ],
)
def test_arc_boundaries_match_golden(sessions, expected, session_id):
    turns = sessions[session_id]
    want = expected["sessions"][session_id]
    assert arcs(turns) == want["arcs"]
    assert unattributable(turns) == want["pre_anchor"]


def test_arcs_never_overlap(sessions):
    """The metric that separates this rule from W1's baseline. Anchor -> session
    end double-counted $13,118 of Opus notional list value; this must be zero."""
    for turns in sessions.values():
        claimed = set()
        for arc in arcs(turns):
            span = set(range(arc["start"], arc["end"] + 1))
            assert not (span & claimed), "arcs overlap — value would be double-counted"
            claimed |= span


def test_arcs_and_remainder_partition_the_session(sessions):
    """No turn is lost: every turn is in exactly one arc or in the remainder."""
    for turns in sessions.values():
        covered = list(unattributable(turns))
        for arc in arcs(turns):
            covered += range(arc["start"], arc["end"] + 1)
        assert sorted(covered) == list(range(len(turns)))


def test_arc_survives_a_six_day_idle_gap(sessions):
    """SYNTH-idle-gap holds a 6-day gap *inside* one arc — a release routine
    waiting on CI. An idle-time boundary would cut here and lose the tail."""
    (arc,) = arcs(sessions["SYNTH-idle-gap"])
    assert arc["end"] == len(sessions["SYNTH-idle-gap"]) - 1


def test_same_skill_reinvocation_is_a_boundary(sessions):
    """Two invocations of one routine are two arcs, not one merged arc."""
    result = arcs(sessions["SYNTH-two-same"])
    assert len(result) == 2
    assert {a["skill"] for a in result} == {"synth-release"}


def test_dedup_takes_max_output_across_a_streaming_group(sessions):
    """Invariant 10: a partial streaming snapshot is written before the final
    count. First-seen dedup would record 500 and undercount output."""
    turns = sessions["SYNTH-idle-gap"]
    assert len(turns) == 4, "the duplicate content-block record must collapse"
    assert turns[1]["usage"]["output"] == 2000
    assert turns[1]["usage"]["cache_read"] == 20000
