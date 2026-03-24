import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from bender import build_pagila_fixture_snapshot
from implementations.spider import SpiderSchemaCoprocessor


class SpiderSchemaCoprocessorTests(unittest.TestCase):
    def test_actor_film_query_produces_schema_constraints(self):
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            build_pagila_fixture_snapshot(),
            top_k=10,
        )

        result = coprocessor.ask("Which actors appeared in Action films?", trace=True)

        self.assertEqual(result["mode"], "coprocessor")
        self.assertIn("query_intent", result["constraints"])
        self.assertIn("candidate_tables", result["constraints"])
        self.assertTrue(result["hypotheses"])
        references = {item["reference"] for item in result["provenance"]}
        self.assertIn("planner:spider_schema", references)

    def test_customer_rental_query_surfaces_join_guidance(self):
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            build_pagila_fixture_snapshot(),
            top_k=10,
        )

        result = coprocessor.ask(
            "List customers and the films they rented.",
            trace=True,
        )

        hypotheses = " ".join(item["text"] for item in result["hypotheses"]).lower()
        self.assertIn("customer", hypotheses)
        self.assertIn("rental", hypotheses)
        self.assertIn("candidate_tables", result["constraints"])
        self.assertIn("inventory", result["constraints"]["candidate_tables"])
        self.assertIn("film", result["constraints"]["candidate_tables"])
        self.assertEqual(
            result["constraints"].get("candidate_join_path"),
            ["customer->rental", "rental->inventory", "inventory->film"],
        )

    def test_payment_query_surfaces_join_guidance(self):
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            build_pagila_fixture_snapshot(),
            top_k=10,
        )

        result = coprocessor.ask(
            "List the tables connecting payments to customers and rentals.",
            trace=True,
        )

        self.assertIn("payment_p2007_01", result["constraints"]["candidate_tables"])
        self.assertEqual(
            result["constraints"].get("candidate_join_path"),
            ["payment_p2007_01->rental", "rental->customer"],
        )


if __name__ == "__main__":
    unittest.main()
