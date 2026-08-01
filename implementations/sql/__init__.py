"""
Generic SQL Schema Reasoning

This package provides domain-agnostic SQL schema reasoning components.

Note: This is still somewhat generic (not tied to a specific database),
but contains heuristics like "rental/film" patterns that may be Pagila-specific.

Components:
- SQLSchemaPlanner: Plans queries over SQL schemas
- SQLSchemaRuleEngine: Applies SQL-specific rules
- SQLSchemaCoprocessor: Combines planner + rules for SQL tasks

Usage:
    from implementations.sql import SQLSchemaCoprocessor
    from octo import snapshot_to_world_model

    coprocessor = SQLSchemaCoprocessor.from_snapshot(
        snapshot,
        model_name="my_db",
    )
    result = coprocessor.ask("Find customers who rented films")
"""

from .sql_coprocessor import (
    SQLSchemaCoprocessor,
    SQLSchemaPlanner,
    SQLSchemaRuleEngine,
)

__all__ = [
    "SQLSchemaCoprocessor",
    "SQLSchemaPlanner",
    "SQLSchemaRuleEngine",
]
