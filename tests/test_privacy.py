"""Invariant 6 — no prompt content leaves the machine, or reaches the store.

`store.db` is the thing that gets backed up, copied, and opened in Datasette,
so a raw value that reaches the database has already leaked. Normalisation
therefore happens at EXTRACTION, not at display, and these tests pin it there.

Excerpts strip full bash commands (verbs only) and full file paths (PRD §13).
"""

from mui.normalize.tools import (
    command_verb,
    iter_tool_calls,
    normalise_target,
    path_class,
)


def test_bash_stores_the_verb_and_never_the_arguments():
    """A command body can carry secrets, hostnames, ticket numbers and the
    content of the operator's work. Only the verb survives."""
    target = normalise_target("Bash", {"command": "pytest tests/auth --token hunter2"})
    assert target == "pytest"
    assert "hunter2" not in target and "auth" not in target


def test_an_unrecognised_verb_collapses_to_other():
    """The verb list is an ALLOWLIST. A first token outside it is still
    operator-specific — a local script, an internal tool — and this column
    lands in `store.db`, which gets backed up and opened in Datasette."""
    target = normalise_target(
        "Bash", {"command": "psql postgres://user:hunter2@prod/db -c 'select *'"}
    )
    assert target == "other"
    assert "hunter2" not in target and "prod" not in target


def test_bash_verb_strips_a_leading_path():
    assert command_verb("/opt/homebrew/bin/pytest tests/ -k auth") == "pytest"


def test_an_unknown_verb_never_passes_through():
    assert command_verb("x" * 200) == "other"
    assert command_verb("./scripts/deploy-internal-thing.sh") == "other"


def test_file_paths_lose_everything_above_the_parent_directory():
    """`/Users/francis/...` identifies the operator; the signals only need to
    know how many distinct files were touched and roughly where."""
    target = normalise_target(
        "Edit", {"file_path": "/Users/francis/secret/app/auth.py"}
    )
    assert target == "app/auth.py"
    assert "francis" not in target and "/Users" not in target


def test_path_class_is_stable_for_the_distinct_files_signal():
    """Two edits to the same file must normalise identically, or the
    '>=5 distinct files' signal would count one file as several."""
    a = path_class("/a/b/project/src/models.py")
    b = path_class("/a/b/project/src/models.py")
    assert a == b == "src/models.py"


def test_urls_keep_the_host_only():
    """A URL path can carry a query string or an identifier."""
    target = normalise_target(
        "WebFetch", {"url": "https://internal.example.com/tickets/1234?token=abc"}
    )
    assert target == "internal.example.com"
    assert "token" not in target and "1234" not in target


def test_unknown_tools_yield_nothing_rather_than_a_default():
    """Fail closed: a tool this function does not know about contributes no
    target at all, rather than leaking whatever field happened to be present."""
    assert normalise_target("SomeFutureTool", {"secret": "value"}) == ""


def test_tool_use_blocks_are_normalised_on_the_way_out():
    record = {
        "message": {
            "content": [
                {"type": "text", "text": "ignored"},
                {
                    "type": "tool_use",
                    "name": "Bash",
                    "input": {"command": "git push --force origin main"},
                },
            ]
        }
    }
    assert list(iter_tool_calls(record)) == [("Bash", "git")]


def test_records_without_tool_use_yield_nothing():
    assert list(iter_tool_calls({"message": {"content": "plain text"}})) == []
