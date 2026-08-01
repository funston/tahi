from __future__ import annotations

import unittest
from pathlib import Path

from octo.compiler.sql import SQLCompilerPipeline
from octo.repair.sql import SQLRepairLoop
from octo.validators.sql import SQLResultMatcher


class StubEngine:
    def __init__(self, results: dict[str, tuple[list[dict[str, object]], str | None]]):
        self.results = results

    def execute(self, sql: str) -> tuple[list[dict[str, object]], str | None]:
        return self.results[sql]


class SQLValidationAndRepairTests(unittest.TestCase):
    def test_matcher_tolerates_numeric_text(self) -> None:
        matcher = SQLResultMatcher(gold_loader=lambda _: [{"value": "4.85"}])
        validation = matcher.validate(
            rows=[{"VALUE": 4.85}],
            execution_error=None,
            gold_paths=[Path("/tmp/gold.csv")],
        )
        self.assertTrue(validation.execution_success)
        self.assertTrue(validation.matched_gold)

    def test_repair_loop_promotes_successful_repair(self) -> None:
        matcher = SQLResultMatcher(gold_loader=lambda _: [{"value": "ok"}])
        engine = StubEngine(
            {
                "bad": ([], "syntax error"),
                "fixed": ([{"VALUE": "ok"}], None),
            }
        )
        loop = SQLRepairLoop(engine=engine, matcher=matcher)
        outcome = loop.run(
            initial_sql="bad",
            gold_paths=[Path("/tmp/gold.csv")],
            repair_candidates=[("fixed", "retry_with_fix")],
        )
        self.assertEqual(outcome.sql, "fixed")
        self.assertTrue(outcome.validation.execution_success)
        self.assertTrue(outcome.validation.matched_gold)
        self.assertEqual(len(outcome.attempts), 1)
        self.assertEqual(outcome.attempts[0].label, "retry_with_fix")

    def test_compiler_pipeline_wraps_repair_loop(self) -> None:
        matcher = SQLResultMatcher(gold_loader=lambda _: [{"value": "ok"}])
        engine = StubEngine(
            {
                "bad": ([], "syntax error"),
                "fixed": ([{"VALUE": "ok"}], None),
            }
        )
        pipeline = SQLCompilerPipeline(engine=engine, matcher=matcher)
        outcome = pipeline.compile(
            initial_sql="bad",
            gold_paths=[Path("/tmp/gold.csv")],
            repair_candidates=[("fixed", "retry_with_fix")],
        )
        self.assertEqual(outcome.sql, "fixed")
        self.assertTrue(outcome.validation.matched_gold)


if __name__ == "__main__":
    unittest.main()
