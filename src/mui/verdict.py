"""The verdict engine — PRD §8. Pure functions, no I/O.

This is the part that **must not be done by a model**. The verdict is a
deterministic, auditable, config-driven function; if it is not reproducible,
nobody will act on it. Purity is what makes every rule unit-testable without a
database, which is how all 28 reference-report rows could be verified before
the system existed.

Keep it pure. A database handle in this module would end that property
silently.
"""

from __future__ import annotations

from dataclasses import dataclass

# PRD §8.2's ordinal scale. Every arithmetic in this module depends on it, which
# is why `model_registry.tier` is CHECK-constrained to exactly these keys.
TIER_ORDINAL = {"small": 0, "mid": 1, "frontier": 2}
ORDINAL_TIER = {v: k for k, v in TIER_ORDINAL.items()}

# PRD §8.1. Reverse-engineered from the reference report, then verified: these
# rules reproduce `model_justification` on all 28 visible rows exactly.
#
# Two cells are counter-intuitive and fell out of the data rather than from
# intuition: Agentic/Medium and Reasoning/Medium both expect `small`. The
# implied claim is that medium-complexity agentic execution is mechanical
# enough for a cheap model with good tools — which, if true, is where most of
# the reclaimable headroom lives, since that is also where the volume sits.
#
# Synthesis/High is the one cell with NO supporting evidence in the reference
# report; no such row appears. Set to `mid` on the reasoning that synthesis is
# bounded judgement, and flagged for calibration.
TIER_MATRIX = {
    "Retrieval": {"Low": "small", "Medium": "small", "High": "mid"},
    "Synthesis": {"Low": "small", "Medium": "mid", "High": "mid"},
    "Agentic": {"Low": "small", "Medium": "small", "High": "frontier"},
    "Reasoning": {"Low": "small", "Medium": "small", "High": "frontier"},
}

JUSTIFIED = "Justified"
ACCEPTABLE = "Acceptable"
ACCEPTABLE_HIGH_STAKES = "Acceptable (high stakes)"
OVERPROVISIONED = "Overprovisioned"
UNDERPROVISIONED = "Underprovisioned"


@dataclass(frozen=True)
class Verdict:
    justification: str
    expected_tier: str
    used_tier: str
    tier_delta: int


def expected_tier(work_type: str, task_complexity: str, stakes: str) -> str:
    """PRD §8.1. `stakes == 'high'` bumps one tier, capped at frontier."""
    tier = TIER_MATRIX[work_type][task_complexity]
    if stakes == "high":
        tier = ORDINAL_TIER[min(TIER_ORDINAL["frontier"], TIER_ORDINAL[tier] + 1)]
    return tier


def decide(
    work_type: str,
    task_complexity: str,
    stakes: str,
    used_tier: str,
    under_signals: int = 0,
) -> Verdict:
    """PRD §8.2. The asymmetry is intentional — this is a cost lens, not a
    symmetric fit score.

    `Justified` means the tier was exactly right. `Acceptable` means no
    overspend, covering both a mild overshoot and a successful downgrade.
    `Overprovisioned` means money was spent that did not need to be. And
    `Underprovisioned` overrides everything, because a cheap model that burns
    forty minutes of engineer time is the most expensive outcome in the table
    and the one a pure cost view never surfaces.

    NOTE FOR THIS SLICE: `under_signals` is always 0, because the slice builds
    no `outcome_signal` table and no cohort p75 thresholds (PRD §8.3). So
    `Underprovisioned` is unreachable here BY CONSTRUCTION, not because it is
    rare — and since it overrides every other verdict, its absence biases every
    number toward over-provisioned. The parameter exists so the rule is
    testable now and correct when the signals land. See `v_caveats`.
    """
    expected = expected_tier(work_type, task_complexity, stakes)
    delta = TIER_ORDINAL[used_tier] - TIER_ORDINAL[expected]

    if under_signals >= 2:
        justification = UNDERPROVISIONED
    elif delta >= 2 or (delta == 1 and task_complexity == "Low"):
        justification = OVERPROVISIONED
    elif delta == 1:
        justification = ACCEPTABLE
    elif delta == 0:
        justification = JUSTIFIED
    elif stakes == "high":
        # Not a cost finding at all — a risk flag. A below-expected tier was
        # used on something expensive to get wrong; it belongs in a review
        # queue, never in a savings ledger.
        justification = ACCEPTABLE_HIGH_STAKES
    else:
        justification = ACCEPTABLE

    return Verdict(justification, expected, used_tier, delta)
