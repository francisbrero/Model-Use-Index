"""The step-4 acceptance gate: does the pipeline reproduce W1's figures?

This is a real criterion, not a vibe. If these do not reproduce, the pipeline
is wrong.

It runs over the operator's real history, which is why it is a CLI command
rather than a committed test: a real transcript must never be committed
(invariant 6). Its output is numbers only — no paths, no content — so it can be
pasted into a PR body, which is what keeps the gate auditable.

TWO CLASSES OF TARGET, and conflating them is how this check becomes useless:

- **Asserted** — stable, and they gate the exit code. `/release-prod` over its
  first 10 runs is the anchor: U10 pinned the regression target to a NAMED
  ROUTINE exactly because corpus totals drift while routine totals do not.
- **Reported** — as-of-a-moment. The corpus grows while being measured
  (analysing transcripts inside Claude Code appends to the history being read),
  so an asserted corpus total would fail daily for a reason that is not a bug.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

RELEASE_ROUTINE = "release-prod"
RELEASE_RUNS = 10
RELEASE_TARGET = 1447.0
RELEASE_TOLERANCE = 0.05

DUPLICATE_RATIO_BAND = (0.45, 0.52)
PROMPT_UNIT_BAND = (1500, 2400)


@dataclass
class Check:
    name: str
    expected: str
    actual: str
    ok: bool | None  # None = reported, not asserted
    note: str = ""


def run_checks(conn: sqlite3.Connection, repo_filter: str, echo) -> int:
    checks: list[Check] = []
    checks.append(_release_prod(conn))
    checks.append(_arc_overlap(conn))
    checks.append(_conservation(conn))
    checks.append(_prompt_unit_count(conn, repo_filter))
    checks.append(_duplicate_ratio(conn))
    checks.extend(_reported(conn, repo_filter))

    echo(f"{'target':<40} {'expected':>16} {'actual':>16}  status")
    echo("-" * 86)
    failures = 0
    for check in checks:
        if check.ok is None:
            status = "reported"
        elif check.ok:
            status = "PASS"
        else:
            status = "FAIL"
            failures += 1
        echo(f"{check.name:<40} {check.expected:>16} {check.actual:>16}  {status}")
        if check.note:
            echo(f"    {check.note}")

    echo("\nAll dollar figures are NOTIONAL LIST VALUE — not money billed.")
    echo("All classifications are PROVISIONAL (M2', R1). Do not act on them.")
    echo("This slice emits NO headroom figure (U3/U3a deferred).")
    return failures


def _release_prod(conn) -> Check:
    """The one assertion that survives corpus growth.

    Ordered by start time and truncated to the first 10 runs: an 11th run
    landing after U10 was measured would otherwise push the total out of band
    for a reason that is not a regression.
    """
    rows = conn.execute(
        "SELECT notional_list_value_usd FROM work_unit "
        "WHERE kind = 'arc' AND anchor_skill = ? "
        "ORDER BY started_at LIMIT ?",
        (RELEASE_ROUTINE, RELEASE_RUNS),
    ).fetchall()
    total = sum(r[0] for r in rows)
    low = RELEASE_TARGET * (1 - RELEASE_TOLERANCE)
    high = RELEASE_TARGET * (1 + RELEASE_TOLERANCE)
    ok = len(rows) == RELEASE_RUNS and low <= total <= high
    return Check(
        f"/{RELEASE_ROUTINE}, first {RELEASE_RUNS} runs",
        f"${RELEASE_TARGET:,.0f} ±5%",
        f"${total:,.0f} ({len(rows)} runs)",
        ok,
        "notional list value; the rule's own output, not W1's $1,511 hand-read",
    )


def _arc_overlap(conn) -> Check:
    """Zero, asserted. This is what catches a regression into W1's rejected
    baseline, which double-counts $13,118 of Opus notional list value."""
    overlaps = conn.execute(
        "SELECT COUNT(*) FROM (SELECT work_unit_id, turn_index FROM api_call "
        "WHERE work_unit_id IS NOT NULL GROUP BY session_id, turn_index "
        "HAVING COUNT(DISTINCT work_unit_id) > 1)"
    ).fetchone()[0]
    return Check("arc overlap (turns in 2+ arcs)", "0", str(overlaps), overlaps == 0)


def _conservation(conn) -> Check:
    """Arcs plus remainder must account for every costed call exactly once.

    Named honestly: this is a COVERAGE check. It catches orphaned rows, not a
    boundary rule that cuts in the wrong place — a wrong rule still conserves
    value, because every call lands in exactly one unit either way.
    """
    orphans = conn.execute(
        "SELECT COUNT(*) FROM api_call WHERE work_unit_id IS NULL"
    ).fetchone()[0]
    return Check(
        "api_call coverage (orphaned rows)",
        "0",
        str(orphans),
        orphans == 0,
        "coverage, not boundary correctness — see prompt-unit count below",
    )


def _prompt_unit_count(conn, repo_filter) -> Check:
    """The check that would actually have caught the 24x boundary bug.

    Cutting at every `user` record yields ~44k units against W1's 1,823,
    because 92% of `user` records are tool results. A band, not a point: the
    corpus grows.
    """
    # Matched on `project_family`, not `repo`: Phoenix's worktrees carry leaf
    # names like `phoenix1` and `website`, so a `repo` match finds a fraction
    # of the family and undercounts it.
    count = conn.execute(
        "SELECT COUNT(*) FROM prompt_unit WHERE project_family LIKE ?",
        (f"%{repo_filter}%",),
    ).fetchone()[0]
    low, high = PROMPT_UNIT_BAND
    return Check(
        f"prompt units ({repo_filter})",
        f"{low:,}-{high:,}",
        f"{count:,}",
        low <= count <= high,
        "W1 measured 1,823; cutting at every `user` record would give ~44,000",
    )


def _duplicate_ratio(conn) -> Check:
    """Invariant 10's canary. A sudden move means the transcript writer
    changed, which is invariant 7's schema-drift signal in another guise."""
    # Counted by parsing, not by string-matching the payload: JSON spacing is
    # a writer's choice (Claude Code emits `{"type":"assistant"`, Python's
    # json.dumps emits `{"type": "assistant"`), so a LIKE pattern silently
    # matches zero rows against one of them and the ratio reads 0%.
    raw = _assistant_record_count(conn)
    unique = conn.execute("SELECT COUNT(*) FROM api_call").fetchone()[0]
    ratio = (raw - unique) / raw if raw else 0.0
    low, high = DUPLICATE_RATIO_BAND
    return Check(
        "duplicate ratio",
        f"{low:.0%}-{high:.0%}",
        f"{ratio:.1%}",
        low <= ratio <= high,
        "W1 measured ~48%; summing without dedup overstates cost by ~91%",
    )


def _assistant_record_count(conn) -> int:
    """Raw `assistant` records, before dedup — the denominator of the
    duplicate ratio."""
    total = 0
    for (payload,) in conn.execute("SELECT payload FROM raw_event"):
        try:
            record = json.loads(payload)
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict) and record.get("type") == "assistant":
            total += 1
    return total


def _reported(conn, repo_filter) -> list[Check]:
    """As-of-a-moment figures. Printed with their W1 reference, never asserted."""
    unique = conn.execute(
        "SELECT COUNT(*) FROM api_call WHERE model_tier = 'frontier'"
    ).fetchone()[0]
    total = conn.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM api_call "
        "WHERE model_tier = 'frontier'"
    ).fetchone()[0]
    subset = conn.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM work_unit "
        "WHERE project_family LIKE ?",
        (f"%{repo_filter}%",),
    ).fetchone()[0]
    remainder = conn.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM work_unit "
        "WHERE kind = 'unattributable'"
    ).fetchone()[0]
    grand = conn.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM work_unit"
    ).fetchone()[0]

    mixed = conn.execute(
        "SELECT COUNT(*) FROM verdict WHERE max_tier IS NOT NULL "
        "AND max_tier <> used_tier"
    ).fetchone()[0]
    verdicts = conn.execute("SELECT COUNT(*) FROM verdict").fetchone()[0]

    return [
        Check(
            "unique frontier responses",
            "37,781 (W1)",
            f"{unique:,}",
            None,
            "corpus grows while measured — W1's figure is as of 2026-09-09",
        ),
        Check(
            "frontier notional list value",
            "$23,059 (W1)",
            f"${total:,.0f}",
            None,
            "as-of-a-moment; not asserted",
        ),
        Check(
            f"{repo_filter} share",
            "73.4% (W1)",
            f"{(100 * subset / grand if grand else 0):.1f}%",
            None,
        ),
        Check(
            "unattributable remainder",
            "7.4% (W1)",
            f"{(100 * remainder / grand if grand else 0):.1f}%",
            None,
            "a labelled row, never dropped",
        ),
        Check(
            "arcs where max_tier != used_tier",
            "—",
            f"{mixed:,} of {verdicts:,}",
            None,
            "if large, a single tier per arc is itself the finding",
        ),
    ]
