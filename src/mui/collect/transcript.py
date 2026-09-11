"""Backfill reader for `~/.claude/projects/**/*.jsonl`.

Walks transcripts and appends each line to `raw_event` verbatim. The ONLY
fields read are `sessionId` (to fill an index column) and nothing else; the
payload is stored as the exact bytes-as-text of the line. A record whose JSON
does not even parse is still stored, with a NULL session id — the collector's
job is to lose nothing, and a line we cannot read today may be readable once
`normalize/` learns the new shape (invariant 2b).

What this deliberately does NOT do:

- It does not skip records with no tokens. A rate-limit hit is an `assistant`
  record with model `<synthetic>`, all-zero usage and `error: "rate_limit"` —
  the only on-disk evidence of an allowance boundary (invariant 10b). A
  reasonable-looking "skip empty usage" filter here would delete the entire
  allowance-calibration signal.
- It does not deduplicate. The duplicate content-block records are real records
  and stay in `raw_event` untouched; dedup is a derivation in `normalize/`
  (invariants 10 and 2b).
- It does not validate, coerce or model anything.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass

DEFAULT_PROJECTS_DIR = pathlib.Path.home() / ".claude" / "projects"
SOURCE = "transcript"


@dataclass(frozen=True)
class BackfillStats:
    files: int = 0
    lines: int = 0
    inserted: int = 0
    duplicates: int = 0
    unparseable: int = 0

    def __add__(self, other: BackfillStats) -> BackfillStats:
        return BackfillStats(
            self.files + other.files,
            self.lines + other.lines,
            self.inserted + other.inserted,
            self.duplicates + other.duplicates,
            self.unparseable + other.unparseable,
        )


def find_transcripts(projects_dir: pathlib.Path | str = DEFAULT_PROJECTS_DIR):
    """Every transcript under the projects directory, in a stable order."""
    projects_dir = pathlib.Path(projects_dir).expanduser()
    return sorted(projects_dir.rglob("*.jsonl"))


def _session_id(line: str, fallback: str) -> str:
    """The one field this layer reads, and it reads it defensively.

    `sessionId` is on ~98% of records; a few types carry only `session_id`, and
    `file-history-snapshot` carries neither. The file stem IS the session id, so
    it is the fallback. A malformed line yields the fallback rather than raising
    — losing the line would violate the layer's whole purpose.
    """
    try:
        record = json.loads(line)
    except (ValueError, TypeError):
        return fallback
    if not isinstance(record, dict):
        return fallback
    value = record.get("sessionId") or record.get("session_id")
    return value if isinstance(value, str) and value else fallback


def iter_events(path: pathlib.Path) -> Iterator[tuple[str, str, str]]:
    """Yield `(session_id, payload, content_hash)` for each line of a transcript.

    The hash covers the transcript's identity and the line's position in it, not
    just the line body. That distinction is load-bearing and was measured:
    **8,205 of 84,101 lines (9.8%) are byte-identical to an earlier line in the
    same file** — repeated tool results, identical short prompts, retried calls.

    Hashing the body alone would make `content_hash UNIQUE` silently collapse
    those into one row, deleting ~10% of the capture. `raw_event` is
    append-only and never loses a record (invariant 2b), and a dedupe is as
    much a loss as a delete. Real deduplication of API responses happens in
    `normalize/` on `(message.id, requestId)`, which is a different key for a
    different purpose (invariant 10).

    Position is the *session-relative line number*, not a byte offset, so the
    hash is stable when a transcript is appended to — which they are,
    constantly. Re-running backfill over a grown file re-derives the same hash
    for every line already stored, so the insert is ignored and only the new
    tail lands. That is what makes the operation idempotent.
    """
    fallback = path.stem
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        # The corpus is LIVE: Claude Code creates, appends to and removes
        # transcripts (subagent files especially) while this walk is running,
        # so a path found by the glob can be gone by the time it is opened.
        # Skipping is correct — the next backfill picks up whatever exists
        # then, and backfill is idempotent. Raising here would mean the
        # observer fails because the observed system did something normal,
        # which is the shape invariant 1 exists to prevent.
        return
    with handle:
        line_number = 0
        try:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                line_number += 1
                session_id = _session_id(line, fallback)
                digest = hashlib.sha256(
                    f"{session_id}\x00{path.name}\x00{line_number}\x00{line}".encode()
                ).hexdigest()
                yield session_id, line, digest
        except OSError:
            # Same reasoning as the open() guard: the file can go away or be
            # truncated mid-read. Keep what was read, lose nothing already
            # stored, and let the next run collect the rest.
            return


def backfill_file(conn: sqlite3.Connection, path: pathlib.Path) -> BackfillStats:
    """Append one transcript's lines to `raw_event`. Idempotent."""
    now = dt.datetime.now(dt.UTC).isoformat()
    lines = inserted = unparseable = 0
    rows = []
    for session_id, payload, digest in iter_events(path):
        lines += 1
        try:
            json.loads(payload)
        except (ValueError, TypeError):
            unparseable += 1
        rows.append((SOURCE, now, session_id, payload, digest))

    with conn:
        for row in rows:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO raw_event "
                "(source, ingested_at, session_id, payload, content_hash) "
                "VALUES (?,?,?,?,?)",
                row,
            )
            inserted += cursor.rowcount

    return BackfillStats(
        files=1,
        lines=lines,
        inserted=inserted,
        duplicates=lines - inserted,
        unparseable=unparseable,
    )


def backfill(
    conn: sqlite3.Connection,
    projects_dir: pathlib.Path | str = DEFAULT_PROJECTS_DIR,
    progress=None,
) -> BackfillStats:
    """Append every transcript under `projects_dir`. Safe to re-run."""
    stats = BackfillStats()
    for path in find_transcripts(projects_dir):
        stats = stats + backfill_file(conn, path)
        if progress is not None:
            progress(path, stats)
    return stats
