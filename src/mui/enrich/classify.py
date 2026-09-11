"""Deterministic classification for the slice. No model involved.

Every label here is assigned by RULE, not observed, and every one is
PROVISIONAL (M2-prime, R1). The `provenance` column records that per axis so a
reader can tell a rule-assigned label from an observed one — which matters most
for `work_type`, where the slice's rule collapses almost everything to
`Agentic`. If most notional value lands there, the tier axis carried no
information this round, and `v_work_type_distribution` is how that becomes
visible instead of invisible.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from mui.enrich.signals import SignalResult, to_complexity

CLASSIFIER_VERSION = "provisional-rules-v1"

# PRD §7.2's enum. `other` is always available — a forced choice into a wrong
# label is worse than an honest `other` — and its share is reported, because
# with ai_activity as the reporting top level an over-used `other` degrades the
# whole report rather than one column.
AI_ACTIVITIES = frozenset(
    {
        "debugging",
        "feature-development",
        "testing",
        "refactoring",
        "code-review",
        "architecture-design",
        "security-review",
        "incident-response",
        "data-analysis",
        "pipeline-analysis",
        "automation",
        "documentation",
        "dependency-management",
        "product-planning",
        "requirements-gathering",
        "roadmap-planning",
        "onboarding",
        "research",
        "other",
    }
)

# PRD §7.4's heuristic seeds. Matched against NORMALISED tool targets — verbs
# and directory/extension classes only, never a command body or a full path
# (invariant 6).
HIGH_STAKES_MARKERS = frozenset(
    {
        "deploy",
        "release",
        "terraform",
        "kubectl",
        "helm",
        "argocd",
        "migrations",
        ".tf",
        ".plist",
        "secrets",
        "auth",
        "payments",
        "Dockerfile",
        ".github/workflows",
        "ci",
        "cd",
    }
)


@dataclass(frozen=True)
class Classification:
    ai_activity: str
    work_type: str
    task_complexity: str
    stakes: str
    complexity_score: int
    signals: tuple[str, ...]
    confidence: float
    provenance: dict[str, str]
    rationale: str


def load_activity_map(config_path: Path | None = None) -> dict[str, str]:
    """Anchor-skill -> `ai_activity`, from config rather than code.

    In config because it is a mapping the operator will extend as they add
    routines, and a code edit for that would be friction that quietly grows the
    `other` bucket instead.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parents[3] / "config.toml"
        if not config_path.exists():
            config_path = config_path.with_name("config.toml.example")
    if not config_path.exists():
        return {}
    data = tomllib.loads(config_path.read_text())
    mapping = data.get("ai_activity", {}).get("by_anchor_skill", {})
    return {k: v for k, v in mapping.items() if v in AI_ACTIVITIES}


def classify_arc(
    anchor_skill: str | None,
    signal: SignalResult,
    tool_names: list[str],
    tool_targets: list[str],
    activity_map: dict[str, str],
) -> Classification:
    """Classify one arc. Every axis is rule-assigned; none is observed."""
    activity = activity_map.get(anchor_skill or "", "other")

    # An anchored arc is a routine executing against real state with tools —
    # PRD §7.1's `Agentic`. The slice never assigns `Synthesis` or `Reasoning`:
    # guessing them deterministically would fabricate the axis that drives the
    # tier, which is worse than declaring the axis uninformative.
    work_type = (
        "Agentic"
        if anchor_skill
        else (
            "Agentic"
            if any(t in {"Edit", "Write", "Bash"} for t in tool_names)
            else "Retrieval"
        )
    )

    stakes = "high" if _is_high_stakes(anchor_skill, tool_targets) else "routine"

    return Classification(
        ai_activity=activity,
        work_type=work_type,
        task_complexity=to_complexity(signal.score),
        stakes=stakes,
        complexity_score=signal.score,
        signals=signal.fired,
        # Not a probability. A fixed, deliberately low number recording that
        # this is a rule's output, not a measurement — the gold set (M2') is
        # what would make a real confidence meaningful.
        confidence=0.5,
        provenance={
            "ai_activity": "rule",
            "work_type": "rule",
            "task_complexity": "rule",
            "stakes": "rule",
        },
        rationale=(
            f"provisional: {signal.score}/6 signals "
            f"({', '.join(signal.fired) or 'none'})"
        ),
    )


def _is_high_stakes(anchor_skill: str | None, tool_targets: list[str]) -> bool:
    haystack = " ".join(tool_targets).lower()
    if anchor_skill:
        haystack += " " + anchor_skill.lower()
    return any(marker.lower() in haystack for marker in HIGH_STAKES_MARKERS)


def provenance_json(classification: Classification) -> str:
    return json.dumps(classification.provenance, sort_keys=True)
