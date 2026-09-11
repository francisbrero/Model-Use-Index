"""Extract tool calls, with targets normalised on the way in.

`target` is NEVER stored raw. Invariant 6 and G4: no prompt content leaves the
machine, and a full bash command or absolute path is prompt content. A Bash
call stores its command VERB only (`pytest`, `git`, `npm`); a file path is
reduced to a repo-relative directory plus an extension class.

The normalisation happens here, at extraction, rather than at display — a raw
value that reaches the database has already leaked, because `store.db` is the
thing that gets backed up, copied and opened in Datasette.
"""

from __future__ import annotations

import pathlib
from typing import Any

# Verbs worth keeping whole; everything else collapses to its first token.
_KNOWN_VERBS = frozenset(
    {
        "pytest",
        "git",
        "npm",
        "npx",
        "uv",
        "pip",
        "python",
        "python3",
        "ruff",
        "make",
        "docker",
        "kubectl",
        "helm",
        "terraform",
        "gh",
        "cargo",
        "go",
        "node",
        "yarn",
        "pnpm",
        "bash",
        "sh",
        "sed",
        "awk",
        "grep",
        "rg",
        "find",
        "cat",
        "ls",
        "mkdir",
        "mv",
        "cp",
        "rm",
        "curl",
        "jq",
        "datasette",
    }
)


def command_verb(command: str) -> str:
    """First token of a command, and nothing else. Never the arguments."""
    if not command:
        return ""
    token = command.strip().split()[0] if command.strip().split() else ""
    token = token.rsplit("/", 1)[-1]
    return token if token in _KNOWN_VERBS else (token[:32] or "")


def path_class(path: str) -> str:
    """A path reduced to `<parent dir>/*<ext>`. Never an absolute path.

    Keeps exactly what the signals need — how many distinct files a unit
    touched, and roughly where — and discards the part that identifies the
    operator's machine and the content of their work.
    """
    if not path:
        return ""
    p = pathlib.PurePath(path)
    parent = p.parent.name or ""
    suffix = p.suffix or ""
    stem = p.stem[:24]
    return f"{parent}/{stem}{suffix}" if parent else f"{stem}{suffix}"


def normalise_target(tool_name: str, tool_input: dict[str, Any]) -> str:
    """The one function that decides what is safe to store."""
    if not isinstance(tool_input, dict):
        return ""

    if tool_name == "Bash":
        return command_verb(str(tool_input.get("command", "")))

    for key in ("file_path", "path", "notebook_path"):
        if key in tool_input:
            return path_class(str(tool_input[key]))

    if tool_name in {"Grep", "Glob"}:
        return path_class(str(tool_input.get("path", "")))

    if tool_name in {"WebFetch", "WebSearch"}:
        url = str(tool_input.get("url", ""))
        # Host only — a URL path can carry a query or an identifier.
        if "//" in url:
            return url.split("//", 1)[1].split("/", 1)[0][:64]
        return ""

    return ""


def iter_tool_calls(record: dict[str, Any]):
    """Yield `(tool_name, target)` for each `tool_use` block of a record."""
    message = record.get("message") or {}
    content = message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name") or ""
        yield name, normalise_target(name, block.get("input") or {})
