"""Pure-function tests on the verdict engine — PRD §8.1 and §8.2.

The rules are deterministic and side-effect free, which is why all 28 rows of
the reference report could be verified before the system existed. These tests
cover the whole matrix and every verdict branch, INCLUDING the branches this
slice cannot reach with real data: `verdict.py` is pure, so correctness of the
rules does not depend on what the slice happens to emit.

That matters most for `Underprovisioned`. The slice never produces one (no
`outcome_signal` table, no cohort p75s — PRD §8.3), and since §8.2 makes it
override every other verdict, an untested branch there would mean the one
verdict that protects against the most expensive outcome is also the one
nothing checks.
"""

import pytest

from mui.verdict import (
    ACCEPTABLE,
    ACCEPTABLE_HIGH_STAKES,
    JUSTIFIED,
    OVERPROVISIONED,
    TIER_MATRIX,
    UNDERPROVISIONED,
    decide,
    expected_tier,
)

WORK_TYPES = ("Retrieval", "Synthesis", "Reasoning", "Agentic")
COMPLEXITIES = ("Low", "Medium", "High")
TIERS = ("small", "mid", "frontier")


# --------------------------------------------------------------------------
# §8.1 — expected tier
# --------------------------------------------------------------------------


@pytest.mark.parametrize("work_type", WORK_TYPES)
@pytest.mark.parametrize("complexity", COMPLEXITIES)
def test_matrix_is_total(work_type, complexity):
    """Every cell resolves. A missing cell would be a KeyError at classify
    time, on a row that had already been costed."""
    assert expected_tier(work_type, complexity, "routine") in TIERS


def test_the_two_counter_intuitive_cells():
    """Agentic/Medium and Reasoning/Medium expect `small`, not `mid`.

    These fell out of the reference report rather than from intuition, and they
    are where most of the reclaimable headroom would live if the claim holds —
    medium-complexity agentic execution being mechanical enough for a cheap
    model with good tools. Pinned because an 'obvious' correction to `mid`
    would silently change the headline.
    """
    assert TIER_MATRIX["Agentic"]["Medium"] == "small"
    assert TIER_MATRIX["Reasoning"]["Medium"] == "small"


def test_synthesis_high_is_the_unevidenced_cell():
    """The one cell with no supporting row in the reference report. Set to
    `mid` on reasoning, flagged for calibration — recorded so a future change
    is a decision rather than a drift."""
    assert TIER_MATRIX["Synthesis"]["High"] == "mid"


@pytest.mark.parametrize("work_type", WORK_TYPES)
@pytest.mark.parametrize("complexity", COMPLEXITIES)
def test_high_stakes_bumps_one_tier_and_caps(work_type, complexity):
    routine = expected_tier(work_type, complexity, "routine")
    high = expected_tier(work_type, complexity, "high")
    order = {t: i for i, t in enumerate(TIERS)}
    assert order[high] == min(order["frontier"], order[routine] + 1)


def test_high_stakes_cannot_exceed_frontier():
    assert expected_tier("Agentic", "High", "high") == "frontier"


# --------------------------------------------------------------------------
# §8.2 — the six verdict branches
# --------------------------------------------------------------------------


def test_justified_when_tier_matches():
    v = decide("Agentic", "High", "routine", "frontier")
    assert v.justification == JUSTIFIED
    assert v.tier_delta == 0


def test_overprovisioned_at_delta_two():
    """Opus on work a small model was expected to handle."""
    v = decide("Agentic", "Medium", "routine", "frontier")
    assert v.justification == OVERPROVISIONED
    assert v.tier_delta == 2


def test_overprovisioned_at_delta_one_when_complexity_is_low():
    """+1 is only overprovisioned on Low — the asymmetry is deliberate."""
    v = decide("Retrieval", "Low", "routine", "mid")
    assert v.justification == OVERPROVISIONED
    assert v.tier_delta == 1


def test_acceptable_at_delta_one_above_low():
    v = decide("Retrieval", "High", "routine", "frontier")
    assert v.justification == ACCEPTABLE
    assert v.tier_delta == 1


def test_acceptable_on_successful_downgrade():
    """A below-expected tier on routine work is a downgrade that WORKED —
    `Acceptable`, not a finding. This is a cost lens, not a fit score."""
    v = decide("Agentic", "High", "routine", "mid")
    assert v.justification == ACCEPTABLE
    assert v.tier_delta == -1


def test_acceptable_high_stakes_is_a_risk_flag_not_a_saving():
    """A below-expected tier on work expensive to get wrong. Belongs in a
    review queue, never in a savings ledger."""
    v = decide("Agentic", "High", "high", "mid")
    assert v.justification == ACCEPTABLE_HIGH_STAKES
    assert v.tier_delta < 0


def test_underprovisioned_overrides_everything():
    """Two or more signals ⇒ Underprovisioned, even where the cost lens alone
    would have said Overprovisioned. A cheap model that burns forty minutes of
    engineer time is the most expensive outcome in the table."""
    v = decide("Agentic", "Medium", "routine", "frontier", under_signals=2)
    assert v.justification == UNDERPROVISIONED


def test_one_signal_does_not_trigger_underprovisioned():
    v = decide("Agentic", "Medium", "routine", "frontier", under_signals=1)
    assert v.justification == OVERPROVISIONED


@pytest.mark.parametrize("work_type", WORK_TYPES)
@pytest.mark.parametrize("complexity", COMPLEXITIES)
@pytest.mark.parametrize("stakes", ("routine", "high"))
@pytest.mark.parametrize("used", TIERS)
def test_every_combination_yields_a_valid_verdict(work_type, complexity, stakes, used):
    """The function is total over its whole input space — no combination
    raises, and none falls through to None."""
    v = decide(work_type, complexity, stakes, used)
    assert v.justification in {
        JUSTIFIED,
        ACCEPTABLE,
        ACCEPTABLE_HIGH_STAKES,
        OVERPROVISIONED,
        UNDERPROVISIONED,
    }
    assert -2 <= v.tier_delta <= 2


def test_verdict_is_pure():
    """Same inputs, same output, no accumulated state. This is what makes the
    rules auditable — and it is a property that a database handle in this
    module would quietly destroy."""
    args = ("Agentic", "Medium", "routine", "frontier")
    assert decide(*args) == decide(*args)
