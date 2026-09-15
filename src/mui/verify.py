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
- **Skipped** — an asserted check that COULD NOT RUN, because the figure it
  needs is not configured. A skip is a failure, not a pass: it prints as SKIP
  and still drives a non-zero exit. See below.

The reference figures themselves are W1 measurements over one operator's
private history, so they live in the gitignored `config.toml` and this
repository ships no default for any of them (`mui.reference`). That is why the
skip path exists and why it must never degrade into a quiet pass — a gate with
nothing to check against, reporting green, is worse than no gate.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from mui.reference import Reference

RELEASE_ROUTINE = "release-prod"

UNSET = "(unset)"

#: Printed when an asserted check cannot run. Distinct from `reported` on
#: purpose: an operator must be able to tell a row that is deliberately not
#: asserted from a row that failed to find its reference.
SKIPPED = "SKIP"


@dataclass
class Check:
    name: str
    expected: str
    actual: str
    ok: bool | None  # None = reported, not asserted
    note: str = ""
    skipped: bool = False  # asserted, but could not run — counts as a failure


def run_checks(
    conn: sqlite3.Connection,
    repo_filter: str | None,
    echo,
    reference: Reference | None = None,
) -> int:
    """Run every check and return the number that did not pass.

    The return value counts FAILURES **and SKIPS together**, because both mean
    the same thing to a caller: this run did not demonstrate the pipeline is
    right. Counting a skip as a pass is the specific way this gate would become
    decorative.

    `repo_filter` may be `None` (no `--repo` given). The repo-scoped checks then
    skip rather than matching `%None%`, which would read zero rows and print a
    confident, meaningless answer.
    """
    checks: list[Check] = []
    checks.append(_release_prod(conn, reference))
    checks.append(_arc_overlap(conn))
    checks.append(_conservation(conn))
    checks.append(_prompt_unit_count(conn, repo_filter, reference))
    checks.append(_duplicate_ratio(conn, reference))
    checks.append(_score_zero_share(conn, repo_filter, reference))
    checks.extend(_reported(conn, repo_filter, reference))

    echo(f"{'target':<40} {'expected':>16} {'actual':>16}  status")
    echo("-" * 86)
    failures = 0
    for check in checks:
        if check.skipped:
            status = SKIPPED
            failures += 1
        elif check.ok is None:
            status = "reported"
        elif check.ok:
            status = "PASS"
        else:
            status = "FAIL"
            failures += 1
        echo(f"{check.name:<40} {check.expected:>16} {check.actual:>16}  {status}")
        if check.note:
            echo(f"    {check.note}")

    if reference is None:
        echo(
            "\nNo [reference] section in config.toml — the W1 comparison figures "
            "are\nlocal measurements and ship with no default. Asserted checks "
            "above read SKIP\nand this run FAILS. See config.toml.example."
        )
    echo("\nAll dollar figures are NOTIONAL LIST VALUE — not money billed.")
    echo("All classifications are PROVISIONAL (M2', R1). Do not act on them.")
    echo("This slice emits NO headroom figure (U3/U3a deferred).")
    return failures


def _release_prod(conn, reference: Reference | None) -> Check:
    """The one assertion that survives corpus growth.

    Ordered by start time and truncated to the first 10 runs: an 11th run
    landing after U10 was measured would otherwise push the total out of band
    for a reason that is not a regression.
    """
    if reference is None:
        return Check(
            f"/{RELEASE_ROUTINE}, first N runs",
            UNSET,
            "not run",
            False,
            "no [reference] configured — cannot assert. This is a FAILURE, not a pass.",
            skipped=True,
        )
    rows = conn.execute(
        "SELECT notional_list_value_usd FROM work_unit "
        "WHERE kind = 'arc' AND anchor_skill = ? "
        "ORDER BY started_at LIMIT ?",
        (RELEASE_ROUTINE, reference.release_runs),
    ).fetchall()
    total = sum(r[0] for r in rows)
    low = reference.release_target * (1 - reference.release_tolerance)
    high = reference.release_target * (1 + reference.release_tolerance)
    ok = len(rows) == reference.release_runs and low <= total <= high
    return Check(
        f"/{RELEASE_ROUTINE}, first {reference.release_runs} runs",
        f"${reference.release_target:,.0f} ±{reference.release_tolerance:.0%}",
        f"${total:,.0f} ({len(rows)} runs)",
        ok,
        "notional list value; the rule's own output, not W1's hand-read",
    )


def _arc_overlap(conn) -> Check:
    """Zero, asserted. This is what catches a regression into W1's rejected
    baseline, which double-counts roughly $13k of Opus notional list value."""
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


def _prompt_unit_count(conn, repo_filter, reference: Reference | None) -> Check:
    """The check that would actually have caught the 24x boundary bug.

    Cutting at every `user` record yields ~44k units against W1's 1,823,
    because 92% of `user` records are tool results. A band, not a point: the
    corpus grows.

    This one is ASSERTED, so an absent band or an absent `--repo` makes it a
    SKIP rather than a reported row — a reported row would not gate the exit
    code, which is the same vacuous pass by a different door.
    """
    if repo_filter is None or reference is None:
        missing = "no --repo given" if repo_filter is None else "no [reference]"
        return Check(
            "prompt units (repo subset)",
            UNSET,
            "not run",
            False,
            f"{missing} — cannot assert. A repo-scoped check will NOT fall back "
            "to matching every repo.",
            skipped=True,
        )
    # Matched on `project_family`, not `repo`: Phoenix's worktrees carry leaf
    # names like `phoenix1` and `website`, so a `repo` match finds a fraction
    # of the family and undercounts it.
    count = conn.execute(
        "SELECT COUNT(*) FROM prompt_unit WHERE project_family LIKE ?",
        (f"%{repo_filter}%",),
    ).fetchone()[0]
    low, high = reference.prompt_unit_band
    return Check(
        f"prompt units ({repo_filter})",
        f"{low:,}-{high:,}",
        f"{count:,}",
        low <= count <= high,
        "cutting at every `user` record would give roughly 24x this",
    )


def _duplicate_ratio(conn, reference: Reference | None) -> Check:
    """Invariant 10's canary. A sudden move means the transcript writer
    changed, which is invariant 7's schema-drift signal in another guise."""
    # Counted by parsing, not by string-matching the payload: JSON spacing is
    # a writer's choice (Claude Code emits `{"type":"assistant"`, Python's
    # json.dumps emits `{"type": "assistant"`), so a LIKE pattern silently
    # matches zero rows against one of them and the ratio reads 0%.
    raw = _assistant_record_count(conn)
    unique = conn.execute("SELECT COUNT(*) FROM api_call").fetchone()[0]
    ratio = (raw - unique) / raw if raw else 0.0
    if reference is None:
        return Check(
            "duplicate ratio",
            UNSET,
            f"{ratio:.1%}",
            False,
            "no [reference] configured — cannot assert the band",
            skipped=True,
        )
    low, high = reference.duplicate_ratio_band
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


def _score_zero_share(conn, repo_filter, reference: Reference | None) -> Check:
    """W1's 43.4% — share of Phoenix Opus notional list value in score-0
    prompt units. REPORTED, not asserted, and deliberately so.

    W1 read its six signals by hand over 1,823 units. This is a code
    reimplementation of those signals over a grown corpus, and it does not
    reproduce the figure: it lands near 22%.

    THE THRESHOLDS DO NOT MOVE TO CLOSE THAT GAP. Adjusting a cutoff until
    43.4% reappears would fabricate the headline, and the number would then be
    believed — which is the single most likely way this slice goes wrong. The
    gap is the finding, and the gold set (M2', R1) is what resolves it: W1
    itself demonstrated two defensible heuristics over the same data
    disagreeing by three orders of magnitude, so a hand-read and a coded read
    disagreeing by 2x is precisely the outcome that motivated M2'.

    Two known contributors, neither of which justifies a retune:
      - The two language signals are PROPORTIONAL here (>=25% of a unit's turns
        carry the vocabulary). The existential form fires on 78% of units
        because a unit spans a median 10 turns at ~15% each — it would measure
        unit length, which `turn_count` already does.
      - W1's hand-read had the prose in front of it; this reads a scrubbed
        reduction (invariant 6 forbids storing the text).
    """
    if repo_filter is None:
        return Check(
            "score-0 share of value",
            UNSET,
            "not run",
            None,
            "no --repo given; this figure is only meaningful scoped to a project",
        )
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN c.complexity_score = 0 "
        "       THEN v.notional_list_value_usd ELSE 0 END), 0) AS zero, "
        "       COALESCE(SUM(v.notional_list_value_usd), 0) AS total "
        "FROM v_prompt_unit_value v "
        "JOIN classification c ON c.unit_id = v.prompt_unit_id "
        "  AND c.unit_grain = 'prompt_unit' "
        "JOIN prompt_unit p ON p.id = v.prompt_unit_id "
        "WHERE p.project_family LIKE ?",
        (f"%{repo_filter}%",),
    ).fetchone()
    share = 100 * row["zero"] / row["total"] if row["total"] else 0.0
    expected = (
        f"{reference.score_zero_share:.1f}% (W1)"
        if reference is not None and reference.score_zero_share is not None
        else UNSET
    )
    return Check(
        "score-0 share of value",
        expected,
        f"{share:.1f}%",
        None,
        "REPORTED, never asserted — the gap is a finding for the gold set "
        "(M2'), not a threshold to tune",
    )


def _reported(conn, repo_filter, reference: Reference | None) -> list[Check]:
    """As-of-a-moment figures. Printed beside their W1 reference where one is
    configured, and against `(unset)` where none is — never asserted either
    way, because the corpus grows while it is being measured."""
    unique = conn.execute(
        "SELECT COUNT(*) FROM api_call WHERE model_tier = 'frontier'"
    ).fetchone()[0]
    total = conn.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM api_call "
        "WHERE model_tier = 'frontier'"
    ).fetchone()[0]
    subset = (
        conn.execute(
            "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM work_unit "
            "WHERE project_family LIKE ?",
            (f"%{repo_filter}%",),
        ).fetchone()[0]
        if repo_filter is not None
        else None
    )
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

    def w1(value: float | None, fmt: str, prefix: str = "", suffix: str = "") -> str:
        """A W1 comparand, or `(unset)`.

        The ` (W1)` suffix is attached only where a figure exists — `(unset)
        (W1)` would read as a real reference.

        `prefix`/`suffix` carry the UNIT, and they are not decoration. This
        column mixes counts, dollars and percentages, so a bare `23,059` beside
        an actual of `$0` is a dollar figure that does not announce itself as
        one — which invariant 5 does not allow, and which also invites reading
        a percentage reference as an absolute.
        """
        if value is None:
            return UNSET
        return f"{prefix}{format(value, fmt)}{suffix} (W1)"

    r = reference
    subset_share = (
        UNSET if subset is None else f"{(100 * subset / grand if grand else 0):.1f}%"
    )
    return [
        Check(
            "unique frontier responses",
            w1(None if r is None else r.frontier_unique, ","),
            f"{unique:,}",
            None,
            "corpus grows while measured — the W1 figure is as of 2026-09-09",
        ),
        Check(
            "frontier notional list value",
            w1(None if r is None else r.frontier_value, ",.0f", prefix="$"),
            f"${total:,.0f}",
            None,
            "as-of-a-moment; not asserted",
        ),
        Check(
            "repo subset share",
            w1(None if r is None else r.subset_share, ".1f", suffix="%"),
            subset_share,
            None,
            "no --repo given" if repo_filter is None else f"scoped to {repo_filter}",
        ),
        Check(
            "unattributable remainder",
            w1(None if r is None else r.remainder_share, ".1f", suffix="%"),
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
