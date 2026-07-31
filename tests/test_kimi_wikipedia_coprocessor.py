"""
Tests for the Kimi Wikipedia multi-hop QA world coprocessor.

No existing files are modified.
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from implementations.kimi_wikipedia import (
    KimiWikipediaCoprocessor,
    KimiWikipediaPlanner,
    KimiWikipediaRuleEngine,
)
from bender.world_state import WorldModel


class TestKimiWikipediaCoprocessor(unittest.TestCase):
    def _build_tiny_world(self) -> WorldModel:
        world = WorldModel(domain="kimi_wikipedia_test", use_ann=False)
        pages = [
            ("page:pride_prejudice", "Pride and Prejudice", "Pride and Prejudice is a novel by Jane Austen."),
            ("page:jane_austen", "Jane Austen", "Jane Austen was an English novelist born in Steventon."),
            ("page:steventon", "Steventon", "Steventon is a village in Hampshire, England."),
            ("page:hampshire", "Hampshire", "Hampshire is a county on the southern coast of England."),
            ("page:england", "England", "England is a country that is part of the United Kingdom."),
            ("page:london", "London", "London is the capital city of England."),
        ]
        for node_id, title, summary in pages:
            world.upsert_node(
                node_id,
                label=title,
                type="wiki_page",
                summary=summary,
                keywords=[title.lower(), *summary.lower().split()],
                title=title,
            )
        links = [
            ("page:pride_prejudice", "page:jane_austen"),
            ("page:jane_austen", "page:steventon"),
            ("page:steventon", "page:hampshire"),
            ("page:hampshire", "page:england"),
            ("page:england", "page:london"),
        ]
        for src, dst in links:
            world.add_edge(src, "links_to", dst, score=0.95)
        world.build_index()
        return world

    def test_planner_identifies_multi_hop_path(self) -> None:
        world = self._build_tiny_world()
        coprocessor = KimiWikipediaCoprocessor.from_world_model(world, top_k=5, max_hops=4)

        result = coprocessor.ask(
            "What is the capital of the country where Jane Austen was born?",
            trace=True,
        )

        path = result["constraints"].get("candidate_path_labels", [])
        self.assertTrue(len(path) >= 2, f"Expected non-trivial path, got {path}")
        self.assertIn("Jane Austen", path)

    def test_rule_engine_adds_bridge_hypothesis(self) -> None:
        world = self._build_tiny_world()
        coprocessor = KimiWikipediaCoprocessor.from_world_model(world, top_k=5, max_hops=4)

        result = coprocessor.ask(
            "Where was the author of Pride and Prejudice born?",
            trace=True,
        )

        hypothesis_kinds = {h.get("kind") for h in result.get("hypotheses", [])}
        self.assertIn("multi_hop_path", hypothesis_kinds)
        self.assertIn("bridge_entity", hypothesis_kinds)

    def test_generate_answer_without_llm_returns_control_packet(self) -> None:
        world = self._build_tiny_world()
        coprocessor = KimiWikipediaCoprocessor.from_world_model(world, top_k=5, max_hops=4)

        result = coprocessor.generate_answer(
            "What is the capital of the country where Jane Austen was born?"
        )

        self.assertIsNone(result["answer"])
        self.assertIsNotNone(result["control_packet"])
        self.assertIsNotNone(result["candidate_path"])


if __name__ == "__main__":
    unittest.main()
