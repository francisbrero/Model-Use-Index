"""W1's six complexity signals, as code. Deterministic; no LLM, no Ollama.

These are the signals W1 read by hand over 1,823 Phoenix prompt units, of which
**43.4% of notional list value carried no signal at all** — the finding that
reframed the whole project's headline from "trivial sessions" to
"high-ceremony, low-reasoning orchestration on Opus".

THE THRESHOLDS ARE W1'S AND ARE FIXED. If the 43.4% figure does not reproduce,
that is a finding to report — not a reason to adjust a threshold until it does.
Tuning these until the target falls out would fabricate the headline, and the
number would then be believed. This is the single most likely way this slice
goes wrong, because the pull to "just check the cutoff" is strong and the
result looks like success.

They are calibrated at the PROMPT grain and are meaningless at the arc grain: an
arc runs a median 69 turns past its tag, so ">=40 turns" would fire on almost
every arc. Score prompt units; aggregate to arcs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Signal thresholds — W1's, fixed. See the module docstring before touching.
MIN_DISTINCT_FILES = 5
MIN_TURNS = 40
MIN_TEST_RUNS = 2

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

_TEST_VERBS = frozenset({"pytest", "test", "jest", "vitest", "go", "cargo", "npm"})
_WRITE_TOOLS = frozenset({"Edit", "Write", "NotebookEdit", "MultiEdit"})
_SUBAGENT_TOOLS = frozenset({"Task", "Agent"})


@dataclass
class SignalInput:
    """Everything the six signals read. Assembled in `normalize/`, so the
    signals themselves stay pure and unit-testable."""

    turns: int = 0
    distinct_files: int = 0
    tool_names: list[str] = field(default_factory=list)
    tool_targets: list[str] = field(default_factory=list)
    text: str = ""


@dataclass(frozen=True)
class SignalResult:
    fired: tuple[str, ...]
    score: int

    @property
    def is_score_zero(self) -> bool:
        return self.score == 0


def evaluate(data: SignalInput) -> SignalResult:
    """Score one prompt unit 0-6. Each signal fires at most once."""
    fired: list[str] = []

    if data.distinct_files >= MIN_DISTINCT_FILES:
        fired.append("distinct_files")

    if data.turns >= MIN_TURNS:
        fired.append("turn_count")

    if _DEBUG_LANGUAGE.search(data.text):
        fired.append("debugging_language")

    if _SELF_CORRECTION.search(data.text):
        fired.append("self_correction")

    if any(name in _SUBAGENT_TOOLS for name in data.tool_names):
        fired.append("subagent_use")

    test_runs = sum(1 for verb in data.tool_targets if verb in _TEST_VERBS)
    if test_runs >= MIN_TEST_RUNS:
        fired.append("repeated_test_runs")

    return SignalResult(tuple(fired), len(fired))


def to_complexity(score: int) -> str:
    """Bucket the 0-6 score into PRD §7.3's three values.

    Three, not ten: small models are meaningfully worse at ordinal regression
    than categorical labelling, and a finer scale invites false precision. The
    bucketing is part of `rules_version` — change it and every verdict changes.
    """
    if score == 0:
        return "Low"
    if score <= 2:
        return "Medium"
    return "High"


def has_write_tools(tool_names: list[str]) -> bool:
    return any(name in _WRITE_TOOLS for name in tool_names)
