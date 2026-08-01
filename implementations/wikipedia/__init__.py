""" Wikipedia multi-hop QA world coprocessor for BENDER."""

from .wikipedia_coprocessor import (
    WikipediaCoprocessor,
    WikipediaPlanner,
    WikipediaRuleEngine,
)

__all__ = [
    "WikipediaCoprocessor",
    "WikipediaPlanner",
    "WikipediaRuleEngine",
]
