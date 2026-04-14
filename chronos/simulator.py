#!/usr/bin/env python3
"""
Chronos Scenario Simulator

Runs N parallel LLM-based future simulations for a given goal.
Each simulation represents a different "possible trajectory" — varying
initial conditions, decisions, and external factors — producing a scored
outcome that feeds into the causal analysis.

Design:
- Uses ThreadPoolExecutor (same pattern as delegate_tool.py) for parallelism
- Each simulation is a lightweight LLM call (no full agent execution)
- Simulations vary along: time_pressure, resource_level, external_events,
  decision_style, obstacle_severity
- Returns raw simulation results for CausalAnalyzer to process
"""

import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Simulation variation axes — used to generate diverse scenario seeds
_TIME_PRESSURES = ["urgent (days)", "moderate (weeks)", "relaxed (months)"]
_RESOURCE_LEVELS = ["constrained", "moderate", "abundant"]
_EXTERNAL_EVENTS = [
    "no major surprises",
    "unexpected competitor emerges",
    "key ally withdraws support",
    "market shift accelerates goal",
    "regulatory change impacts plan",
    "technology breakthrough available",
    "team morale drops",
    "unexpected opportunity arises",
]
_DECISION_STYLES = ["conservative", "balanced", "aggressive"]
_OBSTACLE_LEVELS = ["minimal friction", "moderate obstacles", "significant resistance"]


@dataclass
class ScenarioSeed:
    """Parameters that define one simulation variant."""
    scenario_id: str
    time_pressure: str
    resource_level: str
    external_event: str
    decision_style: str
    obstacle_level: str
    key_decision: str = ""   # Optional forced decision point to test


@dataclass
class SimulationResult:
    """Output from one simulated future trajectory."""
    scenario_id: str
    seed: ScenarioSeed
    trajectory: str          # Narrative of how the future unfolds
    outcome_score: float     # 0.0 = complete failure, 1.0 = perfect success
    outcome_label: str       # "success" | "partial" | "failure"
    key_decisions: List[str] = field(default_factory=list)   # Critical choice points
    inflection_points: List[str] = field(default_factory=list)  # Where trajectory diverged
    final_state: str = ""
    tokens_used: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


def generate_scenario_seeds(
    n: int,
    forced_decisions: Optional[List[str]] = None,
) -> List[ScenarioSeed]:
    """Generate N diverse scenario seeds with varied parameters."""
    seeds = []
    for i in range(n):
        seed = ScenarioSeed(
            scenario_id=f"sim_{i:04d}",
            time_pressure=_TIME_PRESSURES[i % len(_TIME_PRESSURES)],
            resource_level=_RESOURCE_LEVELS[i % len(_RESOURCE_LEVELS)],
            external_event=random.choice(_EXTERNAL_EVENTS),
            decision_style=_DECISION_STYLES[i % len(_DECISION_STYLES)],
            obstacle_level=_OBSTACLE_LEVELS[i % len(_OBSTACLE_LEVELS)],
            key_decision=(forced_decisions[i % len(forced_decisions)]
                          if forced_decisions else ""),
        )
        seeds.append(seed)
    # Shuffle so the first batch isn't biased toward one axis
    random.shuffle(seeds)
    return seeds


def _build_simulation_prompt(
    goal: str,
    seed: ScenarioSeed,
    horizon_days: int,
    context: str = "",
) -> List[Dict]:
    """Build the LLM messages for one simulation run."""
    system = (
        "You are a future-scenario simulator. Given a goal and initial conditions, "
        "simulate how the next {horizon} days unfold realistically — including "
        "setbacks, decisions, and outcomes. Be concrete and specific.\n\n"
        "Output a JSON object with these exact keys:\n"
        "  trajectory: string — narrative of how events unfold (3-5 sentences)\n"
        "  outcome_score: float 0.0-1.0 — how well the goal was achieved\n"
        "  outcome_label: 'success' | 'partial' | 'failure'\n"
        "  key_decisions: list of strings — 3-5 critical choice points that shaped the outcome\n"
        "  inflection_points: list of strings — moments where a different choice would have "
        "changed the outcome\n"
        "  final_state: string — one-sentence description of the end state\n\n"
        "Output ONLY valid JSON. No markdown."
    ).format(horizon=horizon_days)

    user_parts = [
        f"GOAL: {goal}",
        f"TIME HORIZON: {horizon_days} days",
        "",
        "SIMULATION CONDITIONS:",
        f"- Time pressure: {seed.time_pressure}",
        f"- Available resources: {seed.resource_level}",
        f"- External environment: {seed.external_event}",
        f"- Decision-making style applied: {seed.decision_style}",
        f"- Obstacle level: {seed.obstacle_level}",
    ]
    if seed.key_decision:
        user_parts.append(f"- Forced decision tested: {seed.key_decision}")
    if context:
        user_parts.extend(["", f"CONTEXT:\n{context}"])

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def _run_single_simulation(
    goal: str,
    seed: ScenarioSeed,
    horizon_days: int,
    context: str,
    model: Optional[str],
) -> SimulationResult:
    """Execute one simulation. Called in a worker thread."""
    from agent.auxiliary_client import call_llm

    messages = _build_simulation_prompt(goal, seed, horizon_days, context)
    start = time.time()
    try:
        response = call_llm(
            task="session_search",   # reuse session_search auxiliary slot
            model=model,
            messages=messages,
            temperature=0.9,         # high temp = diverse futures
            max_tokens=600,
        )
        raw = response.choices[0].message.content or ""
        # Strip markdown fences if model adds them
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]

        parsed = json.loads(raw)
        return SimulationResult(
            scenario_id=seed.scenario_id,
            seed=seed,
            trajectory=parsed.get("trajectory", ""),
            outcome_score=float(parsed.get("outcome_score", 0.5)),
            outcome_label=parsed.get("outcome_label", "partial"),
            key_decisions=parsed.get("key_decisions", []),
            inflection_points=parsed.get("inflection_points", []),
            final_state=parsed.get("final_state", ""),
            tokens_used=getattr(response.usage, "total_tokens", 0),
        )
    except Exception as e:
        elapsed = time.time() - start
        logger.debug("Simulation %s failed after %.1fs: %s", seed.scenario_id, elapsed, e)
        return SimulationResult(
            scenario_id=seed.scenario_id,
            seed=seed,
            trajectory="",
            outcome_score=0.0,
            outcome_label="failure",
            error=str(e),
        )


class ScenarioSimulator:
    """
    Runs N parallel future simulations and returns scored trajectories.

    Uses ThreadPoolExecutor so simulations run concurrently without
    spinning up full AIAgent subprocesses.
    """

    def __init__(
        self,
        max_workers: int = 8,
        model: Optional[str] = None,
    ):
        self._max_workers = max_workers
        self._model = model  # None = use auxiliary_client auto-detection

    def run(
        self,
        goal: str,
        n_simulations: int = 50,
        horizon_days: int = 30,
        context: str = "",
        forced_decisions: Optional[List[str]] = None,
        progress_callback=None,
    ) -> List[SimulationResult]:
        """
        Run N parallel simulations and return results.

        Args:
            goal: The desired outcome to simulate toward.
            n_simulations: Number of parallel future scenarios to generate.
            horizon_days: How far into the future each simulation looks.
            context: Additional background that shapes simulations.
            forced_decisions: Specific decisions to test across simulations.
            progress_callback: Optional fn(completed, total) for progress reporting.

        Returns:
            List of SimulationResult, sorted by outcome_score descending.
        """
        seeds = generate_scenario_seeds(n_simulations, forced_decisions)
        results: List[SimulationResult] = []
        completed = 0

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(
                    _run_single_simulation,
                    goal, seed, horizon_days, context, self._model
                ): seed
                for seed in seeds
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1
                if progress_callback:
                    try:
                        progress_callback(completed, n_simulations)
                    except Exception:
                        pass

        # Sort: highest scoring first
        results.sort(key=lambda r: r.outcome_score, reverse=True)
        logger.info(
            "Completed %d/%d simulations. Success rate: %.1f%%",
            sum(1 for r in results if r.error is None),
            n_simulations,
            100 * sum(1 for r in results if r.outcome_label == "success") / max(len(results), 1),
        )
        return results
