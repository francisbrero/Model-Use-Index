"""Dedup and the two boundary rules.

This module is the reference implementation from `tests/test_anchor_arc.py`
(issue #13), moved here as that module's docstring instructed. The rejected
candidates stay in the test, so the register's comparative claim — W1's
baseline double-counts $13,118 of Opus notional list value while this rule
double-counts nothing — remains executable rather than merely asserted.

Two grains, and only one of them carries cost:

- `work_unit` — the ARC grain, `u10-next-anchor-v1`. An `attributionSkill`
  anchor runs to the next anchor of any skill, else to session end. This is the
  grain a verdict attaches to, because a routine is the level a harness default
  is set at. **It is the sole cost-bearing grain.**
- `prompt_unit` — the PROMPT grain, `prompt-unit-v1`. One real user prompt and
  the work it caused. This is the grain W1's six complexity signals were
  calibrated on, and it carries no dollar column: two tables that each sum to
  the whole corpus is a 2x double-count waiting for an ad-hoc join.

Every dollar figure derived from this module is NOTIONAL LIST VALUE.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

ARC_RULE_ID = "u10-next-anchor-v1"
PROMPT_RULE_ID = "prompt-unit-v1"

_USAGE_KEYS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_write", "cache_creation_input_tokens"),
    ("cache_read", "cache_read_input_tokens"),
)


# ---------------------------------------------------------------------------
# Dedup — invariant 10. One turn per unique API response.
# ---------------------------------------------------------------------------


def dedup(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse content-block records to unique API responses.

    Keyed by `(message.id, requestId)`, taking **max per usage field**.

    Claude Code writes one assistant record per content block, and each repeats
    the same `usage` object — a turn with text plus two `tool_use` blocks
    becomes three records. They have distinct `uuid`s and distinct file
    positions; nothing about them looks wrong. Summing them naively overstates
    by ~91%, which is the single way this project would lose credibility on its
    first published number.

    Max, not first-seen: within a group `output_tokens` can differ, because a
    partial streaming snapshot is written before the final count. First-seen
    undercounts output — the trap one level below the obvious one — and
    last-by-file-order is not reliable either. Cache fields are constant within
    a group, so max is safe for all four.

    Non-usage fields are reconciled across the group rather than taken from
    whichever block landed first: `attributionSkill` and `isSidechain` may be
    present on some blocks of a response and absent from others, and first-seen
    would make the result depend on file order.
    """
    groups: dict[tuple, dict[str, Any]] = {}
    order: list[tuple] = []

    for position, record in enumerate(records):
        message = record.get("message") or {}
        usage = message.get("usage") or {}
        key = (message.get("id"), record.get("requestId"))
        fields = {name: usage.get(src) or 0 for name, src in _USAGE_KEYS}

        group = groups.get(key)
        if group is None:
            groups[key] = {
                "message_key": key,
                "message_id": message.get("id"),
                "request_id": record.get("requestId"),
                "session": record.get("sessionId") or record.get("session_id"),
                "model": message.get("model"),
                "skill": record.get("attributionSkill") or None,
                "sidechain": bool(record.get("isSidechain")),
                "timestamp": record.get("timestamp"),
                "cwd": record.get("cwd"),
                "git_branch": record.get("gitBranch"),
                "cc_version": record.get("version"),
                # A limit hit carries no tokens and must never be filtered out:
                # it is the only on-disk evidence of an allowance boundary
                # (invariant 10b). `error` is an enum, not a boolean —
                # `server_error` is at parity with `rate_limit`, and an error
                # record is not a limit hit.
                "error_kind": record.get("error"),
                "api_error_status": record.get("apiErrorStatus"),
                "position": position,
                "usage": fields,
            }
            order.append(key)
            continue

        for name, value in fields.items():
            if value > group["usage"][name]:
                group["usage"][name] = value
        # any-of, not first-seen
        group["sidechain"] = group["sidechain"] or bool(record.get("isSidechain"))
        if group["skill"] is None and record.get("attributionSkill"):
            group["skill"] = record["attributionSkill"]
        if group["error_kind"] is None and record.get("error"):
            group["error_kind"] = record["error"]

    return [groups[key] for key in order]


def to_sessions(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group deduplicated turns by session, ordered by `(timestamp, message.id)`.

    Order is part of the rule, not an accident of file layout: the arc boundary
    is "the next anchor", which is only meaningful in time.

    The tie-break is `message.id` rather than file position deliberately. File
    position is a property of *how the records were read*, not of the records,
    so ordering on it makes an arc boundary depend on read order — and a
    normaliser doing a bare `ORDER BY timestamp` in SQL would resolve the same
    ties differently again. Both keys come from the record, so every derived
    number is reproducible from `raw_event` alone (invariant 2b).

    Ties are rare rather than routine: 1 group of 2 turns in 42,528 measured
    (0.005%), both untagged sidechains, so none can move a boundary today. This
    is insurance against an irreproducible number, not a fix for a live bug.
    """
    by_session: dict[str, list[dict[str, Any]]] = {}
    for turn in dedup(records):
        by_session.setdefault(turn["session"], []).append(turn)
    for turns in by_session.values():
        turns.sort(key=lambda t: (t["timestamp"] or "", t["message_key"][0] or ""))
    return by_session


# ---------------------------------------------------------------------------
# The arc grain — `u10-next-anchor-v1`
# ---------------------------------------------------------------------------


def anchor_runs(turns: list[dict[str, Any]]) -> list[tuple[int, int, str]]:
    """Contiguous runs of the same `attributionSkill` -> (start, tag_end, skill).

    A tag run with a hole (`a, None, a`) splits into two runs, so it is
    indistinguishable from a genuine re-invocation. Accepted: U10 treats
    re-invocation as a boundary anyway, so both readings agree.
    """
    runs: list[tuple[int, int, str]] = []
    i, n = 0, len(turns)
    while i < n:
        skill = turns[i]["skill"]
        # `not skill` rather than `is None`: an empty tag is not an anchor.
        # Defensive only — over 81,982 assistant records the field is either
        # absent or a real value; "" and null never occur (checked 2026-09-09).
        if not skill:
            i += 1
            continue
        j = i
        while j + 1 < n and turns[j + 1]["skill"] == skill:
            j += 1
        runs.append((i, j, skill))
        i = j + 1
    return runs


def arcs(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`u10-next-anchor-v1`. Anchor -> next anchor of any skill, else session end.

    `end` is inclusive. U10 scored the alternatives: attributing only the tagged
    turns reaches 9% of Opus value (invariant 11 — the tag covers a median 15
    turns of an arc that runs a median 69 turns past it); anchor-to-session-end
    reaches 92.6% but double-counts $13,118 because 110 of 137 anchored sessions
    carry more than one anchor. This rule reaches the same 92.6% with zero
    overlap.

    The two intuitive refinements both lose, and are recorded here so they are
    not re-proposed: an idle-gap boundary cuts arcs where a routine waits on CI
    (gaps of 529, 699, 1,730 and 8,605 minutes occur *within* single
    `/release-prod` arcs), and a `cwd`/`gitBranch` boundary cuts them where
    release work legitimately moves across worktrees.

    Known error mode: the rule is generous at the tail — the last anchor in a
    session absorbs everything to session end, including unrelated work that
    follows. Sensitivity says this is not load-bearing (capping the final arc at
    +150 turns moves `/release-prod` by 1.2%), but capping at +50 costs 21%, so
    do not cap tightly.
    """
    runs = anchor_runs(turns)
    out = []
    for k, (start, _tag_end, skill) in enumerate(runs):
        end = runs[k + 1][0] - 1 if k + 1 < len(runs) else len(turns) - 1
        out.append({"skill": skill, "start": start, "end": end})
    return out


def unattributable(turns: list[dict[str, Any]]) -> list[int]:
    """Turn indices in no arc.

    Work before a session's first anchor, or every turn when the session has no
    anchor at all. This is 7.4% of Opus notional list value (6.0% unanchored
    sessions, 1.3% pre-anchor work) and must be a LABELLED ROW, never silently
    dropped (U10).
    """
    runs = anchor_runs(turns)
    return list(range(runs[0][0])) if runs else list(range(len(turns)))


def claimed_counts(turns: list[dict[str, Any]], rule=arcs) -> Counter:
    """How many arcs claim each turn index.

    1 everywhere is correct; >1 is a double-count; 0 means the turn is in the
    remainder. This is the assertion that catches a regression back into the
    rejected baseline.
    """
    counts: Counter = Counter()
    for arc in rule(turns):
        counts.update(range(arc["start"], arc["end"] + 1))
    return counts


# ---------------------------------------------------------------------------
# The prompt grain — `prompt-unit-v1`
# ---------------------------------------------------------------------------


def is_prompt_boundary(record: dict[str, Any]) -> bool:
    """Is this `user` record a real prompt, and therefore a unit boundary?

    Three conditions, all of them load-bearing, and the third was measured
    rather than assumed:

    1. `type == "user"`.
    2. Not `isMeta` and not `isSidechain`. Meta records are harness chatter; a
       sidechain prompt belongs to its parent unit, because per-routine figures
       include their subagent cost by construction (U10, invariant 10 §6).
    3. **The content holds no `tool_result` block.** Claude Code writes tool
       results back as `user`-role records, and they are the overwhelming
       majority: 41,224 of 44,680 Phoenix `user` records (92%) are tool results.
       Cutting a unit at every `user` record yields ~44k units against W1's
       1,823 — off by 24x, which would make the 43.4% target unreachable for a
       reason that is a boundary defect rather than a finding.

    Measured 2026-09-11: this rule yields 2,202 Phoenix prompts, of which 1,918
    triggered main-thread Opus work, against W1's 1,823 — a 5% gap fully
    explained by two days of corpus growth.
    """
    if record.get("type") != "user":
        return False
    if record.get("isMeta") or record.get("isSidechain"):
        return False

    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        kinds = {b.get("type") for b in content if isinstance(b, dict)}
        return "tool_result" not in kinds and bool(kinds & {"text", "image"})
    return False
