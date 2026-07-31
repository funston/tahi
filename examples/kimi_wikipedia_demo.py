#!/usr/bin/env python3
"""
kimi_wikipedia_demo.py

Demo the Kimi Wikipedia multi-hop QA coprocessor on a small synthetic Wikipedia graph.

Usage:
  PYTHONPATH=src:. python examples/kimi_wikipedia_demo.py

No existing files are modified.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from implementations.kimi_wikipedia import KimiWikipediaCoprocessor
from bender.world_state import WorldModel


def build_tiny_wikipedia_world() -> WorldModel:
    """Hand-construct a tiny multi-hop world model for demo purposes."""
    world = WorldModel(domain="kimi_wikipedia_demo", use_ann=False)

    pages = [
        ("page:pride_prejudice", "Pride and Prejudice", "Pride and Prejudice is a novel by Jane Austen."),
        ("page:jane_austen", "Jane Austen", "Jane Austen was an English novelist born in Steventon."),
        ("page:steventon", "Steventon", "Steventon is a village in Hampshire, England."),
        ("page:hampshire", "Hampshire", "Hampshire is a county on the southern coast of England."),
        ("page:england", "England", "England is a country that is part of the United Kingdom."),
        ("page:london", "London", "London is the capital city of England and the United Kingdom."),
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

    # links
    links = [
        ("page:pride_prejudice", "page:jane_austen"),
        ("page:jane_austen", "page:steventon"),
        ("page:steventon", "page:hampshire"),
        ("page:hampshire", "page:england"),
        ("page:england", "page:london"),
    ]
    for src, dst in links:
        world.add_edge(src, "links_to", dst, score=0.95)

    # entities
    entities = [
        ("entity:jane_austen", "Jane Austen", "person"),
        ("entity:england", "England", "place"),
        ("entity:london", "London", "place"),
    ]
    for node_id, label, entity_type in entities:
        world.upsert_node(
            node_id,
            label=label,
            type="wiki_entity",
            summary=f"{label} is a {entity_type}.",
            keywords=[label.lower()],
        )

    world.add_edge("page:jane_austen", "mentions", "entity:jane_austen", score=0.90)
    world.add_edge("page:england", "mentions", "entity:england", score=0.90)
    world.add_edge("page:london", "mentions", "entity:london", score=0.90)

    world.build_index()
    return world


def main() -> None:
    world = build_tiny_wikipedia_world()
    coprocessor = KimiWikipediaCoprocessor.from_world_model(world, top_k=5, max_hops=4)

    questions = [
        "What is the capital of the country where Jane Austen was born?",
        "Where was the author of Pride and Prejudice born?",
    ]

    for question in questions:
        print("=" * 60)
        print(f"Question: {question}")
        result = coprocessor.generate_answer(question)
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    main()
