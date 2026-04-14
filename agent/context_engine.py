"""
Pluggable Context Engine

Provides a registry of context providers that inject structured blocks into
the agent's system prompt. Extends the existing MemoryProvider pattern to
support arbitrary context types beyond memory.

Design:
  - ContextProvider: interface for a single context source
  - ContextEngine: registry + builder, called by run_agent.py
  - Slot system: providers declare WHERE they inject (top/memory/tools/footer)
  - Priority: lower number = rendered first within the same slot

Built-in providers included:
  - ChronosContextProvider: injects recent Chronos predictions as context
  - CustomFileProvider: injects content from a user-specified file

Custom providers can be registered at runtime:
    from agent.context_engine import context_engine, ContextProvider

    class MyProvider(ContextProvider):
        slot = "footer"
        priority = 50
        def get_block(self, query, history):
            return "Current date: 2026-04-14"

    context_engine.register(MyProvider())

In run_agent.py, call:
    blocks = context_engine.build_context(user_message, history)
    # blocks["top"], blocks["memory"], blocks["tools"], blocks["footer"]
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Valid injection slots (ordered: top is earliest in prompt)
CONTEXT_SLOTS = ("top", "memory", "tools", "footer")


class ContextProvider(ABC):
    """
    Interface for a pluggable context block.

    Subclass this and register an instance with context_engine.register().
    """

    # Where in the system prompt this block appears
    slot: str = "footer"

    # Lower = rendered first (within same slot)
    priority: int = 50

    # Short identifier shown in debug logs
    name: str = "unnamed_provider"

    def is_available(self) -> bool:
        """Return False to skip this provider (e.g., missing config)."""
        return True

    @abstractmethod
    def get_block(
        self,
        query: str = "",
        history: Optional[List[Dict]] = None,
    ) -> Optional[str]:
        """
        Return a formatted string to inject into the system prompt, or None to skip.

        Args:
            query: The current user message (for query-aware context).
            history: Recent conversation history (for context-aware injection).
        """


class ContextEngine:
    """
    Registry and builder for context providers.

    Usage:
        engine = ContextEngine()
        engine.register(MyProvider())
        blocks = engine.build_context(query, history)
        # Inject blocks["top"] at top of system prompt, etc.
    """

    def __init__(self):
        self._providers: List[ContextProvider] = []

    def register(self, provider: ContextProvider) -> None:
        """Register a context provider."""
        if provider.slot not in CONTEXT_SLOTS:
            logger.warning(
                "ContextProvider %s has unknown slot '%s'; defaulting to 'footer'",
                provider.name, provider.slot,
            )
            provider.slot = "footer"
        self._providers.append(provider)
        self._providers.sort(key=lambda p: (CONTEXT_SLOTS.index(p.slot), p.priority))
        logger.debug("Registered context provider: %s (slot=%s, priority=%d)",
                     provider.name, provider.slot, provider.priority)

    def deregister(self, name: str) -> None:
        """Remove a provider by name."""
        self._providers = [p for p in self._providers if p.name != name]

    def build_context(
        self,
        query: str = "",
        history: Optional[List[Dict]] = None,
    ) -> Dict[str, str]:
        """
        Collect context blocks from all registered providers.

        Returns:
            dict keyed by slot name, each value is a concatenated string
            of all blocks for that slot. Empty slots have empty strings.
        """
        result: Dict[str, List[str]] = {slot: [] for slot in CONTEXT_SLOTS}

        for provider in self._providers:
            try:
                if not provider.is_available():
                    continue
                block = provider.get_block(query=query, history=history)
                if block and block.strip():
                    result[provider.slot].append(block.strip())
            except Exception as e:
                logger.debug(
                    "ContextProvider %s raised during get_block: %s",
                    provider.name, e,
                )

        return {slot: "\n\n".join(blocks) for slot, blocks in result.items()}

    def get_providers(self) -> List[ContextProvider]:
        return list(self._providers)

    def has_providers(self) -> bool:
        return bool(self._providers)


# ─── Singleton ────────────────────────────────────────────────────────────────

context_engine = ContextEngine()


# ─── Built-in providers ───────────────────────────────────────────────────────

class ChronosContextProvider(ContextProvider):
    """
    Injects the most recent Chronos prediction as context.

    Useful for goal-oriented sessions where Chronos has already analyzed
    the current objective — the agent sees the leverage points directly
    in its system prompt without needing to call the tool again.
    """

    slot = "footer"
    priority = 10
    name = "chronos_context"

    def __init__(self, max_predictions: int = 1, max_chars: int = 800):
        self._max_predictions = max_predictions
        self._max_chars = max_chars

    def is_available(self) -> bool:
        try:
            from chronos.temporal_db import TemporalDB  # noqa
            return True
        except ImportError:
            return False

    def get_block(self, query: str = "", history=None) -> Optional[str]:
        try:
            from chronos.temporal_db import TemporalDB
            db = TemporalDB()
            predictions = db.list_predictions(limit=self._max_predictions)
            if not predictions:
                return None

            p = predictions[0]
            interventions = p.get("interventions", [])[:3]
            if not interventions:
                return None

            lines = [
                "## Recent Chronos Analysis",
                f"Goal: {p['goal'][:100]}",
                f"Summary: {p.get('summary', '')[:200]}",
                "Top interventions:",
            ]
            for iv in interventions:
                lines.append(
                    f"  [{iv.get('id','')}] {iv.get('action','')[:80]} "
                    f"(score: {iv.get('composite_score', 0):.2f})"
                )
            lines.append(
                f"(hermes chronos show {p['id']} for full analysis)"
            )

            block = "\n".join(lines)
            return block[:self._max_chars] if len(block) > self._max_chars else block
        except Exception as e:
            logger.debug("ChronosContextProvider error: %s", e)
            return None


class CustomFileProvider(ContextProvider):
    """
    Injects the content of a user-specified file into the system prompt.

    Useful for injecting project-specific instructions, reference docs,
    or dynamic status files that change between sessions.

    Configure via env var HERMES_CONTEXT_FILE=<path> or pass file_path directly.
    """

    slot = "top"
    priority = 5
    name = "custom_file"

    def __init__(self, file_path: Optional[str] = None, slot: str = "top", priority: int = 5):
        self._file_path = file_path or os.getenv("HERMES_CONTEXT_FILE", "")
        self.slot = slot
        self.priority = priority

    def is_available(self) -> bool:
        return bool(self._file_path and os.path.isfile(self._file_path))

    def get_block(self, query: str = "", history=None) -> Optional[str]:
        if not self._file_path:
            return None
        try:
            content = open(self._file_path).read(4000)  # cap at 4K chars
            filename = os.path.basename(self._file_path)
            return f"## Context from {filename}\n{content}"
        except Exception as e:
            logger.debug("CustomFileProvider error reading %s: %s", self._file_path, e)
            return None


class EnvironmentSummaryProvider(ContextProvider):
    """
    Injects a brief environment summary (date, working directory, active profile).
    Helps the agent orient itself in long-running or multi-profile setups.
    """

    slot = "footer"
    priority = 99
    name = "env_summary"

    def is_available(self) -> bool:
        return True

    def get_block(self, query: str = "", history=None) -> Optional[str]:
        import time
        from hermes_constants import display_hermes_home
        date_str = time.strftime("%Y-%m-%d %H:%M %Z")
        cwd = os.getcwd()
        home = display_hermes_home()
        return (
            f"[Context: date={date_str} | cwd={cwd} | hermes_home={home}]"
        )


# ─── Auto-register built-ins based on environment ────────────────────────────

def _auto_register_builtins() -> None:
    """Register built-in providers that have their dependencies satisfied."""
    # Custom file provider (only if env var is set)
    if os.getenv("HERMES_CONTEXT_FILE"):
        p = CustomFileProvider()
        if p.is_available():
            context_engine.register(p)
            logger.debug("Auto-registered CustomFileProvider: %s", p._file_path)

    # Chronos context (only if chronos DB has data — light check)
    try:
        from chronos.temporal_db import _default_db_path
        if _default_db_path().exists():
            context_engine.register(ChronosContextProvider())
            logger.debug("Auto-registered ChronosContextProvider")
    except Exception:
        pass


_auto_register_builtins()
