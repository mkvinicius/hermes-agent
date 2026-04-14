#!/usr/bin/env python3
"""
Chronos Causal Analyzer

Core algorithm: given simulation results, find the causal leverage points —
the minimal interventions that, when applied in the present, converge the
most futures toward the desired outcome.

Algorithm:
  1. Split simulations into success cluster vs failure cluster
  2. Extract decision patterns from each cluster
  3. Find decisions that appear frequently in success but rarely in failure
     (and vice versa) — these are the leverage points
  4. Use LLM to synthesize raw patterns into actionable interventions
  5. Score each intervention by: leverage_ratio × feasibility × reversibility
"""

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from chronos.simulator import SimulationResult

logger = logging.getLogger(__name__)

# Threshold: simulations above this score are "success"
SUCCESS_THRESHOLD = 0.65
FAILURE_THRESHOLD = 0.40


@dataclass
class Intervention:
    """A single prescriptive action with causal metadata."""
    id: str
    action: str                  # What to do, concretely
    action_type: str             # Category: "communicate", "decide", "invest", "remove", etc.
    rationale: str               # Why this is a leverage point
    leverage_score: float        # 0.0–1.0: how much this shifts outcomes
    feasibility_score: float     # 0.0–1.0: how easy to apply now
    reversibility_score: float   # 0.0–1.0: how easy to undo if wrong
    composite_score: float       # Weighted combination for ranking
    time_sensitivity: str        # "immediate", "this_week", "this_month"
    supporting_simulations: int  # How many sims showed this as key
    failure_prevention: str      # What failure mode this avoids

    def to_dict(self) -> Dict:
        return asdict(self)


def _cluster_simulations(
    results: List[SimulationResult],
) -> Tuple[List[SimulationResult], List[SimulationResult], List[SimulationResult]]:
    """Split simulations into success, partial, failure clusters."""
    successes = [r for r in results if r.outcome_score >= SUCCESS_THRESHOLD and not r.error]
    failures = [r for r in results if r.outcome_score < FAILURE_THRESHOLD and not r.error]
    partials = [r for r in results if FAILURE_THRESHOLD <= r.outcome_score < SUCCESS_THRESHOLD and not r.error]
    return successes, partials, failures


def _extract_decision_patterns(
    simulations: List[SimulationResult],
) -> Counter:
    """Count how often each decision/inflection appears in a cluster."""
    counter = Counter()
    for sim in simulations:
        for decision in sim.key_decisions:
            # Normalize: lowercase, strip punctuation
            normalized = re.sub(r"[^\w\s]", "", decision.lower()).strip()
            if normalized:
                counter[normalized] += 1
        for point in sim.inflection_points:
            normalized = re.sub(r"[^\w\s]", "", point.lower()).strip()
            if normalized:
                counter["inflect:" + normalized] += 1
    return counter


def _build_analysis_prompt(
    goal: str,
    successes: List[SimulationResult],
    failures: List[SimulationResult],
    context: str = "",
    leverage_history: Optional[Dict] = None,
) -> List[Dict]:
    """Build the LLM prompt for causal leverage identification."""

    # Sample simulations to stay within context limits
    max_sims = 8
    success_sample = successes[:max_sims]
    failure_sample = failures[:max_sims]

    def fmt_sim(sim: SimulationResult, idx: int) -> str:
        lines = [
            f"  Scenario {idx + 1} (score: {sim.outcome_score:.2f}, "
            f"conditions: {sim.seed.time_pressure}, {sim.seed.resource_level}, "
            f"{sim.seed.external_event}):",
            f"    Outcome: {sim.final_state}",
            f"    Key decisions: {'; '.join(sim.key_decisions[:3])}",
            f"    Inflection points: {'; '.join(sim.inflection_points[:2])}",
        ]
        return "\n".join(lines)

    success_text = "\n".join(fmt_sim(s, i) for i, s in enumerate(success_sample))
    failure_text = "\n".join(fmt_sim(f, i) for i, f in enumerate(failure_sample))

    history_text = ""
    if leverage_history:
        history_text = f"\n\nHISTORICAL LEVERAGE DATA:\n{json.dumps(leverage_history, indent=2)}"

    system = (
        "You are a causal inference engine. You analyze parallel future simulations "
        "to find the minimal present-day interventions that most reliably shift "
        "outcomes from failure toward success.\n\n"
        "Output a JSON object with key 'interventions': an array of objects, "
        "each with:\n"
        "  id: string (unique, e.g. 'iv_001')\n"
        "  action: string — specific, concrete action to take NOW\n"
        "  action_type: string — category: communicate/decide/invest/remove/"
        "delegate/measure/protect/accelerate\n"
        "  rationale: string — why this intervention shifts futures (cite patterns)\n"
        "  leverage_score: float 0.0-1.0 — how strongly this shifts outcomes\n"
        "  feasibility_score: float 0.0-1.0 — how easy to apply today\n"
        "  reversibility_score: float 0.0-1.0 — how easy to undo\n"
        "  time_sensitivity: 'immediate'|'this_week'|'this_month'\n"
        "  failure_prevention: string — what failure mode this avoids\n\n"
        "Output 3-7 interventions. Output ONLY valid JSON."
    )

    user_content = [
        f"GOAL: {goal}",
        f"TOTAL SIMULATIONS: {len(successes) + len(failures)} "
        f"({len(successes)} success, {len(failures)} failure)",
    ]
    if context:
        user_content.append(f"\nCONTEXT: {context}")
    user_content.extend([
        f"\nSUCCESSFUL TRAJECTORIES ({len(success_sample)} shown):",
        success_text or "  (none in this batch)",
        f"\nFAILURE TRAJECTORIES ({len(failure_sample)} shown):",
        failure_text or "  (none in this batch)",
    ])
    if history_text:
        user_content.append(history_text)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_content)},
    ]


class CausalAnalyzer:
    """
    Finds causal leverage points by contrasting successful vs failed simulations.
    Uses LLM synthesis for pattern generalization.
    """

    def __init__(self, model: Optional[str] = None):
        self._model = model

    def analyze(
        self,
        goal: str,
        results: List[SimulationResult],
        context: str = "",
        leverage_history: Optional[Dict] = None,
    ) -> List[Intervention]:
        """
        Analyze simulation results and return ranked interventions.

        Args:
            goal: The goal that was simulated.
            results: All simulation outcomes from ScenarioSimulator.run().
            context: Additional context from the original request.
            leverage_history: Historical performance of intervention types.

        Returns:
            List of Intervention objects, ranked by composite_score descending.
        """
        successes, partials, failures = _cluster_simulations(results)

        logger.info(
            "Analyzing: %d success, %d partial, %d failure simulations",
            len(successes), len(partials), len(failures),
        )

        # Edge case: all successes or all failures — use partial as contrast set
        if not failures and partials:
            failures = partials[:len(partials) // 2]
        if not successes and partials:
            successes = partials[len(partials) // 2:]

        messages = _build_analysis_prompt(
            goal, successes, failures, context, leverage_history
        )

        from agent.auxiliary_client import call_llm
        try:
            response = call_llm(
                task="session_search",
                model=self._model,
                messages=messages,
                temperature=0.3,   # low temp = consistent causal reasoning
                max_tokens=1500,
            )
            raw = response.choices[0].message.content or ""
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]

            parsed = json.loads(raw)
            raw_interventions = parsed.get("interventions", [])
        except Exception as e:
            logger.error("CausalAnalyzer LLM call failed: %s", e)
            return []

        # Build Intervention objects with composite scoring
        interventions = []
        for iv in raw_interventions:
            leverage = float(iv.get("leverage_score", 0.5))
            feasibility = float(iv.get("feasibility_score", 0.5))
            reversibility = float(iv.get("reversibility_score", 0.5))
            # Composite: leverage matters most, feasibility second, reversibility tie-breaks
            composite = (leverage * 0.55) + (feasibility * 0.30) + (reversibility * 0.15)

            # Boost from historical performance
            if leverage_history:
                action_type = iv.get("action_type", "")
                hist = leverage_history.get(action_type, {})
                if hist:
                    sc = hist.get("success_count", 0)
                    fc = hist.get("failure_count", 0)
                    total = sc + fc
                    if total > 3:
                        historical_rate = sc / total
                        composite = composite * 0.85 + historical_rate * 0.15

            # Count supporting simulations
            action_lower = iv.get("action", "").lower()
            supporting = sum(
                1 for r in successes
                if any(action_lower[:20] in d.lower() for d in r.key_decisions)
            )

            interventions.append(Intervention(
                id=iv.get("id", f"iv_{len(interventions):03d}"),
                action=iv.get("action", ""),
                action_type=iv.get("action_type", "unknown"),
                rationale=iv.get("rationale", ""),
                leverage_score=leverage,
                feasibility_score=feasibility,
                reversibility_score=reversibility,
                composite_score=round(composite, 4),
                time_sensitivity=iv.get("time_sensitivity", "this_week"),
                supporting_simulations=supporting,
                failure_prevention=iv.get("failure_prevention", ""),
            ))

        interventions.sort(key=lambda x: x.composite_score, reverse=True)
        return interventions
