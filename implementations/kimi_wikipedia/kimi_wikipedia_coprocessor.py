"""
kimi_wikipedia_coprocessor.py

A BENDER world coprocessor for Wikipedia multi-hop QA.

It combines:
  - semantic retrieval over pages/chunks (vector index)
  - deterministic graph traversal over wiki links and entity relations
  - evidence chunk retrieval along traversed paths
  - structured control packet generation for downstream LLM answering

No existing files are modified.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Any, Optional

from bender.adapter import WrappedLLM, wrap_llm
from bender.integration import BlackBoxIntegration, ModelIntegration
from bender.models import CognitiveState, EntityRef, Hypothesis
from bender.planner import Planner
from bender.rules import RuleEngine
from bender.world_state import WorldModel


# ---------------------------------------------------------------------------
# Query analysis
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[a-z0-9_']+", re.IGNORECASE)


def query_terms(query: str) -> set[str]:
    return set(WORD_RE.findall(query.lower()))


def classify_hop_type(query: str) -> str:
    lowered = query.lower()
    if any(t in lowered for t in ("capital", "city", "country", "born", "nationality")):
        return "geographic"
    if any(t in lowered for t in ("author", "wrote", "written by", "directed by", "composed by")):
        return "authorship"
    if any(t in lowered for t in ("when", "year", "date", "born", "died", "founded")):
        return "temporal"
    return "generic"


# ---------------------------------------------------------------------------
# Graph traversal
# ---------------------------------------------------------------------------

def traverse_graph(
    world_model: WorldModel,
    start_node_id: str,
    target_terms: set[str],
    seed_ids: set[str] | None = None,
    max_depth: int = 4,
    max_width: int = 20,
) -> list[list[str]]:
    """
    Breadth-first search over wiki_page links and entity relations.
    Returns paths (lists of node IDs) whose final node label matches target terms
    and is not a seed entity.
    """
    seed_ids = seed_ids or set()
    paths: list[list[str]] = []
    visited: set[tuple[str, ...]] = set()
    output_paths: set[tuple[str, ...]] = set()
    queue: deque[tuple[str, list[str]]] = deque([(start_node_id, [start_node_id])])
    visited.add((start_node_id,))

    while queue and len(paths) < max_width:
        current, path = queue.popleft()
        # max_depth is the number of edges from start; path length is nodes
        if len(path) - 1 > max_depth:
            continue

        # check if current node looks like an answer candidate (and is not the seed)
        if current not in seed_ids or len(path) > 1:
            node = world_model.nodes.get(current, {})
            label = (node.get("label", "") + " " + node.get("summary", "")).lower()
            if target_terms and target_terms & set(label.split()):
                path_tuple = tuple(path)
                if path_tuple not in output_paths:
                    output_paths.add(path_tuple)
                    paths.append(path)

        # expand neighbors
        for src, rel, dst, attrs in world_model.neighbors(current):
            neighbor = dst if src == current else src
            if neighbor in path:
                continue
            new_path = path + [neighbor]
            path_tuple = tuple(new_path)
            if path_tuple not in visited:
                visited.add(path_tuple)
                queue.append((neighbor, new_path))

    return paths


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class KimiWikipediaPlanner(Planner):
    """Planner for Wikipedia multi-hop QA."""

    def __init__(self, world_model: WorldModel | None = None, max_hops: int = 4):
        self.world_model = world_model
        self.max_hops = max_hops

    def plan(self, query: str, state: CognitiveState) -> CognitiveState:
        super().plan(query, state)

        terms = query_terms(query)
        hop_type = classify_hop_type(query)
        state.planner_state["query_terms"] = sorted(terms)
        state.planner_state["hop_type"] = hop_type
        state.planner_state["max_hops"] = self.max_hops

        # If retrieval produced no seed entities, fall back to direct title matching
        if self.world_model is not None and not state.entities:
            for node_id, node in self.world_model.nodes.items():
                if node.get("type") != "wiki_page":
                    continue
                title = node.get("title", "").lower()
                if title and any(term in title for term in terms):
                    state.entities.append(
                        EntityRef(
                            id=node_id,
                            label=node.get("label", node_id),
                            type="wiki_page",
                            score=1.0,
                            attributes=dict(node),
                        )
                    )
                    if len(state.entities) >= 3:
                        break

        # If we have a world model and seed entities, try to plan traversal targets
        if self.world_model is not None and state.entities:
            seed_ids = {entity.id for entity in state.entities}
            target_terms = self._target_terms(query)
            candidate_paths: list[list[str]] = []
            for seed_entity in state.entities[:3]:
                paths = traverse_graph(
                    self.world_model,
                    seed_entity.id,
                    target_terms,
                    seed_ids=seed_ids,
                    max_depth=self.max_hops,
                )
                candidate_paths.extend(paths)

            # rank by path length and term overlap (prefer shorter paths)
            candidate_paths.sort(key=lambda p: (len(p), self._path_score(p, target_terms)))
            state.planner_state["candidate_paths"] = candidate_paths[:8]

        state.planner_state["steps"] = [
            "capture semantic frame",
            "retrieve seed wiki pages",
            f"plan {hop_type} multi-hop traversal",
            "traverse entity/link graph",
            "retrieve evidence chunks",
            "fuse graph signal",
            "generate answer",
        ]
        state.add_provenance(
            "planner",
            "planner:kimi_wikipedia",
            f"Planned {hop_type} multi-hop traversal up to {self.max_hops} hops.",
        )
        return state

    def _target_terms(self, query: str) -> set[str]:
        # crude target extraction: wh-words and trailing noun phrases
        lowered = query.lower()
        # remove leading wh- phrase
        lowered = re.sub(r"^(what|which|who|where|when|how|why)\s+(is|are|was|were|do|does|did|can|could|would|will)\s+", "", lowered)
        lowered = re.sub(r"^(what|which|who|where|when|how|why)\s+", "", lowered)
        return query_terms(lowered)

    def _path_score(self, path: list[str], target_terms: set[str]) -> float:
        score = 0.0
        for node_id in path:
            node = self.world_model.nodes.get(node_id, {}) if self.world_model else {}
            text = (node.get("label", "") + " " + node.get("summary", "")).lower()
            score += len(target_terms & set(text.split()))
        return -score


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

class KimiWikipediaRuleEngine(RuleEngine):
    """Rule engine for Wikipedia multi-hop QA."""

    def __init__(self, world_model: WorldModel | None = None):
        self.world_model = world_model

    def apply(self, state: CognitiveState) -> CognitiveState:
        # Tag entities by semantic role
        for entity in state.entities:
            label = entity.label.lower()
            if any(t in label for t in ("city", "capital", "country", "state", "river", "mountain")):
                entity.attributes["semantic_role"] = "geographic"
            elif any(t in label for t in ("book", "novel", "film", "movie", "song", "album", "paper")):
                entity.attributes["semantic_role"] = "work"
            elif any(t in label for t in ("author", "writer", "director", "composer", "scientist", "politician")):
                entity.attributes["semantic_role"] = "person"

        # Extract candidate paths from planner
        candidate_paths = state.planner_state.get("candidate_paths", [])
        if candidate_paths:
            best_path = candidate_paths[0]
            path_labels = [
                self.world_model.nodes.get(node_id, {}).get("label", node_id)
                if self.world_model else node_id
                for node_id in best_path
            ]
            state.constraints["candidate_path"] = best_path
            state.constraints["candidate_path_labels"] = path_labels
            state.hypotheses.append(
                Hypothesis(
                    text=f"Best inferred path: {' → '.join(path_labels)}.",
                    confidence=0.75,
                    evidence=["planner:kimi_wikipedia", "rule:path_selection"],
                    kind="multi_hop_path",
                )
            )
            state.add_provenance(
                "reasoning",
                "rule:path_selection",
                f"Selected top graph path with {len(best_path)} nodes.",
                confidence=0.75,
            )

        # Surface bridge entities (intermediate nodes)
        for path in candidate_paths[:3]:
            if len(path) >= 3:
                bridge = path[len(path) // 2]
                bridge_label = (
                    self.world_model.nodes.get(bridge, {}).get("label", bridge)
                    if self.world_model else bridge
                )
                state.hypotheses.append(
                    Hypothesis(
                        text=f"Bridge entity candidate: {bridge_label}.",
                        confidence=0.70,
                        evidence=["rule:bridge_entity"],
                        kind="bridge_entity",
                    )
                )

        return state


# ---------------------------------------------------------------------------
# Coprocessor wrapper
# ---------------------------------------------------------------------------

class KimiWikipediaCoprocessor:
    """End-to-end BENDER coprocessor for Wikipedia multi-hop QA."""

    def __init__(self, model: WrappedLLM, world_model: WorldModel):
        self.model = model
        self.world_model = world_model

    @classmethod
    def from_world_model(
        cls,
        world_model: WorldModel,
        *,
        model_name: str = "kimi-wikipedia-demo",
        integration: ModelIntegration | None = None,
        top_k: int = 8,
        max_hops: int = 4,
    ) -> "KimiWikipediaCoprocessor":
        integration = integration or BlackBoxIntegration()
        model = wrap_llm(
            model_name,
            world_model=world_model,
            integration=integration,
            planner=KimiWikipediaPlanner(world_model=world_model, max_hops=max_hops),
            rules=KimiWikipediaRuleEngine(world_model=world_model),
            top_k=top_k,
        )
        return cls(model=model, world_model=world_model)

    def ask(self, query: str, *, trace: bool = False) -> dict[str, Any]:
        return self.model.ask(query, mode="coprocessor", trace=trace)

    def generate_answer(self, query: str, *, llm_generate_fn=None) -> dict[str, Any]:
        """
        Run the coprocessor and optionally call an LLM to produce a final answer.

        llm_generate_fn: callable(prompt: str) -> str
        If not provided, returns the control packet only.
        """
        state_result = self.ask(query, trace=True)

        answer: Optional[str] = None
        if llm_generate_fn is not None:
            prompt = self._build_answer_prompt(query, state_result)
            answer = llm_generate_fn(prompt)

        return {
            "query": query,
            "answer": answer,
            "control_packet": state_result.get("control_packet"),
            "entities": state_result.get("entities"),
            "relations": state_result.get("relations"),
            "hypotheses": state_result.get("hypotheses"),
            "candidate_path": state_result.get("constraints", {}).get("candidate_path"),
            "candidate_path_labels": state_result.get("constraints", {}).get("candidate_path_labels"),
            "provenance": state_result.get("provenance"),
        }

    def _build_answer_prompt(self, query: str, state_result: dict[str, Any]) -> str:
        entities = state_result.get("entities", [])
        hypotheses = state_result.get("hypotheses", [])
        path_labels = state_result.get("constraints", {}).get("candidate_path_labels", [])

        lines = [
            "You are answering a question using retrieved Wikipedia evidence.",
            "",
            f"Question: {query}",
            "",
        ]
        if path_labels:
            lines.append("Inferred entity path: " + " → ".join(path_labels))
            lines.append("")
        if entities:
            lines.append("Retrieved entities:")
            for entity in entities[:10]:
                lines.append(f"  - {entity}")
            lines.append("")
        if hypotheses:
            lines.append("Reasoning hypotheses:")
            for hypothesis in hypotheses[:6]:
                lines.append(f"  - {hypothesis.get('text', '')} (confidence: {hypothesis.get('confidence', '')})")
            lines.append("")
        lines.append("Answer the question concisely using only the retrieved evidence.")
        return "\n".join(lines)
