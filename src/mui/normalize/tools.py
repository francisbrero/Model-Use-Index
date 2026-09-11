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
import re
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
    """First token of a command, and nothing else. Never the arguments.

    `_KNOWN_VERBS` is an ALLOWLIST, not a hint: anything outside it collapses
    to `other`. A first token is still operator-specific — a local script name,
    an internal tool, a project alias — and this column ends up in `store.db`,
    which is backed up, copied and opened in Datasette. The signals only need
    to tell test runs from everything else, so an allowlist costs nothing and a
    passthrough would leak by default.
    """
    if not command:
        return ""
    tokens = command.strip().split()
    if not tokens:
        return ""
    token = tokens[0].rsplit("/", 1)[-1]
    return token if token in _KNOWN_VERBS else "other"


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


# ---------------------------------------------------------------------------
# Prose, for the two language signals — and nothing else.
# ---------------------------------------------------------------------------

# W1's debugging and self-correction signals read the PROSE of a unit, not its
# tool calls. Storing that prose verbatim would put prompt content in the
# store, which invariant 6 forbids — `store.db` is the thing that gets backed
# up, copied and opened in Datasette.
#
# So the prose never lands anywhere. Only the boolean OUTCOME of matching these
# vocabularies against it does: two bits per unit, from which no content can be
# reconstructed. This is the narrowest thing that makes the signals real
# without keeping the text.
# W1's regexes, verbatim. They are deliberately NOT loosened into a bag of
# words: a word-set match on "wait", "error" or "wrong" fires on ordinary prose
# and takes these from ~15% of turns to ~83%, which would collapse the score-0
# share just as surely as leaving them dead did. Word boundaries and the
# multi-word forms are the calibration.
_DEBUG_LANGUAGE = re.compile(
    r"\b(?:bug|broken|fail(?:s|ed|ing|ure)?|error|traceback|exception|"
    r"crash(?:ed|ing)?|regress(?:ion)?|root cause|reproduce|debug(?:ging)?|"
    r"stack trace|why (?:is|does|isn't|doesn't))\b",
    re.IGNORECASE,
)

_SELF_CORRECTION = re.compile(
    r"\b(?:actually|wait|i was wrong|that's wrong|my mistake|correction|"
    r"let me fix|on reflection|i mis(?:read|understood|took)|scratch that|"
    r"that didn't work|revert)\b",
    re.IGNORECASE,
)


# A unit spans many turns (median 10, p90 43), and each of W1's regexes fires
# on ~15% of turns in isolation. Asking "did ANY turn match" therefore fires on
# ~78% of units — the signal stops describing the unit and starts describing
# its length. So a unit must be debugging-SHAPED: at least this share of its
# turns has to carry the language.
LANGUAGE_SHARE_THRESHOLD = 0.25


def language_shares(texts: list[str]) -> tuple[float, float]:
    """Share of a unit's turns whose prose carries each vocabulary.

    Proportional rather than existential, because the existential form is a
    proxy for turn count — and `turn_count` is already one of the six signals,
    so the two would double-count the same property under different names.

    Retains nothing: two floats out, no offsets, no matched terms, no excerpt.
    """
    scored = [t for t in texts if t and t.strip()]
    if not scored:
        return 0.0, 0.0
    debug = sum(1 for t in scored if _DEBUG_LANGUAGE.search(t))
    correction = sum(1 for t in scored if _SELF_CORRECTION.search(t))
    return debug / len(scored), correction / len(scored)


def language_flags(text: str) -> tuple[bool, bool]:
    """`(debugging, self_correction)` for one unit's prose.

    Returns two booleans and retains nothing — no offsets, no matched terms, no
    excerpt. The caller must never store the text these were computed from;
    that is the whole reason the reduction happens here rather than in
    `enrich/` (invariant 6).

    Measured over ~11,900 real assistant text blocks, these fire on 16.2% and
    13.7% of them respectively. Both numbers are worth keeping in view: a
    version of this function that fired on 1% would be the dead-signal bug, and
    one that fired on 80% would be the opposite failure — and both move the
    score-0 share, which IS the 43.4% headline.
    """
    if not text:
        return False, False
    return bool(_DEBUG_LANGUAGE.search(text)), bool(_SELF_CORRECTION.search(text))


def record_text(record: dict) -> str:
    """The prose of one record: user prompt text, or assistant text blocks.

    Used ONLY to compute `language_flags` and then discarded — it is never
    returned to a caller that writes to the database.
    """
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return " ".join(parts)
