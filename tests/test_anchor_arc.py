"""U10 — the anchor-to-arc bounding rule, locked against the golden fixture.

The rule (`u10-next-anchor-v1`): a routine's arc runs from its `attributionSkill`
anchor to the next anchor of *any* skill, else to session end. See milestones
§2 U10 for the candidate scoring and why the two intuitive refinements
(idle-gap, `cwd`/`gitBranch` change) lose on evidence.

The rejected candidates are implemented here too, deliberately. The register's
load-bearing claim is comparative — the W1 baseline double-counts $13,118 of
Opus notional list value while this rule double-counts nothing — and a claim
that only one rule is in the module is a claim no test can check.

The accepted rule now lives in `mui.normalize.work_unit` and is imported here
(issue #14, M1). The REJECTED candidates stay local to this module on purpose:
the register's load-bearing claim is comparative — the W1 baseline double-counts
$13,118 of Opus notional list value while this rule double-counts nothing — and
a claim that only one rule is in the module is a claim no test can check.

Every dollar figure in this module and its fixture is NOTIONAL LIST VALUE
(invariant 5).
"""

import json
import pathlib
from collections import Counter

import pytest

from mui.normalize.work_unit import (
    anchor_runs,
    arcs,
    claimed_counts,
    dedup,
    to_sessions,
    unattributable,
)

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
    "SYNTH-no-anchor",
    "SYNTH-adjacent-anchors",
    "SYNTH-dup-and-tie",
]


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
# Rejected candidates. Kept local so the comparison stays executable.
# --------------------------------------------------------------------------


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


# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def expected():
    return json.loads((FIXTURES / "expected.json").read_text())


@pytest.fixture(scope="module")
def rates(expected):
    return expected["rates_notional_list_value_usd_per_1m"]["opus"]


@pytest.fixture(scope="module")
def raw_records():
    return [
        json.loads(line)
        for line in (FIXTURES / "anchor_shapes.jsonl").read_text().splitlines()
        if line.strip()
    ]


@pytest.fixture(scope="module")
def sessions():
    records = [
        json.loads(line)
        for line in (FIXTURES / "anchor_shapes.jsonl").read_text().splitlines()
        if line.strip()
    ]
    return to_sessions(records)


def test_duplicate_blocks_carry_distinct_uuids(raw_records):
    """The fixture must reproduce *why* the duplicates are deceptive.

    Claude Code gives every content-block record its own `uuid`, so a duplicate
    group looks like several legitimate separate records — nothing about them is
    malformed. A fixture that reused one uuid across a group would misrepresent
    the shape and quietly suggest `uuid` was a usable dedup key. Invariant 10
    says it is not.
    """
    uuids = [r["uuid"] for r in raw_records]
    assert len(uuids) == len(set(uuids)), "content-block records need distinct uuids"
    groups = Counter((r["message"]["id"], r.get("requestId")) for r in raw_records)
    assert max(groups.values()) > 1, (
        "the fixture must contain at least one real duplicate group"
    )
    assert len(uuids) > len(groups), "duplicate blocks must outnumber API responses"


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


def test_a_session_with_no_anchor_is_entirely_unattributable(sessions):
    """The largest component of the remainder, and the easiest to lose.

    At full scale, sessions with no anchor at all are 6.0% of Opus notional list
    value ($1,416 across 48 sessions) against 1.3% for pre-first-anchor work. A
    rule that returned an empty remainder here would understate the labelled
    7.4% figure by four fifths while every arc assertion still passed.
    """
    turns = sessions["SYNTH-no-anchor"]
    assert all(t["skill"] is None for t in turns), "the fixture must be untagged"
    assert arcs(turns) == []
    assert unattributable(turns) == list(range(len(turns)))


def test_adjacent_anchor_runs_both_produce_an_arc(sessions):
    """Two anchors with no untagged turn between them. Every other multi-anchor
    session here has a gap, which lets a run-advance off-by-one skip the second
    anchor silently; here it would drop an entire arc."""
    turns = sessions["SYNTH-adjacent-anchors"]
    runs = anchor_runs(turns)
    assert [(start, tag_end) for start, tag_end, _ in runs] == [(0, 1), (2, 3)], (
        "the fixture's two runs must be directly adjacent"
    )
    assert [a["skill"] for a in arcs(turns)] == ["synth-release", "synth-pr"]


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


def test_turns_are_ordered_by_timestamp(sessions):
    """`SYNTH-out-of-order` pins **timestamp as the primary key**, against both
    of the wrong orderings.

    Its records are written to the file as Oa(10:02), Oz(10:00), Om(10:01), and
    the ids are minted so lexicographic order is the *reverse* of chronological
    order. Sorting on file position puts the anchor at index 1 and loses turn 0
    to the remainder; sorting on `message.id` alone reverses the session; only
    `(timestamp, message.id)` gives the anchor index 0 and the arc [0..2].

    Without that contradiction the test proves nothing: in every other session
    the ids happen to sort in timestamp order, so the primary key could be
    deleted outright and the suite would stay green.
    """
    turns = sessions["SYNTH-out-of-order"]
    ids = [t["message_key"][0] for t in turns]
    assert ids != sorted(ids), (
        "id order must contradict timestamp order, or timestamp-primary is untested"
    )
    assert [t["position"] for t in turns] != sorted(t["position"] for t in turns), (
        "the fixture must actually be out of file order, or this proves nothing"
    )
    assert [t["timestamp"] for t in turns] == sorted(t["timestamp"] for t in turns), (
        "turns must be sorted into chronological order"
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
    # `== value` alone cannot separate any-of from last-wins when the *later*
    # block is the bare one, so assert the bare block does not clear the field
    if order == ("first", "second"):
        assert turn[key] is not None and turn[key] is not False, (
            f"a later bare block must not overwrite {field} — that is last-wins"
        )


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


def test_dedup_is_max_not_last_by_file_order(sessions):
    """Invariant 10 rejects first-seen *and* last-by-file-order, so the fixture
    carries a duplicate group in each direction.

    `SYNTH-idle-gap`'s group is written 500 then 2,000 — there last-wins happens
    to equal max, so it cannot tell the two apart. This group is written 2,000,
    500, 900: max is 2,000, last-wins would be 900 and first-seen 2,000. Only
    max satisfies both sessions at once.
    """
    turns = sessions["SYNTH-dup-and-tie"]
    assert len(turns) == 3, "three content blocks must collapse to one response"
    assert turns[2]["usage"]["output"] == 2000, (
        "max per field — not last-by-file-order (900), not the mean"
    )
    assert turns[2]["usage"]["cache_read"] == 8000


def test_order_tie_is_broken_by_message_id(sessions):
    """Two turns sharing an identical timestamp: the untagged one is written
    first, so `(timestamp, message.id)` puts the anchor second.

    Real transcripts routinely emit several turns inside the same second.
    Sorting on timestamp alone leaves the order unspecified, and since the arc
    boundary is defined by order, that would make derived numbers
    irreproducible — invariant 2b.
    """
    turns = sessions["SYNTH-dup-and-tie"]
    assert turns[0]["timestamp"] == turns[1]["timestamp"], (
        "the fixture must contain a genuine timestamp tie"
    )
    # the pair also breaks the message.id / requestId 1:1, so the two fields
    # order it oppositely — a tie-break on requestId would swap these turns
    assert turns[0]["message_key"][1] > turns[1]["message_key"][1], (
        "requestId must order the tie the other way, or requestId-vs-message.id "
        "is untested"
    )
    assert turns[0]["message_key"][0] < turns[1]["message_key"][0], (
        "the tie must resolve on message.id, a property of the record"
    )
    assert turns[0]["skill"] is None
    assert turns[1]["skill"] == "synth-release"
    (arc,) = arcs(turns)
    assert (arc["start"], arc["end"]) == (1, 2)
    assert unattributable(turns) == [0]


def test_tied_timestamps_are_ordered_deterministically(sessions):
    """The property the `(timestamp, message.id)` key actually buys: the same
    records in a different input order must yield the same arcs.

    Python's `sort` is stable, so *within this module* dropping the tie-break
    degrades to file order and is indistinguishable. The mutation this guards
    against is a reimplementation that reorders — a normaliser doing
    `ORDER BY timestamp` in SQL, where ties come back in whatever order the
    query planner chose. Sorting a shuffled input is how that gets caught here
    without depending on CPython's stability guarantee.
    """
    records = [
        json.loads(line)
        for line in (FIXTURES / "anchor_shapes.jsonl").read_text().splitlines()
        if line.strip()
    ]
    tied = [r for r in records if r["sessionId"] == "SYNTH-dup-and-tie"]
    baseline = to_sessions(tied)["SYNTH-dup-and-tie"]
    # the two tied records are the ones whose relative order is contestable
    reordered = [tied[1], tied[0], *tied[2:]]
    shuffled = to_sessions(reordered)["SYNTH-dup-and-tie"]
    assert [t["message_key"] for t in shuffled] == [
        t["message_key"] for t in baseline
    ], "tied timestamps must resolve to a stable order, not the input order"


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
