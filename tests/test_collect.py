"""Golden-file tests for the collector and the schema.

The collector's contract is narrow and load-bearing: capture everything, parse
nothing (invariant 2), lose nothing (invariant 2b). Each test below pins one of
the specific ways that contract has been broken before or could be broken by a
reasonable-looking edit.

Fixtures are hand-written and obviously synthetic (invariant 6). No real
transcript is committed.
"""

import json
import pathlib
import sqlite3

import pytest

from mui.collect.transcript import backfill, backfill_file, iter_events
from mui.db import connect, migrate

SESSION = "SYNTH-collect"


def _record(**overrides):
    base = {
        "type": "assistant",
        "sessionId": SESSION,
        "uuid": "u-1",
        "requestId": "req-1",
        "timestamp": "2026-01-01T00:00:00.000Z",
        "message": {
            "id": "msg-1",
            "model": "claude-opus-5",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "cache_creation_input_tokens": 30,
                "cache_read_input_tokens": 40,
            },
        },
    }
    base.update(overrides)
    return base


@pytest.fixture
def store(tmp_path):
    conn = connect(tmp_path / "store.db")
    migrate(conn)
    return conn


@pytest.fixture
def transcript(tmp_path):
    def _write(records):
        path = tmp_path / f"{SESSION}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return path

    return _write


def test_backfill_is_idempotent(store, transcript):
    path = transcript([_record(), _record(uuid="u-2")])
    first = backfill_file(store, path)
    second = backfill_file(store, path)
    assert first.inserted == 2
    assert second.inserted == 0, "re-running backfill must insert nothing new"
    assert second.duplicates == 2


def test_identical_lines_are_both_kept(store, transcript):
    """`raw_event` is append-only and never loses a record (invariant 2b).

    Measured on real history: 9.8% of lines are byte-identical to an earlier
    line in the same file — repeated tool results, identical short prompts,
    retried calls. Hashing the line body alone would silently collapse every
    one of them, deleting a tenth of the capture while the store still looked
    healthy. This is the subtlest available way to break the project.
    """
    identical = _record()
    path = transcript([identical, identical])
    stats = backfill_file(store, path)
    assert stats.inserted == 2, "identical lines are distinct records, not dupes"

    stored = store.execute("SELECT COUNT(*) FROM raw_event").fetchone()[0]
    assert stored == 2


def test_appending_to_a_transcript_only_ingests_the_tail(store, tmp_path):
    """Transcripts grow constantly. Re-reading a grown file must re-derive the
    same hash for everything already stored, or every backfill would duplicate
    the whole history."""
    path = tmp_path / f"{SESSION}.jsonl"
    path.write_text(json.dumps(_record()) + "\n")
    assert backfill_file(store, path).inserted == 1

    with path.open("a") as handle:
        handle.write(json.dumps(_record(uuid="u-2")) + "\n")
    second = backfill_file(store, path)
    assert second.inserted == 1, "only the appended line is new"
    assert second.duplicates == 1


def test_zero_usage_synthetic_records_are_kept(store, transcript):
    """A rate-limit hit is an `assistant` record with model `<synthetic>`,
    all-zero usage, `error: rate_limit` and `apiErrorStatus: 429`.

    It is the ONLY on-disk evidence of an allowance boundary (invariant 10b).
    A reasonable-looking "skip records with no tokens" filter in `collect/`
    would delete the entire allowance-calibration signal, which is why the
    collector is forbidden from interpreting anything at all.
    """
    limit_hit = _record(
        uuid="u-limit",
        error="rate_limit",
        apiErrorStatus=429,
        message={
            "id": "msg-limit",
            "model": "<synthetic>",
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    )
    backfill_file(store, transcript([limit_hit]))
    payload = store.execute("SELECT payload FROM raw_event").fetchone()[0]
    assert json.loads(payload)["error"] == "rate_limit"


def test_unparseable_lines_are_still_stored(store, tmp_path):
    """A line we cannot read today may be readable once `normalize/` learns the
    new shape. Dropping it would make the drift unrecoverable."""
    path = tmp_path / f"{SESSION}.jsonl"
    path.write_text('{"broken": \n' + json.dumps(_record()) + "\n")
    stats = backfill_file(store, path)
    assert stats.unparseable == 1
    assert stats.inserted == 2, "the malformed line is captured too"


def test_session_id_falls_back_to_the_filename(store, tmp_path):
    """`file-history-snapshot` records carry neither `sessionId` nor
    `session_id`. The file stem IS the session id."""
    path = tmp_path / "SYNTH-fallback.jsonl"
    path.write_text(json.dumps({"type": "file-history-snapshot"}) + "\n")
    backfill_file(store, path)
    session = store.execute("SELECT session_id FROM raw_event").fetchone()[0]
    assert session == "SYNTH-fallback"


def test_snake_case_session_id_is_read(tmp_path):
    """Some record types carry only `session_id`."""
    path = tmp_path / "other.jsonl"
    path.write_text(json.dumps({"type": "system", "session_id": SESSION}) + "\n")
    assert next(iter_events(path))[0] == SESSION


def test_a_vanishing_transcript_does_not_crash_the_walk(store, tmp_path):
    """The corpus is LIVE: Claude Code creates and removes transcripts while
    the walk runs. The observer must never fail because the observed system
    did something normal (invariant 1)."""
    (tmp_path / "gone.jsonl").write_text(json.dumps(_record()) + "\n")
    missing = tmp_path / "never-existed.jsonl"
    assert list(iter_events(missing)) == []


def test_backfill_walks_nested_project_directories(store, tmp_path):
    nested = tmp_path / "-Users-x-Project" / "subagents"
    nested.mkdir(parents=True)
    (nested / "agent-1.jsonl").write_text(json.dumps(_record()) + "\n")
    stats = backfill(store, tmp_path)
    assert stats.files == 1 and stats.inserted == 1


def test_raw_event_stores_the_payload_verbatim(store, transcript):
    """The collector appends the line as-is. If it ever reformats, normalises
    or re-serialises, it has started interpreting (invariant 2)."""
    record = _record()
    path = transcript([record])
    backfill_file(store, path)
    payload = store.execute("SELECT payload FROM raw_event").fetchone()[0]
    assert payload == json.dumps(record)


def test_migrations_are_idempotent(tmp_path):
    conn = connect(tmp_path / "m.db")
    assert migrate(conn), "first run applies migrations"
    assert migrate(conn) == [], "second run applies nothing"


def test_failed_migration_leaves_no_trace(tmp_path):
    """`executescript` would commit the DDL and roll back only the version row,
    wedging the store permanently on the next run. Statements are executed
    individually inside an explicit transaction so a bad migration is a no-op
    that can simply be fixed and re-run."""
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    src = pathlib.Path(__file__).resolve().parents[1] / "migrations"
    (migrations / "001_init.sql").write_text((src / "001_init.sql").read_text())

    conn = connect(tmp_path / "f.db")
    migrate(conn, migrations)

    (migrations / "009_bad.sql").write_text(
        "CREATE TABLE leaked(a);\nSELECT * FROM no_such_table;"
    )
    with pytest.raises(sqlite3.OperationalError):
        migrate(conn, migrations)

    leaked = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='leaked'"
    ).fetchone()[0]
    assert leaked == 0, "a failed migration must leave nothing behind"

    (migrations / "009_bad.sql").write_text("CREATE TABLE fixed(a);")
    assert migrate(conn, migrations) == ["009_bad.sql"], "and must retry cleanly"
