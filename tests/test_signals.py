"""W1's six complexity signals, and the grain they are valid at.

The thresholds here are W1's and are FIXED. These tests exist partly to make a
silent retune visible: if someone adjusts a cutoff until the 43.4% target falls
out, a test fails rather than the headline quietly changing.
"""

import pytest

from mui.enrich.signals import (
    MIN_DISTINCT_FILES,
    MIN_TURNS,
    SignalInput,
    evaluate,
    to_complexity,
)
from mui.normalize.tools import language_flags


def test_no_signals_is_score_zero():
    """The 43.4% finding is about exactly this state: real Opus spend on work
    showing no complexity signal at all."""
    result = evaluate(SignalInput(turns=3, distinct_files=1))
    assert result.score == 0
    assert result.is_score_zero
    assert result.fired == ()


def test_thresholds_are_w1s_and_pinned():
    """Pinned deliberately. Re-tuning these until a target reproduces would
    fabricate the headline, and the number would then be believed."""
    assert MIN_DISTINCT_FILES == 5
    assert MIN_TURNS == 40


def test_distinct_files_fires_at_the_threshold_not_above_it():
    assert "distinct_files" in evaluate(SignalInput(distinct_files=5)).fired
    assert "distinct_files" not in evaluate(SignalInput(distinct_files=4)).fired


def test_turn_count_fires_at_the_threshold():
    assert "turn_count" in evaluate(SignalInput(turns=40)).fired
    assert "turn_count" not in evaluate(SignalInput(turns=39)).fired


@pytest.mark.parametrize(
    "text", ["the test failed", "traceback in prod", "why doesn't this work"]
)
def test_debugging_vocabulary_is_detected(text):
    """The reduction runs in `normalize/`, over prose that is then discarded —
    the prompt text must never reach `enrich/` or the store (invariant 6)."""
    debug, _ = language_flags(text)
    assert debug


@pytest.mark.parametrize("text", ["actually, let me fix that", "wait, that's wrong"])
def test_self_correction_vocabulary_is_detected(text):
    _, correction = language_flags(text)
    assert correction


def test_plain_text_triggers_neither_flag():
    assert language_flags("add a column to the report") == (False, False)


def test_language_flags_retain_nothing():
    """Two booleans out, and no way back to the text. That is what makes it
    safe to compute these over real prompt content at all."""
    result = language_flags("the traceback shows a bug in the payment path")
    assert result == (True, False)
    assert all(isinstance(flag, bool) for flag in result)


def test_tool_targets_alone_cannot_fire_the_language_signals():
    """The bug this interface change fixes.

    The signals were previously fed the concatenation of NORMALISED TOOL
    TARGETS — verbs and `dir/stem.ext` path classes — against which W1's prose
    regexes essentially never matched. Both signals were dead in production
    while their unit tests passed, because the tests fed prose the pipeline
    never supplied. That inflated the score-0 share, which IS the 43.4%
    headline, in the flattering direction.
    """
    targets = "pytest git src/models.py app/auth.py example.com"
    assert language_flags(targets) == (False, False)

    result = evaluate(SignalInput(tool_targets=targets.split()))
    assert "debugging_language" not in result.fired
    assert "self_correction" not in result.fired


def test_the_language_signals_fire_when_normalize_says_so():
    result = evaluate(SignalInput(has_debug_language=True, has_self_correction=True))
    assert "debugging_language" in result.fired
    assert "self_correction" in result.fired


def test_subagent_use_fires():
    assert "subagent_use" in evaluate(SignalInput(tool_names=["Task"])).fired


def test_repeated_test_runs_needs_more_than_one():
    once = evaluate(SignalInput(tool_targets=["pytest"]))
    twice = evaluate(SignalInput(tool_targets=["pytest", "pytest"]))
    assert "repeated_test_runs" not in once.fired
    assert "repeated_test_runs" in twice.fired


def test_each_signal_fires_at_most_once():
    """Six signals, so the score is bounded at 6 — a unit that edits 40 files
    does not score 40."""
    result = evaluate(
        SignalInput(
            turns=500,
            distinct_files=50,
            tool_names=["Task", "Task"],
            tool_targets=["pytest"] * 10,
            has_debug_language=True,
            has_self_correction=True,
        )
    )
    assert result.score == 6
    assert len(result.fired) == len(set(result.fired))


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0, "Low"), (1, "Medium"), (2, "Medium"), (3, "High"), (6, "High")],
)
def test_complexity_bucketing(score, expected):
    """PRD §7.3 — three buckets, not ten. Part of `rules_version`: change this
    and every verdict changes."""
    assert to_complexity(score) == expected
