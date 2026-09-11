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

    total = conn.execute(
        "SELECT COALESCE(SUM(notional_list_value_usd), 0) FROM work_unit"
    ).fetchone()[0]
    typer.echo(f"\n  ${total:,.0f} {NOTIONAL} (not money billed)")
    typer.echo("  classifications are PROVISIONAL — see `select * from v_caveats`")


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
    typer.echo("Start at `v_caveats` — it states what this slice does NOT show.")
    subprocess.run(["datasette", path], check=False)


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
