"""
Chronos CLI subcommand for Hermes.

Commands:
    hermes chronos analyze "goal" [--context=...] [--simulations=50] [--horizon=30]
    hermes chronos track <prediction_id> <intervention_id> "outcome description"
    hermes chronos show <prediction_id>
    hermes chronos history [--limit=10]

The CLI provides direct terminal access to the Chronos engine without
needing to go through the agent conversation loop.
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from hermes_cli.colors import Colors, color


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def _get_engine():
    from chronos.engine import ChronosEngine
    return ChronosEngine()


def _print_banner():
    print(color("⏳ CHRONOS — Temporal Causal Engine", Colors.CYAN))
    print(color("   Find the leverage point that changes the future.", Colors.DIM))
    print()


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

def chronos_analyze(
    goal: str,
    context: str = "",
    simulations: int = 30,
    horizon: int = 30,
    domain: str = "",
    preset: str = "balanced",
    json_output: bool = False,
):
    """
    Analyze a goal and prescribe the highest-leverage interventions.

    Usage:
        hermes chronos analyze "Launch mobile app by Q3"
        hermes chronos analyze "Close the Series A" --context="3 months runway" --simulations=50
        hermes chronos analyze "Lose 10kg" --preset=budget --simulations=100
    """
    _print_banner()
    print(color(f"Goal: {goal}", Colors.BOLD))
    print(color(f"Preset: {preset} | {simulations} simulations | {horizon}-day horizon", Colors.DIM))
    print()

    # Show cost estimate before running
    try:
        from chronos.model_tiers import PRESETS, ChronosModelConfig
        if preset in PRESETS:
            cfg = PRESETS[preset]
        else:
            cfg = ChronosModelConfig.resolve()
        est = cfg.estimate_cost(simulations)
        print(color(f"  Estimated cost: {est}", Colors.DIM))
        print(color(f"  {cfg.describe()}", Colors.DIM))
        print()
    except Exception:
        pass

    start = time.time()
    completed_sims = [0]

    def _progress(done: int, total: int):
        completed_sims[0] = done
        pct = done / max(total, 1)
        bar_width = 30
        filled = int(pct * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"\r  [{bar}] {done}/{total}", end="", flush=True)

    try:
        from chronos.engine import ChronosEngine
        engine = ChronosEngine(preset=preset)
        output = engine.analyze(
            goal=goal,
            context=context,
            n_simulations=simulations,
            horizon_days=horizon,
            domain=domain,
            output_format="both",
            progress_callback=_progress,
        )
    except Exception as e:
        print()
        print(color(f"Error: {e}", Colors.RED))
        sys.exit(1)

    elapsed = time.time() - start
    print(f"\r  Completed {completed_sims[0]} simulations in {elapsed:.1f}s        ")
    print()

    if json_output:
        print(json.dumps(output["json_report"], indent=2, ensure_ascii=False))
    else:
        print(output["text_report"])

    cost = output.get("cost_estimate", "")
    if cost:
        print(color(f"  Cost estimate: {cost}", Colors.DIM))

    print(color(
        f"  Prediction saved. ID: {output['prediction_id']}",
        Colors.DIM,
    ))
    print(color(
        f"  Track outcome with: hermes chronos track {output['prediction_id']} <iv_id> \"what happened\"",
        Colors.DIM,
    ))
    print()


def chronos_track(
    prediction_id: str,
    intervention_id: str,
    outcome: str,
    success: Optional[bool] = None,
    delta: Optional[float] = None,
    notes: str = "",
):
    """
    Record the outcome of an intervention to improve future predictions.

    Usage:
        hermes chronos track chr_1234567_abc123 iv_001 "Sent the email, got response in 2 days"
        hermes chronos track chr_1234567_abc123 iv_001 "Sent the email, no response" --success=false --delta=-0.3
    """
    _print_banner()
    print(color(f"Recording outcome for prediction {prediction_id}...", Colors.DIM))

    try:
        engine = _get_engine()
        outcome_id = engine.record_outcome(
            prediction_id=prediction_id,
            intervention_id=intervention_id,
            outcome_text=outcome,
            success=success,
            delta_score=delta,
            notes=notes,
        )
        print(color(f"  Outcome recorded: {outcome_id}", Colors.CYAN))
        print(color("  Chronos will use this to improve future leverage predictions.", Colors.DIM))
        print()
    except Exception as e:
        print(color(f"Error: {e}", Colors.DIM))
        sys.exit(1)


def chronos_show(prediction_id: str, json_output: bool = False):
    """
    Show a stored prediction by ID.

    Usage:
        hermes chronos show chr_1234567_abc123
    """
    _print_banner()
    try:
        engine = _get_engine()
        pred = engine.get_prediction(prediction_id)
        if not pred:
            print(color(f"Prediction not found: {prediction_id}", Colors.DIM))
            sys.exit(1)

        if json_output:
            print(json.dumps(pred, indent=2, ensure_ascii=False))
            return

        print(color(f"Prediction: {prediction_id}", Colors.CYAN))
        print(color(f"Goal: {pred['goal']}", Colors.DIM))
        print(color(f"Horizon: {pred['horizon_days']} days", Colors.DIM))
        print(color(f"Confidence: {pred.get('confidence', 0):.2f}", Colors.DIM))
        print(color(f"Summary: {pred.get('summary', 'N/A')}", Colors.DIM))
        print()
        print(color("Interventions:", Colors.CYAN))
        for iv in pred.get("interventions", []):
            print(f"  [{iv['id']}] {iv['action']}")
            print(f"         Score: {iv['composite_score']:.2f} | {iv['time_sensitivity']}")
            print()
    except Exception as e:
        print(color(f"Error: {e}", Colors.DIM))
        sys.exit(1)


def chronos_history(limit: int = 10, json_output: bool = False):
    """
    List recent Chronos predictions.

    Usage:
        hermes chronos history
        hermes chronos history --limit=20
    """
    _print_banner()
    try:
        engine = _get_engine()
        predictions = engine.list_predictions(limit=limit)

        if not predictions:
            print(color("No predictions yet. Run: hermes chronos analyze \"your goal\"", Colors.DIM))
            return

        if json_output:
            print(json.dumps(predictions, indent=2, ensure_ascii=False))
            return

        print(color(f"Recent Predictions ({len(predictions)})", Colors.CYAN))
        print()
        for pred in predictions:
            created = time.strftime(
                "%Y-%m-%d %H:%M",
                time.localtime(pred.get("created_at", 0)),
            )
            confidence = pred.get("confidence", 0)
            n_iv = len(pred.get("interventions", []))
            print(f"  {color(pred['id'], Colors.CYAN)}")
            print(f"    Goal:        {pred['goal'][:70]}")
            print(f"    Created:     {created}")
            print(f"    Confidence:  {confidence:.2f}")
            print(f"    Interventions: {n_iv}")
            if pred.get("domain"):
                print(f"    Domain:      {pred['domain']}")
            print()
    except Exception as e:
        print(color(f"Error: {e}", Colors.DIM))
        sys.exit(1)
