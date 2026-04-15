#!/usr/bin/env python3
"""
Chronos Tool — Hermes Integration

Registers Chronos as a first-class Hermes tool so the agent can use it
during conversations. Two actions:
  - analyze: run full temporal causal analysis
  - track:   record outcome of an intervention (feedback loop)

Tool registration follows the standard registry.register() pattern
used by all other Hermes tools.
"""

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

from tools.registry import registry, tool_error, tool_result


# ------------------------------------------------------------------
# Tool schema
# ------------------------------------------------------------------

CHRONOS_SCHEMA = {
    "name": "chronos",
    "description": (
        "Temporal Causal Engine. Simulates N parallel futures for a goal, "
        "identifies the minimal present-day interventions (leverage points) "
        "that converge the most futures toward success, and prescribes a ranked "
        "action plan. Tracks intervention outcomes for continuous improvement. "
        "Use this tool when you need to: plan strategy under uncertainty, "
        "decide between competing priorities, identify the highest-leverage "
        "action to take today, or understand which decisions have the most "
        "impact on a long-term goal."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["analyze", "track", "history"],
                "description": (
                    "'analyze': run full causal analysis for a goal. "
                    "'track': record the outcome of an applied intervention. "
                    "'history': list recent Chronos predictions."
                ),
            },
            "goal": {
                "type": "string",
                "description": (
                    "[analyze] The desired outcome to simulate toward. "
                    "Be specific: 'Launch mobile app by Q3' is better than 'succeed'."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "[analyze] Background information: team size, constraints, "
                    "current state, domain specifics."
                ),
            },
            "n_simulations": {
                "type": "integer",
                "description": (
                    "[analyze] Number of parallel futures to simulate. "
                    "10-30 for quick analysis, 50-100 for thorough analysis. Default: 30."
                ),
                "default": 30,
            },
            "horizon_days": {
                "type": "integer",
                "description": (
                    "[analyze] Time horizon in days for each simulation. Default: 30."
                ),
                "default": 30,
            },
            "domain": {
                "type": "string",
                "description": (
                    "[analyze] Domain tag for historical leverage lookup. "
                    "E.g. 'product', 'health', 'business', 'personal'. Optional."
                ),
            },
            "preset": {
                "type": "string",
                "enum": ["ultra", "premium", "balanced", "xai", "budget"],
                "description": (
                    "[analyze] Model tier preset (default: premium). "
                    "'ultra': Sonnet sims + Opus analysis — maximum quality, 24 workers. "
                    "'premium': Haiku sims + Opus analysis — best speed/quality ratio, 20 workers. "
                    "'balanced': GPT-4o sims + Opus analysis — cross-provider, 12 workers. "
                    "'xai': full Grok-4 stack — 2M context, 16 workers. "
                    "'budget': Gemini Flash + Haiku — minimal cost."
                ),
            },
            "prediction_id": {
                "type": "string",
                "description": "[track] The prediction ID from a previous analyze call.",
            },
            "intervention_id": {
                "type": "string",
                "description": (
                    "[track] The intervention ID (e.g. 'iv_001') from the prediction."
                ),
            },
            "outcome_text": {
                "type": "string",
                "description": "[track] What actually happened after applying the intervention.",
            },
            "success": {
                "type": "boolean",
                "description": "[track] Whether the intervention led to a positive outcome.",
            },
            "delta_score": {
                "type": "number",
                "description": (
                    "[track] How much better/worse than predicted (−1.0 to +1.0). "
                    "0.0 = exactly as predicted, 1.0 = much better, −1.0 = much worse."
                ),
            },
        },
        "required": ["action"],
    },
}


# ------------------------------------------------------------------
# Handler
# ------------------------------------------------------------------

def handle_chronos(args: Dict[str, Any]) -> str:
    action = args.get("action", "").strip().lower()

    if action == "analyze":
        return _handle_analyze(args)
    elif action == "track":
        return _handle_track(args)
    elif action == "history":
        return _handle_history(args)
    else:
        return tool_error(f"Unknown action: {action}. Use 'analyze', 'track', or 'history'.")


def _handle_analyze(args: Dict[str, Any]) -> str:
    goal = args.get("goal", "").strip()
    if not goal:
        return tool_error("'goal' is required for action='analyze'.")

    context = args.get("context", "")
    n_simulations = int(args.get("n_simulations", 30))
    horizon_days = int(args.get("horizon_days", 30))
    domain = args.get("domain", "")
    preset = args.get("preset", "premium")

    # Clamp to sane range
    n_simulations = max(5, min(n_simulations, 200))
    horizon_days = max(1, min(horizon_days, 365))

    try:
        from chronos.engine import ChronosEngine
        engine = ChronosEngine(preset=preset)

        logger.info("Chronos analyze: goal='%s' n=%d horizon=%d preset=%s",
                    goal[:40], n_simulations, horizon_days, preset)

        output = engine.analyze(
            goal=goal,
            context=context,
            n_simulations=n_simulations,
            horizon_days=horizon_days,
            domain=domain,
            output_format="json",
        )

        # Return structured JSON for the agent to interpret
        return tool_result(output["json_report"])

    except Exception as e:
        logger.exception("Chronos analyze failed: %s", e)
        return tool_error(f"Chronos analysis failed: {type(e).__name__}: {e}")


def _handle_track(args: Dict[str, Any]) -> str:
    prediction_id = args.get("prediction_id", "").strip()
    intervention_id = args.get("intervention_id", "").strip()
    outcome_text = args.get("outcome_text", "").strip()

    if not prediction_id:
        return tool_error("'prediction_id' is required for action='track'.")
    if not intervention_id:
        return tool_error("'intervention_id' is required for action='track'.")
    if not outcome_text:
        return tool_error("'outcome_text' is required for action='track'.")

    success = args.get("success")
    delta_score = args.get("delta_score")

    try:
        from chronos.engine import ChronosEngine
        engine = ChronosEngine()
        outcome_id = engine.record_outcome(
            prediction_id=prediction_id,
            intervention_id=intervention_id,
            outcome_text=outcome_text,
            success=success,
            delta_score=delta_score,
        )
        return tool_result(
            outcome_id=outcome_id,
            prediction_id=prediction_id,
            intervention_id=intervention_id,
            recorded=True,
            message="Outcome recorded. Chronos will use this to improve future predictions.",
        )
    except Exception as e:
        logger.exception("Chronos track failed: %s", e)
        return tool_error(f"Failed to record outcome: {type(e).__name__}: {e}")


def _handle_history(args: Dict[str, Any]) -> str:
    limit = int(args.get("limit", 10))
    try:
        from chronos.engine import ChronosEngine
        engine = ChronosEngine()
        predictions = engine.list_predictions(limit=limit)
        # Return compact summary
        summary = [
            {
                "id": p["id"],
                "goal": p["goal"][:80],
                "created_at": p["created_at"],
                "confidence": p.get("confidence", 0),
                "domain": p.get("domain", ""),
                "n_interventions": len(p.get("interventions", [])),
            }
            for p in predictions
        ]
        return tool_result(predictions=summary, count=len(summary))
    except Exception as e:
        logger.exception("Chronos history failed: %s", e)
        return tool_error(f"Failed to fetch history: {type(e).__name__}: {e}")


def check_chronos_requirements() -> bool:
    """Chronos has no external API key requirements — uses Hermes' LLM setup."""
    try:
        from agent.auxiliary_client import call_llm  # noqa: F401
        return True
    except ImportError:
        return False


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

registry.register(
    name="chronos",
    toolset="chronos",
    schema=CHRONOS_SCHEMA,
    handler=handle_chronos,
    check_fn=check_chronos_requirements,
    is_async=False,
    description=CHRONOS_SCHEMA["description"],
    emoji="⏳",
)
