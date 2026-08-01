import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import build_pagila_fixture_snapshot, snapshot_to_world_model
from implementations.sql import SQLSchemaCoprocessor


class DatabaseCoprocessorTests(unittest.TestCase):
    def test_pagila_fixture_snapshot_builds_world_model(self):
        snapshot = build_pagila_fixture_snapshot()
        world_model = snapshot_to_world_model(snapshot)

        self.assertEqual(snapshot.database_name, "pagila_fixture")
        self.assertIn("database:pagila_fixture", world_model.nodes)
        self.assertIn("table:public.actor", world_model.nodes)
        self.assertIn("column:public.actor.first_name", world_model.nodes)
        self.assertIn("table:public.rental", world_model.nodes)

        edge_types = {(src, rel, dst) for src, rel, dst, _ in world_model.edges}
        self.assertIn(
            ("table:public.rental", "references_table", "table:public.customer"),
            edge_types,
        )
        self.assertIn(
            ("table:public.film_actor", "references_table", "table:public.actor"),
            edge_types,
        )

    def test_sql_coprocessor_finds_customer_rental_inventory_film_path(self):
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            build_pagila_fixture_snapshot(),
            top_k=10,
        )

        result = coprocessor.ask(
            "Which tables connect customers to the films they rented?",
            trace=True,
        )

        self.assertEqual(
            result["constraints"].get("candidate_join_path"),
            ["customer->rental", "rental->inventory", "inventory->film"],
        )
        self.assertEqual(
            result["constraints"].get("recommended_bridge_tables"),
            ["rental", "inventory"],
        )

    def test_sql_coprocessor_finds_actor_to_category_film_path(self):
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            build_pagila_fixture_snapshot(),
            top_k=10,
        )

        result = coprocessor.ask(
            "Which tables connect actors to film categories?",
            trace=True,
        )

        self.assertEqual(
            result["constraints"].get("candidate_join_path"),
            [
                "actor->film_actor",
                "film_actor->film",
                "film->film_category",
                "film_category->category",
            ],
        )
        self.assertEqual(
            result["constraints"].get("recommended_bridge_tables"),
            ["film_actor", "film", "film_category"],
        )

    def test_sql_coprocessor_finds_payment_customer_rental_path(self):
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            build_pagila_fixture_snapshot(),
            top_k=10,
        )

        result = coprocessor.ask(
            "Which tables connect customer payments to rentals?",
            trace=True,
        )

        self.assertEqual(
            result["constraints"].get("candidate_join_path"),
            [
                "payment_p2007_01->rental",
                "rental->customer",
            ],
        )
        self.assertEqual(
            result["constraints"].get("recommended_bridge_tables"),
            ["rental"],
        )


if __name__ == "__main__":
    unittest.main()
