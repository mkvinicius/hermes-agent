#!/usr/bin/env python3
"""
Chronos Engine

Main orchestrator. Coordinates the full pipeline:
  ScenarioSimulator → CausalAnalyzer → Prescriptor → TemporalDB

Entry point for both the Hermes tool and the CLI.
"""

import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from chronos.simulator import ScenarioSimulator, SimulationResult
from chronos.causal_analyzer import CausalAnalyzer, Intervention
from chronos.prescriptor import build_summary, format_as_json, format_as_text
from chronos.temporal_db import TemporalDB
from chronos.entity_graph import EntityExtractor, EntityGraph
from chronos.model_tiers import ChronosModelConfig, PRESETS

logger = logging.getLogger(__name__)


class ChronosEngine:
    """
    Temporal Causal Engine.

    Given a goal and context, runs parallel future simulations, identifies
    causal leverage points, and prescribes the minimal present-day actions
    that converge the most futures toward success.

    Usage:
        # Auto (Hermes picks best available model for each tier)
        engine = ChronosEngine()

        # Named preset
        engine = ChronosEngine(preset="budget")   # Gemini Flash sims + Haiku analysis
        engine = ChronosEngine(preset="balanced")  # GPT-4o-mini sims + Sonnet analysis
        engine = ChronosEngine(preset="premium")   # Haiku sims + Opus analysis
        engine = ChronosEngine(preset="local")     # Llama3.3 sims + Qwen2.5 analysis (free)
        engine = ChronosEngine(preset="xai")       # Grok-fast sims + Grok-4 analysis

        # Full custom control
        engine = ChronosEngine(
            simulation_model="google/gemini-2.0-flash-exp",
            analysis_model="anthropic/claude-opus-4-6",
        )

        result = engine.analyze(
            goal="Launch product by Q3",
            context="We have a 5-person team and 3 months of runway",
            n_simulations=50,
            horizon_days=90,
        )
        print(result["text_report"])
        print(result["cost_estimate"])   # e.g. "~$0.018"
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        # Legacy single-model arg (all tiers use same model)
        model: Optional[str] = None,
        # Named preset: "budget" | "balanced" | "premium" | "local" | "xai"
        preset: Optional[str] = None,
        # Per-tier overrides (take precedence over preset and env vars)
        simulation_model:  Optional[str] = None,
        analysis_model:    Optional[str] = None,
        summary_model:     Optional[str] = None,
        extract_model:     Optional[str] = None,
        max_sim_workers:   Optional[int] = None,
    ):
        # Resolve model config: explicit args > preset > env vars > config.yaml > auto
        if preset and preset in PRESETS:
            base = PRESETS[preset]
            self._model_cfg = ChronosModelConfig(
                simulation_model  = simulation_model  or base.simulation_model,
                analysis_model    = analysis_model    or base.analysis_model,
                summary_model     = summary_model     or base.summary_model,
                extract_model     = extract_model     or base.extract_model,
                max_sim_workers   = max_sim_workers   or base.max_sim_workers,
            )
        else:
            # Legacy: if single `model` arg passed, use it for all tiers
            _fallback = model or None
            self._model_cfg = ChronosModelConfig.resolve(
                simulation_model  = simulation_model  or _fallback,
                analysis_model    = analysis_model    or _fallback,
                summary_model     = summary_model     or _fallback,
                extract_model     = extract_model     or _fallback,
                max_sim_workers   = max_sim_workers,
            )

        logger.info("ChronosEngine init: %s", self._model_cfg.describe())

        self._db = TemporalDB(db_path)
        self._simulator = ScenarioSimulator(
            max_workers=self._model_cfg.max_sim_workers,
            model=self._model_cfg.simulation_model,
        )
        self._analyzer  = CausalAnalyzer(model=self._model_cfg.analysis_model)
        self._extractor = EntityExtractor(model=self._model_cfg.extract_model)
        self._model     = self._model_cfg.analysis_model  # for summary

    # ------------------------------------------------------------------
    # Primary interface
    # ------------------------------------------------------------------

    def analyze(
        self,
        goal: str,
        context: str = "",
        n_simulations: int = 50,
        horizon_days: int = 30,
        domain: str = "",
        forced_decisions: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        output_format: str = "both",  # "json" | "text" | "both"
    ) -> Dict[str, Any]:
        """
        Full Chronos pipeline: simulate → analyze → prescribe → store.

        Args:
            goal: What you want to achieve.
            context: Background information that shapes simulations.
            n_simulations: Number of parallel futures to simulate (10–200).
            horizon_days: Time horizon for each simulation.
            domain: Domain tag for leverage history lookup (e.g. "product", "health").
            forced_decisions: Specific decisions to test across simulations.
            progress_callback: fn(completed, total) called after each simulation.
            output_format: "json", "text", or "both".

        Returns:
            dict with keys: prediction_id, interventions, simulation_results,
            json_report (if requested), text_report (if requested), summary.
        """
        prediction_id = f"chr_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        logger.info(
            "Chronos analysis started: id=%s goal='%s...' n=%d horizon=%dd",
            prediction_id, goal[:40], n_simulations, horizon_days,
        )

        # --- Phase 0: Extract world model (MiroFish-inspired entity graph) ---
        entity_graph: Optional[EntityGraph] = None
        if context or len(goal) > 30:
            logger.info("Extracting entity graph from goal + context...")
            entity_graph = self._extractor.extract(goal, context)
            if entity_graph.entities:
                logger.info(
                    "Entity graph: %d entities, %d relationships",
                    len(entity_graph.entities),
                    len(entity_graph.relationships),
                )

        # --- Phase 1: Simulate futures ---
        simulation_results: List[SimulationResult] = self._simulator.run(
            goal=goal,
            n_simulations=n_simulations,
            horizon_days=horizon_days,
            context=context,
            forced_decisions=forced_decisions,
            entity_graph=entity_graph,
            progress_callback=progress_callback,
        )

        # --- Phase 2: Find causal leverage ---
        leverage_history = self._get_leverage_history(domain)
        # Enrich context with entity graph summary for better causal reasoning
        analysis_context = context
        if entity_graph and entity_graph.entities:
            analysis_context = f"{context}\n\n{entity_graph.summary()}".strip()
        interventions: List[Intervention] = self._analyzer.analyze(
            goal=goal,
            results=simulation_results,
            context=analysis_context,
            leverage_history=leverage_history,
        )

        # --- Phase 3: Build summary ---
        summary = build_summary(
            goal=goal,
            interventions=interventions,
            results=simulation_results,
            prediction_id=prediction_id,
            model=self._model,
        )

        # --- Phase 4: Persist prediction ---
        self._db.store_prediction(
            prediction_id=prediction_id,
            goal=goal,
            interventions=[iv.to_dict() for iv in interventions],
            horizon_days=horizon_days,
            context=context,
            n_simulations=n_simulations,
            summary=summary,
            confidence=self._compute_confidence(interventions, simulation_results),
            domain=domain,
        )

        logger.info(
            "Chronos complete: id=%s interventions=%d confidence=%.2f",
            prediction_id,
            len(interventions),
            self._compute_confidence(interventions, simulation_results),
        )

        # --- Phase 5: Format output ---
        cost_estimate = self._model_cfg.estimate_cost(n_simulations)
        output: Dict[str, Any] = {
            "prediction_id": prediction_id,
            "interventions": [iv.to_dict() for iv in interventions],
            "simulation_results": [r.to_dict() for r in simulation_results],
            "summary": summary,
            "entity_graph": entity_graph.to_dict() if entity_graph else None,
            "cost_estimate": cost_estimate,
            "model_tiers": {
                "simulation":  self._model_cfg.simulation_model  or "auto",
                "analysis":    self._model_cfg.analysis_model    or "auto",
                "summary":     self._model_cfg.summary_model     or "auto",
                "extraction":  self._model_cfg.extract_model     or "auto",
                "sim_workers": self._model_cfg.max_sim_workers,
            },
        }

        if output_format in ("json", "both"):
            output["json_report"] = format_as_json(
                prediction_id=prediction_id,
                goal=goal,
                interventions=interventions,
                results=simulation_results,
                summary=summary,
                horizon_days=horizon_days,
            )

        if output_format in ("text", "both"):
            output["text_report"] = format_as_text(
                prediction_id=prediction_id,
                goal=goal,
                interventions=interventions,
                results=simulation_results,
                summary=summary,
                horizon_days=horizon_days,
            )

        return output

    # ------------------------------------------------------------------
    # Feedback loop
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        prediction_id: str,
        intervention_id: str,
        outcome_text: str,
        success: Optional[bool] = None,
        delta_score: Optional[float] = None,
        notes: str = "",
    ) -> str:
        """
        Record what actually happened after an intervention was applied.

        This feeds the feedback loop: future analyses for similar domains
        will have historical leverage data to boost or penalize intervention types.

        Args:
            prediction_id: The prediction this outcome belongs to.
            intervention_id: Which specific intervention was applied.
            outcome_text: Human description of what happened.
            success: True if the outcome was positive, False if not, None if unclear.
            delta_score: How much better/worse than predicted (−1.0 to +1.0).
            notes: Any additional notes.

        Returns:
            outcome_id
        """
        import uuid as _uuid
        outcome_id = f"out_{int(time.time())}_{_uuid.uuid4().hex[:6]}"
        self._db.record_outcome(
            outcome_id=outcome_id,
            prediction_id=prediction_id,
            intervention_id=intervention_id,
            outcome_text=outcome_text,
            success=success,
            delta_score=delta_score,
            notes=notes,
        )
        logger.info("Outcome recorded: %s for prediction %s", outcome_id, prediction_id)
        return outcome_id

    def get_prediction(self, prediction_id: str) -> Optional[Dict]:
        """Retrieve a stored prediction by ID."""
        return self._db.get_prediction(prediction_id)

    def list_predictions(self, limit: int = 20) -> List[Dict]:
        """List recent predictions."""
        return self._db.list_predictions(limit=limit)

    def get_training_data(self) -> List[Dict]:
        """Return prediction/outcome pairs for model analysis."""
        return self._db.get_training_data()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_leverage_history(self, domain: str) -> Optional[Dict]:
        """Fetch historical leverage stats for known intervention types."""
        action_types = [
            "communicate", "decide", "invest", "remove",
            "delegate", "measure", "protect", "accelerate",
        ]
        history = {}
        for at in action_types:
            stats = self._db.get_leverage_stats(at, domain)
            if stats:
                history[at] = stats
        return history if history else None

    @staticmethod
    def _compute_confidence(
        interventions: List[Intervention],
        results: List[SimulationResult],
    ) -> float:
        """Overall confidence in the analysis quality."""
        if not results:
            return 0.0
        valid = [r for r in results if not r.error]
        if not valid:
            return 0.0
        # Data richness: how many valid simulations
        data_score = min(len(valid) / 50.0, 1.0)
        # Spread score: good spread between success and failure
        scores = [r.outcome_score for r in valid]
        spread = max(scores) - min(scores) if scores else 0
        # Intervention quality: avg leverage of top 3
        top_leverage = (
            sum(iv.leverage_score for iv in interventions[:3]) / min(3, len(interventions))
            if interventions else 0
        )
        return round((data_score * 0.4) + (spread * 0.3) + (top_leverage * 0.3), 3)
