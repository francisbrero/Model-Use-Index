"""W1's six complexity signals, and the grain they are valid at.

The thresholds here are W1's and are FIXED. These tests exist partly to make a
silent retune visible: if someone adjusts a cutoff until the 43.4% target falls
out, a test fails rather than the headline quietly changing.
"""

import pytest

from mui.enrich.classify import _is_high_stakes
from mui.enrich.signals import (
    MIN_DISTINCT_FILES,
    MIN_TURNS,
    SignalInput,
    evaluate,
    to_complexity,
)
from mui.normalize.tools import (
    LANGUAGE_SHARE_THRESHOLD,
    language_flags,
    language_shares,
)


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


def test_the_language_share_threshold_is_pinned():
    """0.25, and it is a JUDGEMENT CALL rather than a measured breakpoint.

    W1 read its units by hand and left no threshold to inherit. Over 2,674 real
    prompt units the fire rate moves smoothly from 72% (any turn) to 7% (half
    the turns) with nothing to discover in between.

    0.25 puts both language signals in the same range as the other four
    (subagent use 24.9%, turn count 11.3%, distinct files 9.8%) so that no one
    signal dominates the score. Pinned here so that moving it is a visible,
    reviewed change — the standing risk on this slice is somebody nudging a
    cutoff until W1's 43.4% reappears, which would fabricate the headline.
    """
    assert LANGUAGE_SHARE_THRESHOLD == 0.25


def test_a_unit_is_scored_by_shape_not_by_length():
    """One debugging turn in twenty does not make a debugging unit.

    The existential form ("did any turn match") fires on 72% of real units,
    because units are long — so it measures length, and `turn_count` is already
    a separate signal. Two signals counting the same property would double-count
    it under different names.
    """
    one_in_twenty = ["the build failed"] + ["routine progress"] * 19
    debug_share, _ = language_shares(one_in_twenty)
    assert debug_share < LANGUAGE_SHARE_THRESHOLD

    half = ["the build failed"] * 10 + ["routine progress"] * 10
    debug_share, _ = language_shares(half)
    assert debug_share >= LANGUAGE_SHARE_THRESHOLD


def test_language_shares_ignores_empty_turns():
    """A tool-only turn has no prose and must not dilute the denominator."""
    assert language_shares(["the build failed", "", "   "])[0] == 1.0


def test_language_shares_of_nothing_is_zero_not_an_error():
    assert language_shares([]) == (0.0, 0.0)


def test_high_stakes_matches_path_segments_not_substrings():
    """`ci` must not fire on `src/precision.py`.

    Over-firing here is not harmless: `stakes == high` bumps the expected tier
    (PRD §8.1), which SUPPRESSES `Overprovisioned`. A sloppy match quietly
    shrinks the headline rather than loudly breaking something.
    """
    assert not _is_high_stakes(None, ["src/precision.py"])
    assert not _is_high_stakes(None, ["docs/specific.md"])
    assert not _is_high_stakes(None, ["src/models.py"])


def test_high_stakes_fires_on_real_infrastructure():
    """PRD §7.4's seeds: deploy scripts, CI/CD, migrations, infra."""
    assert _is_high_stakes(None, ["migrations/001.sql"])
    assert _is_high_stakes(None, ["infra/main.tf"])
    assert _is_high_stakes(None, ["workflows/deploy.yml"])
    assert _is_high_stakes(None, ["scripts/deploy.sh"])


def test_high_stakes_reads_the_anchor_skill_by_segment():
    assert _is_high_stakes("release-prod", [])
    assert not _is_high_stakes("fix-issue", [])
