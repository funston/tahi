import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import build_pagila_fixture_snapshot, snapshot_to_world_model  # noqa: E402
from implementations.spider import (  # noqa: E402
    SpiderLiteSQLBenchmarkAdapter,
    SpiderLiteSQLGenerator,
    SpiderLiteSQLRepairLoop,
    SpiderLiteTask,
)


class SpiderLiteSQLTests(unittest.TestCase):
    def test_generator_builds_customer_rental_sql(self):
        snapshot = build_pagila_fixture_snapshot()
        generator = SpiderLiteSQLGenerator()
        task = SpiderLiteTask(
            task_id="local_customer_rental",
            db_id="pagila_fixture",
            question="Which tables connect customers to the films they rented?",
        )

        draft = generator.generate(
            task=task,
            question="Which tables connect customers to the films they rented?",
            snapshot=snapshot,
            candidate_tables=["customer", "rental", "inventory", "film"],
            candidate_join_path=[
                "customer->rental",
                "rental->inventory",
                "inventory->film",
            ],
        )

        self.assertIn('FROM "customer"', draft.sql)
        self.assertIn('JOIN "rental" ON "customer"."customer_id" = "rental"."customer_id"', draft.sql)
        self.assertIn('JOIN "inventory" ON "rental"."inventory_id" = "inventory"."inventory_id"', draft.sql)
        self.assertIn('JOIN "film" ON "inventory"."film_id" = "film"."film_id"', draft.sql)

    def test_repair_loop_produces_executable_sql_on_synthetic_snapshot(self):
        snapshot = build_pagila_fixture_snapshot()
        repair_loop = SpiderLiteSQLRepairLoop(max_repairs=2)
        task = SpiderLiteTask(
            task_id="local_customer_rental",
            db_id="pagila_fixture",
            question="Which tables connect customers to the films they rented?",
        )

        result = repair_loop.run(
            task=task,
            question="Which tables connect customers to the films they rented?",
            snapshot=snapshot,
            candidate_tables=["customer", "rental", "inventory", "film"],
            candidate_join_path=[
                "customer->rental",
                "rental->inventory",
                "inventory->film",
            ],
            db_path=None,
        )

        self.assertTrue(result["execution_success"])
        self.assertTrue(result["synthetic_db_used"])
        self.assertIn('JOIN "film"', result["sql"])

    def test_sql_benchmark_adapter_runs_end_to_end(self):
        snapshot = build_pagila_fixture_snapshot()
        world = snapshot_to_world_model(snapshot)
        adapter = SpiderLiteSQLBenchmarkAdapter(
            snapshots_by_db={"pagila_fixture": snapshot},
            worlds_by_db={"pagila_fixture": world},
            top_k=8,
            max_repairs=2,
        )
        task = SpiderLiteTask(
            task_id="task-1",
            db_id="pagila_fixture",
            question="Which tables connect customers to the films they rented?",
            gold_tables=["customer", "rental", "inventory", "film"],
        )

        result = adapter.run_task(task)
        summary = adapter.evaluate_tasks([task])

        self.assertEqual(result["table_recall"], 1.0)
        self.assertTrue(result["execution_success"])
        self.assertIsNotNone(summary["executable_sql_rate"])
        self.assertEqual(summary["executable_sql_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
