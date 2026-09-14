"""`mui` — the front door.

Read-only over data already on disk. This slice registers no hooks, starts no
daemon and writes nothing to `~/.claude/`, so invariant 1 ("never break the
thing being observed") is satisfied trivially: there is nothing here that could
wedge a turn.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import typer

from mui import __version__, db
from mui.collect import transcript
from mui.enrich.pipeline import enrich
from mui.normalize.pipeline import rebuild
from mui.normalize.pricing import Registry

app = typer.Typer(
    add_completion=False,
    help=(
        "Model Use Index — what Claude Code actually consumed, and whether the "
        "model tier fit the work. Every dollar figure is NOTIONAL LIST VALUE; "
        "every classification is PROVISIONAL."
    ),
)

NOTIONAL = "notional list value"


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(f"mui {__version__}")


@app.command()
def status(store: str = typer.Option(str(db.DEFAULT_DB_PATH))) -> None:
    """What is in the store right now."""
    conn = db.connect(store)
    db.migrate(conn)

    def count(table: str) -> int:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    typer.echo(f"store: {pathlib.Path(store).expanduser()}")
    for table in (
        "raw_event",
        "api_call",
        "work_unit",
        "prompt_unit",
        "tool_call",
        "classification",
        "verdict",
    ):
        typer.echo(f"  {table:<16} {count(table):>10,}")

    typer.echo("")
    _echo_summary(conn)
    typer.echo(
        "\n  Read a single unit with `select * from v_work_unit_summary`, "
        "\n  or a verdict with `select * from v_verdict_readable`."
    )
    typer.echo("  classifications are PROVISIONAL — see `select * from v_caveats`")


def _echo_summary(conn) -> None:
    """The one-screen answer, grouped by pool because pools never sum."""
    rows = conn.execute(
        "SELECT allowance_pool, ai_activity, work_units, "
        "notional_list_value_usd, pct_of_pool, overprovisioned_units, "
        "overprovisioned_notional_usd FROM v_summary"
    ).fetchall()
    if not rows:
        typer.echo("  nothing classified yet — run `mui classify`")
        return

    for pool in dict.fromkeys(r["allowance_pool"] for r in rows):
        typer.echo(f"  pool: {pool}   (pools are separate ceilings, never summed)")
        typer.echo(
            f"    {'activity':<24}{'units':>6}{'notional':>11}{'%pool':>7}"
            f"{'over':>6}{'over $':>10}"
        )
        for row in (r for r in rows if r["allowance_pool"] == pool):
            typer.echo(
                f"    {(row['ai_activity'] or '(unclassified)'):<24}"
                f"{row['work_units']:>6}"
                f"{row['notional_list_value_usd']:>11,.0f}"
                f"{row['pct_of_pool']:>6.1f}%"
                f"{row['overprovisioned_units']:>6}"
                f"{row['overprovisioned_notional_usd']:>10,.0f}"
            )
        flagged = sum(
            r["overprovisioned_notional_usd"]
            for r in rows
            if r["allowance_pool"] == pool
        )
        typer.echo(
            f"\n    ${flagged:,.0f} {NOTIONAL} flagged over-provisioned — "
            "an UPPER BOUND (R2):"
        )
        typer.echo(
            "    it assumes the cheaper tier finishes in the same tokens, "
            "and it will not."
        )


@app.command()
def backfill(
    projects: str = typer.Option(str(transcript.DEFAULT_PROJECTS_DIR)),
    store: str = typer.Option(str(db.DEFAULT_DB_PATH)),
) -> None:
    """Append every transcript to `raw_event`. Idempotent; safe to re-run."""
    conn = db.connect(store)
    applied = db.migrate(conn)
    if applied:
        typer.echo(f"migrations applied: {', '.join(applied)}")

    stats = transcript.backfill(conn, projects)
    typer.echo(
        f"{stats.files:,} files · {stats.lines:,} lines · "
        f"{stats.inserted:,} new · {stats.duplicates:,} already stored"
    )
    if stats.unparseable:
        typer.echo(
            f"  {stats.unparseable:,} lines did not parse as JSON — stored "
            "anyway, for a later parser (invariant 2b)"
        )


@app.command()
def normalize(store: str = typer.Option(str(db.DEFAULT_DB_PATH))) -> None:
    """Derive api_call / work_unit / prompt_unit / tool_call from raw_event."""
    conn = db.connect(store)
    db.migrate(conn)
    stats = rebuild(conn, Registry.load(conn))
    for key, value in stats.items():
        typer.echo(f"  {key:<16} {value:>10,}")
    if stats["unknown_models"]:
        typer.echo(
            f"  {stats['unknown_models']:,} calls hit an unregistered model — "
            "add it to model_registry rather than letting it default"
        )


@app.command()
def classify(store: str = typer.Option(str(db.DEFAULT_DB_PATH))) -> None:
    """Score, classify and write verdicts. Deterministic; no model involved."""
    conn = db.connect(store)
    db.migrate(conn)
    stats = enrich(conn)
    for key, value in stats.items():
        typer.echo(f"  {key:<16} {value:>10,}")
    typer.echo("\n  PROVISIONAL — not validated until the gold set lands (M2')")


@app.command()
def run(
    projects: str = typer.Option(str(transcript.DEFAULT_PROJECTS_DIR)),
    store: str = typer.Option(str(db.DEFAULT_DB_PATH)),
) -> None:
    """backfill -> normalize -> classify, in one go."""
    ctx = typer.Context
    del ctx
    backfill(projects=projects, store=store)
    normalize(store=store)
    classify(store=store)


@app.command()
def open_ui(store: str = typer.Option(str(db.DEFAULT_DB_PATH))) -> None:
    """Browse the store in Datasette (TD §8.1) — the Phase 1 UI.

    Datasette is pointed at the file rather than a dashboard being hand-built:
    it gives a queryable, faceted UI plus a SQL console for zero code, which is
    also what catches capture bugs while they are still cheap.
    """
    if shutil.which("datasette") is None:
        typer.echo("datasette not installed — `uv sync --extra ui`", err=True)
        raise typer.Exit(1)

    path = str(pathlib.Path(store).expanduser())
    command = ["datasette", path]

    # Without this, Datasette lists nine raw tables above fifteen views and the
    # landing page is `work_unit`: 458 rows of UUIDs and floats, with nothing
    # saying which view answers the question you have. The metadata puts the
    # four readable views up front and repeats the notional-list-value and
    # provisional labels, which are easiest to lose in a UI.
    metadata = pathlib.Path(__file__).resolve().parents[2] / "datasette.yaml"
    if metadata.exists():
        command += ["--metadata", str(metadata)]

    typer.echo("Start at v_summary · v_verdict_readable · v_work_unit_summary")
    typer.echo("v_caveats states what this slice does NOT show. Read it first.")
    subprocess.run(command, check=False)


@app.command()
def verify(
    store: str = typer.Option(str(db.DEFAULT_DB_PATH)),
    repo: str = typer.Option("Phoenix", help="repo substring for the W1 subset"),
) -> None:
    """Check the slice against W1's hand-computed figures.

    Prints numbers only — no transcript content, no paths — so the output can
    be pasted into a PR without violating invariant 6.

    Two classes of target, and the distinction is load-bearing:

    - ASSERTED rows have a stable expected value and participate in the exit
      code. `/release-prod` over its first 10 runs is the main one, pinned to a
      named routine precisely because the corpus total drifts.
    - REPORTED rows are as-of-a-moment. The corpus grows while it is measured —
      analysing transcripts inside Claude Code appends to the very history
      being read — so asserting a frozen total would fail daily for a reason
      that is not a bug.
    """
    from mui.verify import run_checks

    conn = db.connect(store)
    db.migrate(conn)
    failures = run_checks(conn, repo_filter=repo, echo=typer.echo)
    if failures:
        typer.echo(f"\n{failures} asserted check(s) FAILED", err=True)
        raise typer.Exit(1)
    typer.echo("\nall asserted checks passed")


def main() -> None:
    sys.exit(app())


if __name__ == "__main__":
    main()
