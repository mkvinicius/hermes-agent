"""
Chronos: Temporal Causal Engine for Hermes Agent.

Finds minimal present actions that converge the maximum number of simulated
futures toward a desired goal. Architecture:

    Goal + Context
         │
         ▼
    Simulator ──── runs N parallel LLM scenario simulations
         │
         ▼
    CausalAnalyzer ── clusters outcomes, finds divergence points
         │
         ▼
    Prescriptor ──── ranks interventions by leverage score
         │
         ▼
    TemporalDB ───── persists prediction → action → outcome for feedback loop
"""

from chronos.engine import ChronosEngine

__all__ = ["ChronosEngine"]
