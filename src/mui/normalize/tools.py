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

import hashlib
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


# Directory names that describe a role rather than the operator's work, and
# are therefore safe to keep verbatim. `_is_high_stakes` matches against these,
# so they have to survive normalisation to be useful at all.
_SAFE_DIRS = frozenset(
    {
        "src",
        "tests",
        "test",
        "lib",
        "app",
        "docs",
        "doc",
        "scripts",
        "bin",
        "migrations",
        "config",
        "public",
        "static",
        "assets",
        "components",
        "services",
        "models",
        "views",
        "utils",
        "api",
        "web",
        "server",
        "client",
        "ci",
        "cd",
        "workflows",
        "terraform",
        "k8s",
        "helm",
        "charts",
        "auth",
        "secrets",
        "payments",
        "billing",
        "deploy",
        "release",
        "infra",
        "build",
        "node_modules",
        "vendor",
        ".github",
        ".ssh",
        "dist",
        "hooks",
        "collect",
        "normalize",
        "enrich",
        "analyses",
        "fixtures",
    }
)


def _opaque(text: str) -> str:
    """A short stable digest. Preserves cardinality, reveals nothing.

    `distinct_files` only needs to tell two files apart, never to know what
    either is called.

    Eight hex characters is 2^32. Measured on this corpus there are 1,657
    distinct targets, which puts the expected number of collisions at 0.0003 —
    a collision would merge two files into one and nudge `distinct_files` down
    by one on a single unit, so the consequence is negligible even in the
    unlikely case. The digest is one-way, so the original name is not
    recoverable from the store.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def path_class(path: str) -> str:
    """A path reduced to `<parent>/<opaque><ext>`. Never an identifying name.

    A filename is the operator's WORK CONTENT, not just a location:
    `acme-acquisition-memo.md` and `NDA-project-zeus/plan.md` name a client and
    a deal. So the stem is hashed, and the parent directory is kept only when
    it is a structural name (`src`, `migrations`, `.github`) rather than a
    project or client name.

    This column lands in `store.db`, which is backed up, copied and opened in
    Datasette — so the normalisation happens HERE, at extraction. A value that
    reaches the database has already leaked (invariant 6, PRD §13).

    The extension survives because it is a type, not a name, and
    `_is_high_stakes` matches on it (`.tf`, `.plist`).
    """
    if not path:
        return ""
    p = pathlib.PurePath(path)
    suffix = p.suffix or ""
    stem = _opaque(p.stem) if p.stem else ""
    parent = p.parent.name or ""
    if parent and parent.lower() not in _SAFE_DIRS:
        parent = _opaque(parent)
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
# ~72% of units — the signal stops describing the unit and starts describing
# its length, which `turn_count` already measures. So a unit must be
# debugging-SHAPED: at least this share of its turns has to carry the language.
#
# THIS NUMBER IS A JUDGEMENT CALL, AND IT IS THE WEAKEST PART OF THE SLICE'S
# SCORING. It is stated plainly rather than defended, because W1 gave no
# threshold to inherit — it read the units by hand.
#
# Measured over 2,674 real prompt units, the fire rate moves smoothly with no
# natural breakpoint to discover:
#
#   threshold   debug%   self-correction%
#     any        72.4       69.7
#     0.10       62.8       56.1
#     0.15       51.9       42.1
#     0.20       43.7       33.5
#     0.25       34.3       25.4      <- chosen
#     0.33       22.6       15.9
#     0.40       13.9        9.3
#     0.50       10.2        7.0
#
# 0.25 was chosen because it puts both signals in the same range as the other
# four (subagent use 24.9%, turn count 11.3%, distinct files 9.8%), so no
# single signal dominates the six-signal score. That is a defensible reason,
# not a measured one.
#
# It was NOT chosen to make the score-0 share reproduce W1's 43.4%. It does not
# — the result is 21.8%, and the gap is reported as a finding (`v_caveats`
# row `score_zero_gap`). Choosing this threshold by whether the headline
# reappeared is precisely the failure mode that would fabricate it; the gold
# set (M2-prime, R1) is what replaces this judgement with evidence.
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


# Conventional branch prefixes. Anything else collapses to `other`, for the
# same reason the Bash verb list is an allowlist: a branch name carries ticket
# numbers, client names and descriptive slugs — `fix/superadmin-org-seeds-
# integrations`, `security/issue-2237` — which is work content, not a label.
_BRANCH_KINDS = frozenset({
    "feature", "feat", "fix", "bugfix", "hotfix", "chore", "docs", "doc",
    "refactor", "test", "tests", "perf", "security", "ci", "build", "style",
    "release", "revert", "experiment", "spike", "main", "master", "develop",
    "dev", "staging", "production", "head",
})


def branch_kind(branch: str | None) -> str | None:
    """The KIND of a branch, never its name.

    `feature/issue-14-m1-e2e-slice` -> `feature`; `master` -> `master`;
    anything unconventional -> `other`. Enough to tell release work from
    feature work, which is all any analysis here asks of it.
    """
    if not branch:
        return None
    head = branch.strip().split("/", 1)[0].lower()
    return head if head in _BRANCH_KINDS else "other"
