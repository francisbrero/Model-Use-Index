"""Score prompt units, aggregate to arcs, classify, and write verdicts.

The two-grain flow, which exists because of a measured mismatch: W1's six
signals were calibrated on 1,823 prompt-grain units, and an arc runs a median
69 turns past its tag. Applying prompt thresholds directly to arcs would fire
">=40 turns" on nearly every one and collapse the score-0 share to zero.

So: signals score PROMPT units, arcs AGGREGATE from them, verdicts attach to
ARCS. Cost lives only on arcs.
"""

from __future__ import annotations

import json
import sqlite3

from mui.enrich.classify import (
    CLASSIFIER_VERSION,
    classify_arc,
    load_activity_map,
    provenance_json,
)
from mui.enrich.signals import SignalInput, SignalResult, evaluate
from mui.verdict import TIER_ORDINAL, decide

RULES_VERSION = "provisional-rules-v1"


def enrich(conn: sqlite3.Connection, activity_map: dict | None = None) -> dict:
    """Classify every work unit and write its verdict. Idempotent."""
    activity_map = activity_map if activity_map is not None else load_activity_map()
    stats = {"prompt_units": 0, "work_units": 0, "score_zero": 0}

    prompt_signals = _score_prompt_units(conn, stats)

    with conn:
        conn.execute("DELETE FROM verdict")
        conn.execute("DELETE FROM classification")

        for prompt_id, (signal, _) in prompt_signals.items():
            conn.execute(
                "INSERT INTO classification (unit_id, unit_grain, "
                "classifier_version, ai_activity, work_type, provenance, "
                "task_complexity, stakes, complexity_score, signals, "
                "confidence, rationale, classified_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
                (
                    prompt_id,
                    "prompt_unit",
                    CLASSIFIER_VERSION,
                    "other",
                    "Agentic",
                    json.dumps({"work_type": "rule"}),
                    _complexity(signal.score),
                    "routine",
                    signal.score,
                    json.dumps(list(signal.fired)),
                    0.5,
                    f"provisional: {signal.score}/6 signals",
                ),
            )

        for row in conn.execute(
            "SELECT id, anchor_skill, kind FROM work_unit"
        ).fetchall():
            _enrich_work_unit(conn, row, prompt_signals, activity_map, stats)

    return stats


def _complexity(score: int) -> str:
    from mui.enrich.signals import to_complexity

    return to_complexity(score)


def _score_prompt_units(conn, stats) -> dict:
    """Evaluate the six signals over each prompt unit."""
    results = {}
    rows = conn.execute(
        "SELECT id, turns, session_id, start_turn, end_turn FROM prompt_unit"
    ).fetchall()

    for row in rows:
        tools = conn.execute(
            "SELECT tool_name, target FROM tool_call WHERE prompt_unit_id = ?",
            (row["id"],),
        ).fetchall()
        text = " ".join(t["target"] or "" for t in tools)
        targets = [t["target"] for t in tools if t["target"]]
        names = [t["tool_name"] for t in tools]
        distinct_files = len({t for t in targets if "/" in t or "." in t})

        signal = evaluate(
            SignalInput(
                turns=row["turns"],
                distinct_files=distinct_files,
                tool_names=names,
                tool_targets=targets,
                text=text,
            )
        )
        results[row["id"]] = (signal, row)
        stats["prompt_units"] += 1
        if signal.is_score_zero:
            stats["score_zero"] += 1

    return results


def _enrich_work_unit(conn, row, prompt_signals, activity_map, stats) -> None:
    """An arc's complexity AGGREGATES its prompt units — it is not a re-run of
    prompt thresholds over the whole arc."""
    prompt_rows = conn.execute(
        "SELECT id FROM prompt_unit WHERE work_unit_id = ?", (row["id"],)
    ).fetchall()

    scores = [
        prompt_signals[p["id"]][0] for p in prompt_rows if p["id"] in prompt_signals
    ]
    fired: set[str] = set()
    for signal in scores:
        fired.update(signal.fired)
    aggregate = SignalResult(tuple(sorted(fired)), len(fired))

    tools = conn.execute(
        "SELECT tool_name, target FROM tool_call WHERE work_unit_id = ?",
        (row["id"],),
    ).fetchall()

    classification = classify_arc(
        row["anchor_skill"],
        aggregate,
        [t["tool_name"] for t in tools],
        [t["target"] for t in tools if t["target"]],
        activity_map,
    )

    conn.execute(
        "INSERT INTO classification (unit_id, unit_grain, classifier_version, "
        "ai_activity, work_type, provenance, task_complexity, stakes, "
        "complexity_score, signals, confidence, rationale, classified_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
        (
            row["id"],
            "work_unit",
            CLASSIFIER_VERSION,
            classification.ai_activity,
            classification.work_type,
            provenance_json(classification),
            classification.task_complexity,
            classification.stakes,
            classification.complexity_score,
            json.dumps(list(classification.signals)),
            classification.confidence,
            classification.rationale,
        ),
    )

    used, maximum, pool = _arc_tier(conn, row["id"])
    if used is None:
        return

    verdict = decide(
        classification.work_type,
        classification.task_complexity,
        classification.stakes,
        used,
        # Always 0 in this slice: no outcome_signal table, no cohort p75s
        # (PRD §8.3). `Underprovisioned` is therefore unreachable BY
        # CONSTRUCTION, which biases every number toward over-provisioned.
        under_signals=0,
    )

    conn.execute(
        "INSERT INTO verdict (work_unit_id, rules_version, justification, "
        "expected_tier, used_tier, max_tier, tier_delta, evidence, "
        "allowance_pool) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            row["id"],
            RULES_VERSION,
            verdict.justification,
            verdict.expected_tier,
            verdict.used_tier,
            maximum,
            verdict.tier_delta,
            json.dumps(
                {
                    "signals": list(classification.signals),
                    "score": classification.complexity_score,
                    "underprovisioned_unreachable": True,
                }
            ),
            pool,
        ),
    )
    stats["work_units"] += 1


def _arc_tier(conn, work_unit_id):
    """`used_tier` is the tier carrying the PLURALITY OF NOTIONAL LIST VALUE.

    Not the max (one Opus call would outvote forty Haiku ones) and not the
    modal call (forty cheap subagent calls would outvote the Opus work that
    carries the value). `max_tier` is returned alongside so mixed arcs stay
    visible rather than being flattened away.

    Non-billable models (`<synthetic>`, i.e. rate-limit and error records) are
    excluded from the vote: they carry no tokens, and they have no ordinal.
    """
    rows = conn.execute(
        "SELECT a.model_tier, a.allowance_pool, "
        "       SUM(a.notional_list_value_usd) AS value, COUNT(*) AS calls "
        "FROM api_call a "
        "JOIN model_registry m ON a.model = m.model_pattern OR "
        "     a.model GLOB m.model_pattern "
        "WHERE a.work_unit_id = ? AND m.is_billable = 1 "
        "GROUP BY a.model_tier, a.allowance_pool",
        (work_unit_id,),
    ).fetchall()

    if not rows:
        return None, None, None

    best = max(rows, key=lambda r: (r["value"], r["calls"]))
    tiers = [r["model_tier"] for r in rows if r["model_tier"] in TIER_ORDINAL]
    maximum = max(tiers, key=lambda t: TIER_ORDINAL[t]) if tiers else None
    return best["model_tier"], maximum, best["allowance_pool"]
