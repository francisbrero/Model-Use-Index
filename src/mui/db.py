"""SQLite connection and the migration runner.

Raw SQL in numbered `.sql` files applied against a `schema_version` table. No
ORM and no Alembic (invariant 8, TD §5): the schema is analytical and the
queries are the product, so hiding them behind a mapper would hide the thing
that matters.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sqlite3

DEFAULT_DB_PATH = pathlib.Path.home() / ".model-use-index" / "store.db"
MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[2] / "migrations"


def connect(path: pathlib.Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the store with the pragmas TD §5 settled on.

    WAL so a reader (Datasette, the operator's own sqlite3) never blocks the
    batch writer. `synchronous=NORMAL` because this is a derived, re-runnable
    store — everything in it can be rebuilt from `raw_event`, and `raw_event`
    itself from transcripts still on disk. `busy_timeout` so the second writer
    waits rather than raising the intermittent, night-only `database is locked`
    that a retry loop would otherwise have to paper over.
    """
    path = pathlib.Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _applied(conn: sqlite3.Connection) -> set[int]:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row is None:
        return set()
    return {r[0] for r in conn.execute("SELECT version FROM schema_version")}


def migrate(
    conn: sqlite3.Connection, migrations_dir: pathlib.Path | None = None
) -> list[str]:
    """Apply every unapplied migration in numeric order. Idempotent and atomic.

    Each file is applied inside one explicit transaction together with its
    `schema_version` insert, so a migration that fails part-way leaves the
    database untouched and is retried whole on the next run.

    This deliberately does NOT use `sqlite3.Connection.executescript`, which
    issues an implicit COMMIT before it runs. Under `executescript` a migration
    that creates a table and then errors leaves the table committed and the
    version row rolled back — so the next run fails permanently on
    "table already exists" with no path forward but hand-editing the store.
    Splitting the script and driving the transaction by hand is the only way to
    get the property the version table is there to provide.
    """
    migrations_dir = migrations_dir or MIGRATIONS_DIR
    done = _applied(conn)
    applied: list[str] = []

    for sql_file in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
        version = int(sql_file.name[:3])
        if version in done:
            continue

        statements = _split_statements(sql_file.read_text())
        # Bootstrap: `schema_version` is created by 001, so the insert below
        # cannot run until that statement has executed within this transaction.
        conn.execute("BEGIN")
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at, name) VALUES (?,?,?)",
                (version, dt.datetime.now(dt.UTC).isoformat(), sql_file.name),
            )
        except Exception:
            conn.rollback()
            raise
        conn.commit()
        applied.append(sql_file.name)

    return applied


def _split_statements(script: str) -> list[str]:
    """Split a migration into statements on semicolons outside string literals.

    Deliberately small rather than a real SQL parser: these are hand-written
    DDL files in this repo, not arbitrary input. It handles the one case that
    actually occurs — a `;` inside a quoted string — and would need extending
    for triggers or `BEGIN...END` blocks, which no migration here uses.
    """
    statements: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(script):
        ch = script[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                # '' inside a quoted string is an escaped quote, not a close.
                if i + 1 < len(script) and script[i + 1] == quote:
                    buf.append(script[i + 1])
                    i += 2
                    continue
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == "-" and script[i : i + 2] == "--":
            while i < len(script) and script[i] != "\n":
                i += 1
            continue
        elif ch == ";":
            statements.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1

    if "".join(buf).strip():
        statements.append("".join(buf))
    return [s for s in (st.strip() for st in statements) if s]
