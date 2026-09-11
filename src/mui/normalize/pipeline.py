"""Drive the derivation: `raw_event` -> api_call / work_unit / prompt_unit / tool_call.

Everything here is recomputable from `raw_event` alone (invariant 2b), so the
derived tables are rebuilt wholesale on each run rather than patched. That is
the recovery story: a parser bug is fixed by fixing the parser and re-running,
never by editing captured data.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from typing import Any

from mui.normalize.pricing import Registry
from mui.normalize.tools import iter_tool_calls
from mui.normalize.work_unit import (
    ARC_RULE_ID,
    PROMPT_RULE_ID,
    arcs,
    is_prompt_boundary,
    to_sessions,
    unattributable,
)

DERIVED_TABLES = (
    "verdict",
    "classification",
    "tool_call",
    "api_call",
    "prompt_unit",
    "work_unit",
)


def iter_raw(conn: sqlite3.Connection, counter: dict | None = None):
    """Every captured record, parsed.

    A line that will not parse is skipped and COUNTED, never dropped from
    `raw_event` — it stays there for a later parser to pick up (invariant 2b).
    The count is invariant 7's schema-drift canary: the transcript format is
    undocumented and unstable, so a rising parse-failure rate is the earliest
    signal that the writer changed, and it must be a number rather than a
    silent absence.
    """
    for row in conn.execute("SELECT payload FROM raw_event ORDER BY id"):
        try:
            record = json.loads(row["payload"])
        except (ValueError, TypeError):
            if counter is not None:
                counter["parse_failures"] = counter.get("parse_failures", 0) + 1
            continue
        if isinstance(record, dict):
            yield record


def _repo_of(cwd: str | None) -> str | None:
    """Repo name only — never the full path (invariant 6, G4)."""
    if not cwd:
        return None
    return cwd.rstrip("/").rsplit("/", 1)[-1] or None


# Directory segments that mark a worktree rather than naming a project.
_WORKTREE_MARKERS = ("worktrees", "worktree", ".worktrees")


def _project_family(cwd: str | None) -> str | None:
    """The project a worktree belongs to, not the worktree itself.

    `.../MadKudu/Phoenix-worktrees/phoenix1` and
    `.../MadKudu/Phoenix/webapp/worktrees/bug2` both belong to `Phoenix`.
    Grouping by the leaf directory instead scatters one project across a dozen
    names — which is exactly how W1's "Phoenix and its worktrees are 73.4%"
    would come out as a handful of unrelated small rows.

    Returns a single directory NAME, never a path (invariant 6).
    """
    if not cwd:
        return None
    parts = [p for p in cwd.strip("/").split("/") if p]
    if not parts:
        return None

    # Scan left to right and stop at the FIRST worktree marker, so a nested
    # layout resolves to the outermost project: `Phoenix/webapp/worktrees/bug2`
    # is Phoenix work in the webapp subtree, not a separate `webapp` project.
    for index, part in enumerate(parts):
        lowered = part.lower()
        # `Phoenix-worktrees/x` — the family is the prefix before the marker.
        for marker in _WORKTREE_MARKERS:
            if lowered.endswith(f"-{marker}") and len(part) > len(marker) + 1:
                return part[: -(len(marker) + 1)]
        # `Phoenix/webapp/worktrees/x` — walk back to the first segment that is
        # not itself a subtree of the project directory.
        if lowered in _WORKTREE_MARKERS and index > 0:
            return parts[max(0, index - 2)] if index >= 2 else parts[index - 1]

    return parts[-1]


def _assistant_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if r.get("type") == "assistant"]


def rebuild(conn: sqlite3.Connection, registry: Registry | None = None) -> dict:
    """Rebuild every derived table from `raw_event`. Idempotent by construction."""
    registry = registry or Registry.load(conn)

    counter: dict[str, int] = {}
    records = list(iter_raw(conn, counter))
    by_session_records: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        session = record.get("sessionId") or record.get("session_id")
        if session:
            by_session_records.setdefault(session, []).append(record)

    sessions = to_sessions(_assistant_records(records))

    with conn:
        for table in DERIVED_TABLES:
            conn.execute(f"DELETE FROM {table}")

        stats = {
            "parse_failures": counter.get("parse_failures", 0),
            "sessions": 0,
            "api_calls": 0,
            "work_units": 0,
            "prompt_units": 0,
            "unknown_models": 0,
        }

        for session_id, turns in sessions.items():
            stats["sessions"] += 1
            _write_session(
                conn,
                registry,
                session_id,
                turns,
                by_session_records.get(session_id, []),
                stats,
            )

    return stats


def _write_session(conn, registry, session_id, turns, raw_records, stats) -> None:
    # --- arcs (the cost-bearing grain) -------------------------------------
    arc_list = arcs(turns)
    remainder = unattributable(turns)

    turn_owner: dict[int, str] = {}
    for index, arc in enumerate(arc_list):
        unit_id = f"{session_id}:arc:{index}"
        span = turns[arc["start"] : arc["end"] + 1]
        _insert_work_unit(
            conn,
            registry,
            unit_id,
            session_id,
            "arc",
            arc["skill"],
            arc["start"],
            arc["end"],
            span,
        )
        for i in range(arc["start"], arc["end"] + 1):
            turn_owner[i] = unit_id
        stats["work_units"] += 1

    if remainder:
        unit_id = f"{session_id}:remainder"
        span = [turns[i] for i in remainder]
        _insert_work_unit(
            conn,
            registry,
            unit_id,
            session_id,
            "unattributable",
            None,
            remainder[0],
            remainder[-1],
            span,
        )
        for i in remainder:
            turn_owner[i] = unit_id
        stats["work_units"] += 1

    # --- prompt units (scoring grain, no cost column) ----------------------
    prompt_owner = _write_prompt_units(
        conn, session_id, turns, raw_records, turn_owner, stats
    )

    # --- api calls (one row per unique API response) -----------------------
    for index, turn in enumerate(turns):
        _insert_api_call(
            conn,
            registry,
            session_id,
            index,
            turn,
            turn_owner.get(index),
            prompt_owner.get(index),
            stats,
        )

    # --- tool calls (input to three of the six signals, and to `stakes`) ---
    _write_tool_calls(conn, session_id, raw_records, turns, turn_owner, prompt_owner)


def _write_tool_calls(
    conn, session_id, raw_records, turns, turn_owner, prompt_owner
) -> None:
    """One row per `tool_use` block, targets normalised at extraction.

    Ownership is resolved by timestamp against the deduped turn stream, since a
    tool_use block belongs to the assistant turn that emitted it.
    """
    turn_times = [(t["timestamp"] or "", i) for i, t in enumerate(turns)]
    turn_times.sort()

    counter = 0
    for record in raw_records:
        if record.get("type") != "assistant":
            continue
        ts = record.get("timestamp") or ""
        index = _turn_at(turn_times, ts)
        for name, target in iter_tool_calls(record):
            if not name:
                continue
            counter += 1
            conn.execute(
                "INSERT OR IGNORE INTO tool_call (id, session_id, work_unit_id, "
                "prompt_unit_id, tool_name, target, is_error, is_sidechain, "
                "turn_index, started_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    f"{session_id}:tool:{counter}",
                    session_id,
                    turn_owner.get(index),
                    prompt_owner.get(index),
                    name,
                    target,
                    0,
                    int(bool(record.get("isSidechain"))),
                    index if index is not None else -1,
                    ts,
                ),
            )


def _turn_at(turn_times, timestamp):
    """Index of the last turn at or before `timestamp`."""
    found = None
    for ts, index in turn_times:
        if ts <= timestamp:
            found = index
        else:
            break
    return found


def _write_prompt_units(conn, session_id, turns, raw_records, turn_owner, stats):
    """Assign each assistant turn to the prompt that caused it.

    Boundaries are real prompts only (`prompt-unit-v1`); 92% of `user` records
    are tool results and are NOT boundaries. Work before the first prompt of a
    session belongs to no prompt unit and simply carries a NULL FK — it is
    still costed, via its arc.
    """
    boundaries = [
        r.get("timestamp") or "" for r in raw_records if is_prompt_boundary(r)
    ]
    boundaries.sort()

    prompt_owner: dict[int, str] = {}
    if not boundaries:
        return prompt_owner

    # Walk turns in order, advancing the prompt pointer as timestamps pass it.
    pointer = -1
    members: dict[int, list[int]] = {}
    for index, turn in enumerate(turns):
        ts = turn["timestamp"] or ""
        while pointer + 1 < len(boundaries) and boundaries[pointer + 1] <= ts:
            pointer += 1
        if pointer < 0:
            continue
        prompt_owner[index] = f"{session_id}:prompt:{pointer}"
        members.setdefault(pointer, []).append(index)

    for pointer_index, turn_indexes in members.items():
        unit_id = f"{session_id}:prompt:{pointer_index}"
        first, last = turn_indexes[0], turn_indexes[-1]
        conn.execute(
            "INSERT INTO prompt_unit (id, session_id, work_unit_id, rule_id, "
            "start_turn, end_turn, turns, started_at, ended_at, repo, "
            "project_family, allowance_pool) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                unit_id,
                session_id,
                turn_owner.get(first),
                PROMPT_RULE_ID,
                first,
                last,
                len(turn_indexes),
                turns[first]["timestamp"],
                turns[last]["timestamp"],
                _repo_of(turns[first].get("cwd")),
                _project_family(turns[first].get("cwd")),
                "anthropic-seat",
            ),
        )
        stats["prompt_units"] += 1

    return prompt_owner


def _insert_work_unit(
    conn, registry, unit_id, session_id, kind, skill, start, end, span
) -> None:
    total = 0.0
    for turn in span:
        # An unregistered model contributes 0 here rather than aborting the
        # unit; `api_call` still records the row, and `stats.unknown_models`
        # surfaces the registry gap.
        with contextlib.suppress(LookupError):
            total += registry.notional_list_value_usd(turn["model"], turn["usage"])
    first = span[0] if span else None
    last = span[-1] if span else None
    conn.execute(
        "INSERT INTO work_unit (id, session_id, kind, rule_id, anchor_skill, "
        "start_turn, end_turn, turns, started_at, ended_at, cwd, repo, "
        "project_family, git_branch, cc_version, allowance_pool, "
        "notional_list_value_usd) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            unit_id,
            session_id,
            kind,
            ARC_RULE_ID,
            skill,
            start,
            end,
            len(span),
            first["timestamp"] if first else None,
            last["timestamp"] if last else None,
            None,  # cwd omitted: a full path is captured data (invariant 6)
            _repo_of(first.get("cwd")) if first else None,
            _project_family(first.get("cwd")) if first else None,
            first.get("git_branch") if first else None,
            first.get("cc_version") if first else None,
            "anthropic-seat",
            total,
        ),
    )


def _insert_api_call(
    conn, registry, session_id, index, turn, work_unit_id, prompt_unit_id, stats
) -> None:
    model = turn["model"] or "<unknown>"
    try:
        rate = registry.resolve(model)
        tier, pool = rate.tier, rate.allowance_pool
        value = registry.notional_list_value_usd(model, turn["usage"])
    except LookupError:
        # Loud in `mui doctor`, but never a reason to drop the record: an
        # unregistered model is a registry gap, and losing the row would lose
        # the evidence of it.
        stats["unknown_models"] += 1
        tier, pool, value = "small", "anthropic-seat", 0.0

    usage = turn["usage"]
    conn.execute(
        "INSERT OR IGNORE INTO api_call (id, session_id, work_unit_id, "
        "prompt_unit_id, message_id, request_id, provider, allowance_pool, "
        "model, model_tier, input_tokens, output_tokens, cache_creation_tokens, "
        "cache_read_tokens, notional_list_value_usd, registry_version, "
        "attribution_skill, is_sidechain, error_kind, api_error_status, "
        "cc_version, turn_index, started_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            f"{turn['message_id']}|{turn['request_id']}",
            session_id,
            work_unit_id,
            prompt_unit_id,
            turn["message_id"],
            turn["request_id"],
            "anthropic",
            pool,
            model,
            tier,
            usage["input"],
            usage["output"],
            usage["cache_write"],
            usage["cache_read"],
            value,
            registry.version,
            turn["skill"],
            int(turn["sidechain"]),
            turn["error_kind"],
            turn["api_error_status"],
            turn["cc_version"],
            index,
            turn["timestamp"],
        ),
    )
    stats["api_calls"] += 1
