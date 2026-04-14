#!/usr/bin/env python3
"""
Chronos Entity Graph — MiroFish-inspired world model

Before running simulations, Chronos extracts a lightweight knowledge graph
from the goal and context. This makes each simulated future concrete:
instead of varying generic parameters ("time_pressure: urgent"), simulations
reference *specific actors and relationships* from the real situation.

MiroFish insight: simulation quality rises dramatically when agents play
specific roles (Alice the skeptical CFO, Competitor B, Supplier Acme) rather
than abstract archetypes (resource_level: constrained).

Pipeline:
    Goal + Context
         │
    EntityExtractor.extract()
         │  LLM: extract entities + relationships as JSON
         ▼
    EntityGraph
         │  entities: [CFO, CTO, Competitor, Regulator, ...]
         │  relationships: [CFO opposes CTO, Competitor threatens Goal, ...]
         ▼
    ScenarioSeed (entity_states + key_actor + relationship_shift)
         │
    Simulator.run() — richer, more specific simulations
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────

ENTITY_TYPES = (
    "person",           # individual human actor
    "organization",     # company, team, department
    "resource",         # money, time, tool, technology
    "constraint",       # rule, regulation, deadline, dependency
    "opportunity",      # market window, alliance, trend
    "risk",             # threat, blocker, uncertainty
)

RELATIONSHIP_TYPES = (
    "supports",         # A actively helps B succeed
    "opposes",          # A actively blocks B
    "controls",         # A has authority over B
    "depends_on",       # A requires B to function
    "competes_with",    # A and B have conflicting goals
    "influences",       # A shapes B's behavior
    "provides",         # A supplies resource to B
    "threatens",        # A is a risk to B
)

# Possible states an entity can be in for a given simulation
ENTITY_STATES = {
    "person":       ["supportive", "skeptical", "neutral", "unavailable", "opposed", "overloaded"],
    "organization": ["aligned", "bureaucratic", "agile", "restructuring", "hostile", "acquired"],
    "resource":     ["abundant", "adequate", "constrained", "depleted", "blocked"],
    "constraint":   ["enforced", "relaxed", "waived", "escalating", "ignored"],
    "opportunity":  ["open", "closing", "closed", "expanding", "contested"],
    "risk":         ["dormant", "emerging", "active", "mitigated", "materialized"],
}


@dataclass
class Entity:
    id: str
    name: str
    type: str                          # from ENTITY_TYPES
    role: str                          # what role this entity plays for the goal
    current_state: str = "unknown"     # baseline state
    attributes: Dict[str, str] = field(default_factory=dict)

    def possible_states(self) -> List[str]:
        return ENTITY_STATES.get(self.type, ["active", "inactive", "unstable"])

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Relationship:
    source_id: str
    target_id: str
    type: str                    # from RELATIONSHIP_TYPES
    strength: float = 0.5        # 0.0 weak → 1.0 strong
    description: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EntityGraph:
    goal: str
    entities: List[Entity] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)

    # ─── convenience accessors ───────────────────────────────────────

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None

    def get_by_type(self, entity_type: str) -> List[Entity]:
        return [e for e in self.entities if e.type == entity_type]

    def get_relationships(self, entity_id: str) -> List[Relationship]:
        return [r for r in self.relationships
                if r.source_id == entity_id or r.target_id == entity_id]

    def key_actors(self) -> List[Entity]:
        """Entities that appear most frequently in relationships — most influential."""
        from collections import Counter
        counts: Counter = Counter()
        for r in self.relationships:
            counts[r.source_id] += 1
            counts[r.target_id] += 1
        top_ids = [eid for eid, _ in counts.most_common(5)]
        return [e for e in self.entities if e.id in top_ids]

    def blocking_relationships(self) -> List[Relationship]:
        return [r for r in self.relationships
                if r.type in ("opposes", "threatens", "competes_with")]

    def enabling_relationships(self) -> List[Relationship]:
        return [r for r in self.relationships
                if r.type in ("supports", "provides", "influences")]

    def summary(self) -> str:
        lines = [f"Goal: {self.goal}", f"Entities ({len(self.entities)}):"]
        for e in self.entities[:8]:
            lines.append(f"  [{e.type}] {e.name} — {e.role}")
        if self.relationships:
            lines.append(f"Relationships ({len(self.relationships)}):")
            for r in self.relationships[:6]:
                src = self.get_entity(r.source_id)
                tgt = self.get_entity(r.target_id)
                if src and tgt:
                    lines.append(f"  {src.name} {r.type} {tgt.name} (strength: {r.strength:.1f})")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "goal": self.goal,
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
        }


# ─────────────────────────────────────────────
# Extractor
# ─────────────────────────────────────────────

_EXTRACTION_SYSTEM = """\
You are a world-model extractor. Given a goal and context, identify the key
entities (actors, resources, constraints, risks, opportunities) and their
relationships that will determine whether the goal succeeds or fails.

Output a JSON object with:
  entities: array of {
    id: "e_001" (sequential),
    name: string (specific name, not generic),
    type: one of [person, organization, resource, constraint, opportunity, risk],
    role: string (1 sentence: what role in achieving the goal),
    current_state: string (baseline condition today),
    attributes: object (key facts, e.g. {"budget": "50k", "timeline": "3 months"})
  }
  relationships: array of {
    source_id: string,
    target_id: string,
    type: one of [supports, opposes, controls, depends_on, competes_with,
                  influences, provides, threatens],
    strength: float 0.0-1.0,
    description: string (1 sentence)
  }

Rules:
- Be SPECIFIC: "Sarah (VP Sales)" not "a stakeholder"
- 4-10 entities max; 3-10 relationships max
- Focus on entities that can CHANGE and INFLUENCE the outcome
- Output ONLY valid JSON
"""


class EntityExtractor:
    """
    Extracts a world-model (entity graph) from a goal + context string.
    The graph feeds directly into ScenarioSimulator to make futures specific.
    """

    def __init__(self, model: Optional[str] = None):
        self._model = model

    def extract(self, goal: str, context: str = "") -> EntityGraph:
        """
        Extract entities and relationships from goal + context.

        Returns an EntityGraph. On failure, returns an empty graph
        (simulator degrades gracefully to generic seeds).
        """
        from agent.auxiliary_client import call_llm

        user_content = f"GOAL: {goal}"
        if context.strip():
            user_content += f"\n\nCONTEXT:\n{context}"

        try:
            response = call_llm(
                task="session_search",
                model=self._model,
                messages=[
                    {"role": "system", "content": _EXTRACTION_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                max_tokens=1200,
            )
            raw = response.choices[0].message.content or ""
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]

            parsed = json.loads(raw)
            return self._build_graph(goal, parsed)

        except Exception as e:
            logger.warning("EntityExtractor failed (using generic seeds): %s", e)
            return EntityGraph(goal=goal)

    def _build_graph(self, goal: str, parsed: Dict) -> EntityGraph:
        graph = EntityGraph(goal=goal)

        for raw_e in parsed.get("entities", []):
            entity = Entity(
                id=str(raw_e.get("id", f"e_{len(graph.entities):03d}")),
                name=str(raw_e.get("name", "Unknown")),
                type=str(raw_e.get("type", "person")),
                role=str(raw_e.get("role", "")),
                current_state=str(raw_e.get("current_state", "unknown")),
                attributes=dict(raw_e.get("attributes", {})),
            )
            graph.entities.append(entity)

        entity_ids = {e.id for e in graph.entities}
        for raw_r in parsed.get("relationships", []):
            src = str(raw_r.get("source_id", ""))
            tgt = str(raw_r.get("target_id", ""))
            if src not in entity_ids or tgt not in entity_ids:
                continue
            rel = Relationship(
                source_id=src,
                target_id=tgt,
                type=str(raw_r.get("type", "influences")),
                strength=float(raw_r.get("strength", 0.5)),
                description=str(raw_r.get("description", "")),
            )
            graph.relationships.append(rel)

        logger.info(
            "EntityGraph: %d entities, %d relationships",
            len(graph.entities),
            len(graph.relationships),
        )
        return graph


# ─────────────────────────────────────────────
# Entity-aware seed generation
# ─────────────────────────────────────────────

def generate_entity_seeds(graph: EntityGraph, n: int) -> List[Dict]:
    """
    Generate N scenario variants based on the entity graph.

    Each variant specifies:
    - entity_states: which state each entity is in for this simulation
    - key_actor: which entity drives this scenario (whose action matters most)
    - relationship_shift: which relationship flips direction

    Returns list of dicts (merged into ScenarioSeed.entity_context).
    """
    import random

    seeds = []
    entities = graph.entities
    relationships = graph.relationships

    for i in range(n):
        # Vary entity states
        entity_states = {}
        for e in entities:
            states = e.possible_states()
            # Bias toward "harder" states in later simulations to stress-test
            if i < n // 3:
                # First third: optimistic (good states)
                state = states[0]
            elif i < 2 * n // 3:
                # Middle third: random
                state = random.choice(states)
            else:
                # Last third: pessimistic (challenging states)
                state = states[-1] if len(states) > 1 else random.choice(states)
            entity_states[e.id] = state

        # Pick a key actor for this scenario
        key_actors = graph.key_actors()
        key_actor = key_actors[i % len(key_actors)] if key_actors else None

        # Pick a relationship to stress-test
        rel_shift = None
        if relationships:
            rel = relationships[i % len(relationships)]
            src = graph.get_entity(rel.source_id)
            tgt = graph.get_entity(rel.target_id)
            if src and tgt:
                # Flip enabling → blocking or vice versa for variety
                if rel.type in ("supports", "provides"):
                    flipped = "withholds" if i % 2 == 0 else "supports"
                elif rel.type in ("opposes", "threatens"):
                    flipped = "neutralized" if i % 2 == 0 else "escalates"
                else:
                    flipped = rel.type
                rel_shift = f"{src.name} {flipped} {tgt.name}"

        seeds.append({
            "entity_states": entity_states,
            "key_actor_id": key_actor.id if key_actor else None,
            "key_actor_name": key_actor.name if key_actor else None,
            "relationship_shift": rel_shift or "",
        })

    return seeds


def format_entity_context(
    graph: EntityGraph,
    seed: Dict,
) -> str:
    """
    Format entity states into a rich scenario description for LLM simulation prompt.
    """
    lines = ["WORLD MODEL:"]

    entity_states = seed.get("entity_states", {})
    for e in graph.entities:
        state = entity_states.get(e.id, e.current_state)
        lines.append(f"  [{e.type}] {e.name}: {state} — {e.role}")

    if seed.get("key_actor_name"):
        lines.append(f"\nKEY ACTOR THIS SCENARIO: {seed['key_actor_name']}")

    if seed.get("relationship_shift"):
        lines.append(f"RELATIONSHIP SHIFT: {seed['relationship_shift']}")

    # Add critical relationships
    blocking = graph.blocking_relationships()
    if blocking:
        lines.append("\nACTIVE TENSIONS:")
        for r in blocking[:3]:
            src = graph.get_entity(r.source_id)
            tgt = graph.get_entity(r.target_id)
            if src and tgt:
                lines.append(f"  {src.name} {r.type} {tgt.name}: {r.description}")

    return "\n".join(lines)
