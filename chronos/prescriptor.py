#!/usr/bin/env python3
"""
Chronos Prescriptor

Formats intervention results for human consumption and generates
an executive summary of the temporal causal analysis.

Provides:
  - Structured output for the Hermes tool system (JSON)
  - Human-readable report for CLI display
  - Summary generation via LLM
"""

import json
import logging
from typing import Any, Dict, List, Optional

from chronos.causal_analyzer import Intervention
from chronos.simulator import SimulationResult

logger = logging.getLogger(__name__)

_TIME_SENSITIVITY_ORDER = {"immediate": 0, "this_week": 1, "this_month": 2}
_TIME_SENSITIVITY_LABELS = {
    "immediate": "Act TODAY",
    "this_week": "Act this week",
    "this_month": "Act this month",
}
_ACTION_TYPE_EMOJIS = {
    "communicate": "💬",
    "decide": "⚡",
    "invest": "💰",
    "remove": "🗑",
    "delegate": "🤝",
    "measure": "📊",
    "protect": "🛡",
    "accelerate": "🚀",
    "unknown": "🔑",
}


def build_summary(
    goal: str,
    interventions: List[Intervention],
    results: List[SimulationResult],
    prediction_id: str,
    model: Optional[str] = None,
) -> str:
    """Generate a concise executive summary of the analysis."""
    total = len(results)
    success_count = sum(1 for r in results if r.outcome_label == "success")
    failure_count = sum(1 for r in results if r.outcome_label == "failure")
    baseline_rate = success_count / max(total, 1)

    if not interventions:
        return (
            f"Analyzed {total} simulated futures for: '{goal}'. "
            f"Baseline success rate: {baseline_rate:.0%}. "
            "No clear leverage points identified — goal may be underspecified."
        )

    top = interventions[0]
    from agent.auxiliary_client import call_llm
    try:
        response = call_llm(
            task="session_search",
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise executive summaries for temporal causal analyses. "
                        "2-3 sentences max. Be direct and actionable."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Goal: {goal}\n"
                        f"Simulations: {total} total, {success_count} success "
                        f"({baseline_rate:.0%} baseline rate)\n"
                        f"Top intervention: {top.action} "
                        f"(leverage: {top.leverage_score:.2f}, composite: {top.composite_score:.2f})\n"
                        f"Total interventions identified: {len(interventions)}\n\n"
                        "Write a 2-3 sentence executive summary that tells the user "
                        "what matters most and what to do first."
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.debug("Summary LLM call failed: %s", e)
        return (
            f"Analyzed {total} futures for '{goal}' "
            f"(baseline success: {baseline_rate:.0%}). "
            f"Top leverage point: {top.action[:80]}... "
            f"(composite score: {top.composite_score:.2f}). "
            f"Prediction ID: {prediction_id}"
        )


def format_as_json(
    prediction_id: str,
    goal: str,
    interventions: List[Intervention],
    results: List[SimulationResult],
    summary: str,
    horizon_days: int,
) -> Dict[str, Any]:
    """Return structured JSON output for the Hermes tool system."""
    total = len(results)
    success_count = sum(1 for r in results if r.outcome_label == "success")
    failure_count = sum(1 for r in results if r.outcome_label == "failure")

    return {
        "prediction_id": prediction_id,
        "goal": goal,
        "horizon_days": horizon_days,
        "summary": summary,
        "simulation_stats": {
            "total": total,
            "success": success_count,
            "partial": total - success_count - failure_count,
            "failure": failure_count,
            "baseline_success_rate": round(success_count / max(total, 1), 3),
        },
        "interventions": [iv.to_dict() for iv in interventions],
    }


def format_as_text(
    prediction_id: str,
    goal: str,
    interventions: List[Intervention],
    results: List[SimulationResult],
    summary: str,
    horizon_days: int,
) -> str:
    """Return a human-readable report for CLI display."""
    total = len(results)
    success_count = sum(1 for r in results if r.outcome_label == "success")
    failure_count = sum(1 for r in results if r.outcome_label == "failure")
    baseline = success_count / max(total, 1)

    lines = [
        "",
        "=" * 64,
        "  CHRONOS — Temporal Causal Analysis",
        "=" * 64,
        f"  Goal:    {goal[:60]}",
        f"  Horizon: {horizon_days} days",
        f"  ID:      {prediction_id}",
        "-" * 64,
        f"  Simulations: {total}  |  Success: {success_count} ({baseline:.0%})  "
        f"|  Failure: {failure_count}",
        "-" * 64,
        "",
        f"  SUMMARY",
        f"  {summary}",
        "",
        "  LEVERAGE INTERVENTIONS (ranked by composite score)",
        "",
    ]

    # Group by time_sensitivity
    grouped: Dict[str, List[Intervention]] = {}
    for iv in interventions:
        ts = iv.time_sensitivity
        grouped.setdefault(ts, []).append(iv)

    for ts_key in sorted(grouped.keys(), key=lambda k: _TIME_SENSITIVITY_ORDER.get(k, 9)):
        ts_label = _TIME_SENSITIVITY_LABELS.get(ts_key, ts_key.upper())
        lines.append(f"  [{ts_label}]")
        for iv in grouped[ts_key]:
            emoji = _ACTION_TYPE_EMOJIS.get(iv.action_type, "🔑")
            score_bar = _score_bar(iv.composite_score)
            lines.extend([
                f"  {emoji} {iv.action}",
                f"     Score: {score_bar} {iv.composite_score:.2f}  "
                f"(leverage: {iv.leverage_score:.2f} / "
                f"feasibility: {iv.feasibility_score:.2f} / "
                f"reversibility: {iv.reversibility_score:.2f})",
                f"     Why: {iv.rationale[:100]}",
                f"     Prevents: {iv.failure_prevention[:80]}" if iv.failure_prevention else "",
                "",
            ])
        lines.append("")

    lines.extend([
        "-" * 64,
        f"  To track outcome: hermes chronos track {prediction_id} <intervention_id>",
        "=" * 64,
        "",
    ])
    return "\n".join(line for line in lines if line is not None)


def _score_bar(score: float, width: int = 10) -> str:
    """Render a simple ASCII score bar."""
    filled = round(score * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"
