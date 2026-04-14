#!/usr/bin/env python3
"""
Chronos Model Tiers

Separates model usage by phase to optimize cost vs quality:

  simulation_model  → cheap/fast  (runs N times in parallel)
  analysis_model    → strong      (runs once for causal reasoning)
  summary_model     → any         (runs once for executive summary)

Configuration (in priority order):
  1. Explicit arguments to ChronosEngine()
  2. Environment variables (CHRONOS_SIM_MODEL, CHRONOS_ANALYSIS_MODEL, etc.)
  3. config.yaml section [chronos]
  4. Hermes auxiliary_client auto-detection (fallback)

Recommended tiers by budget:

  Budget (< $0.01 per 50 sims):
    simulation_model  = "google/gemini-2.0-flash-exp"
    analysis_model    = "anthropic/claude-haiku-4-5-20251001"

  Balanced (~$0.02 per 50 sims):
    simulation_model  = "openai/gpt-4o-mini"
    analysis_model    = "anthropic/claude-sonnet-4-6"

  Premium (~$0.15 per 50 sims):
    simulation_model  = "anthropic/claude-haiku-4-5-20251001"
    analysis_model    = "anthropic/claude-opus-4-6"

  Local (free, requires Ollama):
    simulation_model  = "ollama/llama3.3"
    analysis_model    = "ollama/qwen2.5:32b"
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Cost reference table (USD per 1M tokens, input/output) ──────────────────
# Used for estimation only — not enforced
MODEL_COSTS: dict = {
    # Anthropic
    "claude-opus-4-6":              (15.0, 75.0),
    "claude-sonnet-4-6":            (3.0,  15.0),
    "claude-haiku-4-5-20251001":    (0.8,  4.0),
    # OpenAI
    "gpt-4o":                       (2.5,  10.0),
    "gpt-4o-mini":                  (0.15, 0.6),
    "o1":                           (15.0, 60.0),
    # Google
    "gemini-2.5-pro":               (1.25, 10.0),
    "gemini-2.0-flash":             (0.1,  0.4),
    "gemini-flash-1.5":             (0.075, 0.3),
    # xAI
    "grok-4":                       (3.0,  15.0),
    "grok-code-fast":               (0.5,  1.5),
    # Mistral
    "mistral-large-latest":         (2.0,  6.0),
    "mistral-small-latest":         (0.2,  0.6),
    # Qwen
    "qwen-max":                     (0.4,  1.2),
    "qwen-turbo":                   (0.05, 0.15),
    # Local
    "ollama/*":                     (0.0,  0.0),
}

# Env var names
_ENV_SIM_MODEL       = "CHRONOS_SIM_MODEL"
_ENV_ANALYSIS_MODEL  = "CHRONOS_ANALYSIS_MODEL"
_ENV_SUMMARY_MODEL   = "CHRONOS_SUMMARY_MODEL"
_ENV_EXTRACT_MODEL   = "CHRONOS_EXTRACT_MODEL"
_ENV_MAX_WORKERS     = "CHRONOS_MAX_WORKERS"


@dataclass
class ChronosModelConfig:
    """
    Model tier configuration for the Chronos pipeline.

    simulation_model:  used for each of the N parallel simulations
    analysis_model:    used once for causal leverage identification
    summary_model:     used once for executive summary generation
    extract_model:     used once for entity graph extraction
    max_sim_workers:   ThreadPoolExecutor concurrency for simulations
    """
    simulation_model:  Optional[str] = None
    analysis_model:    Optional[str] = None
    summary_model:     Optional[str] = None
    extract_model:     Optional[str] = None
    max_sim_workers:   int = 8

    @classmethod
    def from_env(cls) -> "ChronosModelConfig":
        """Build config from environment variables."""
        workers_raw = os.getenv(_ENV_MAX_WORKERS, "")
        try:
            workers = int(workers_raw) if workers_raw else 8
        except ValueError:
            workers = 8
        return cls(
            simulation_model=os.getenv(_ENV_SIM_MODEL) or None,
            analysis_model=os.getenv(_ENV_ANALYSIS_MODEL) or None,
            summary_model=os.getenv(_ENV_SUMMARY_MODEL) or None,
            extract_model=os.getenv(_ENV_EXTRACT_MODEL) or None,
            max_sim_workers=max(1, min(workers, 32)),
        )

    @classmethod
    def from_yaml(cls) -> "ChronosModelConfig":
        """Load from ~/.hermes/config.yaml [chronos] section if present."""
        try:
            from hermes_cli.config import load_config
            cfg = load_config()
            chronos_cfg = cfg.get("chronos", {})
            if not chronos_cfg:
                return cls()
            workers_raw = chronos_cfg.get("max_sim_workers", 8)
            return cls(
                simulation_model=chronos_cfg.get("simulation_model") or None,
                analysis_model=chronos_cfg.get("analysis_model") or None,
                summary_model=chronos_cfg.get("summary_model") or None,
                extract_model=chronos_cfg.get("extract_model") or None,
                max_sim_workers=max(1, min(int(workers_raw), 32)),
            )
        except Exception:
            return cls()

    @classmethod
    def resolve(
        cls,
        simulation_model:  Optional[str] = None,
        analysis_model:    Optional[str] = None,
        summary_model:     Optional[str] = None,
        extract_model:     Optional[str] = None,
        max_sim_workers:   Optional[int] = None,
    ) -> "ChronosModelConfig":
        """
        Merge explicit args > env vars > config.yaml, in that order.
        None means "use Hermes auxiliary_client auto-detection".
        """
        yaml_cfg = cls.from_yaml()
        env_cfg  = cls.from_env()

        def pick(explicit, env_val, yaml_val):
            return explicit or env_val or yaml_val or None

        resolved_workers = (
            max_sim_workers
            or env_cfg.max_sim_workers
            or yaml_cfg.max_sim_workers
            or 8
        )

        return cls(
            simulation_model=pick(simulation_model,  env_cfg.simulation_model,  yaml_cfg.simulation_model),
            analysis_model  =pick(analysis_model,    env_cfg.analysis_model,    yaml_cfg.analysis_model),
            summary_model   =pick(summary_model,     env_cfg.summary_model,     yaml_cfg.summary_model),
            extract_model   =pick(extract_model,     env_cfg.extract_model,     yaml_cfg.extract_model),
            max_sim_workers =max(1, min(int(resolved_workers), 32)),
        )

    def describe(self) -> str:
        """Human-readable description of the model tier config."""
        def _fmt(m):
            return m.split("/")[-1] if m and "/" in m else (m or "auto")

        lines = [
            "Chronos model tiers:",
            f"  simulation  → {_fmt(self.simulation_model)} "
            f"(× up to {self.max_sim_workers} parallel workers)",
            f"  analysis    → {_fmt(self.analysis_model)}",
            f"  summary     → {_fmt(self.summary_model)}",
            f"  extraction  → {_fmt(self.extract_model)}",
        ]
        return "\n".join(lines)

    def estimate_cost(self, n_simulations: int = 30) -> str:
        """Rough cost estimate for one full analysis run."""
        def _cost_per_million(model: Optional[str]):
            if not model:
                return (2.5, 10.0)  # gpt-4o as default assumption
            slug = model.split("/")[-1].lower()
            for key, (inp, out) in MODEL_COSTS.items():
                if key.replace("*", "") in slug or slug.startswith(key.replace("/*", "")):
                    return (inp, out)
            return (1.0, 4.0)   # unknown model — mid-range estimate

        sim_inp, sim_out   = _cost_per_million(self.simulation_model)
        ana_inp, ana_out   = _cost_per_million(self.analysis_model)
        ext_inp, ext_out   = _cost_per_million(self.extract_model)
        sum_inp, sum_out   = _cost_per_million(self.summary_model)

        # Approximate token counts per phase
        sim_tokens_in  = 500 * n_simulations
        sim_tokens_out = 400 * n_simulations
        ana_tokens_in, ana_tokens_out   = 2000, 1500
        ext_tokens_in, ext_tokens_out   = 800,  1200
        sum_tokens_in, sum_tokens_out   = 500,  150

        total = (
            (sim_tokens_in  * sim_inp + sim_tokens_out  * sim_out)  / 1_000_000 +
            (ana_tokens_in  * ana_inp + ana_tokens_out  * ana_out)  / 1_000_000 +
            (ext_tokens_in  * ext_inp + ext_tokens_out  * ext_out)  / 1_000_000 +
            (sum_tokens_in  * sum_inp + sum_tokens_out  * sum_out)  / 1_000_000
        )

        if total < 0.001:
            return f"< $0.001 (essentially free)"
        return f"~${total:.4f}"


# ─── Pre-built tier presets ───────────────────────────────────────────────────

PRESETS: dict[str, ChronosModelConfig] = {
    "budget": ChronosModelConfig(
        simulation_model="google/gemini-2.0-flash-exp",
        analysis_model="anthropic/claude-haiku-4-5-20251001",
        summary_model="google/gemini-2.0-flash-exp",
        extract_model="google/gemini-2.0-flash-exp",
        max_sim_workers=12,
    ),
    "balanced": ChronosModelConfig(
        simulation_model="openai/gpt-4o-mini",
        analysis_model="anthropic/claude-sonnet-4-6",
        summary_model="openai/gpt-4o-mini",
        extract_model="openai/gpt-4o-mini",
        max_sim_workers=8,
    ),
    "premium": ChronosModelConfig(
        simulation_model="anthropic/claude-haiku-4-5-20251001",
        analysis_model="anthropic/claude-opus-4-6",
        summary_model="anthropic/claude-sonnet-4-6",
        extract_model="anthropic/claude-sonnet-4-6",
        max_sim_workers=6,
    ),
    "local": ChronosModelConfig(
        simulation_model="ollama/llama3.3",
        analysis_model="ollama/qwen2.5:32b",
        summary_model="ollama/llama3.3",
        extract_model="ollama/llama3.3",
        max_sim_workers=4,
    ),
    "xai": ChronosModelConfig(
        simulation_model="xai/grok-code-fast",
        analysis_model="xai/grok-4",
        summary_model="xai/grok-code-fast",
        extract_model="xai/grok-code-fast",
        max_sim_workers=8,
    ),
}
