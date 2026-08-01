import json
import os
import sqlite3
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import build_pagila_fixture_snapshot, snapshot_to_world_model  # noqa: E402
from implementations.spider import (  # noqa: E402
    SpiderLiteBenchmarkAdapter,
    SpiderLiteSQLiteDatabaseLoader,
    SpiderLiteSQLiteMetadataLoader,
    SpiderLiteTaskLoader,
    SpiderLiteWorkspace,
    enrich_world_with_spider_sqlite_metadata,
)


class SpiderLiteTests(unittest.TestCase):
    def test_loader_supports_jsonl(self):
        payload = {
            "instance_id": "task-1",
            "db_id": "pagila_fixture",
            "question": "Which tables connect customers to the films they rented?",
            "gold_tables": ["customer", "rental", "inventory", "film"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tasks.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")

            tasks = SpiderLiteTaskLoader().load(path)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "task-1")
        self.assertEqual(tasks[0].db_id, "pagila_fixture")
        self.assertEqual(tasks[0].gold_tables, ["customer", "rental", "inventory", "film"])

    def test_adapter_runs_task_against_registered_snapshot(self):
        world = snapshot_to_world_model(build_pagila_fixture_snapshot())
        adapter = SpiderLiteBenchmarkAdapter(
            snapshots_by_db={"pagila_fixture": build_pagila_fixture_snapshot()},
            worlds_by_db={"pagila_fixture": world},
            top_k=8,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tasks.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    [
                        {
                            "instance_id": "task-1",
                            "db_id": "pagila_fixture",
                            "question": "Which tables connect customers to the films they rented?",
                            "gold_tables": ["customer", "rental", "inventory", "film"],
                        }
                    ],
                    handle,
                )
            tasks = SpiderLiteTaskLoader().load(path)

        result = adapter.run_task(tasks[0])

        self.assertEqual(
            result["candidate_join_path"],
            ["customer->rental", "rental->inventory", "inventory->film"],
        )
        self.assertEqual(result["table_recall"], 1.0)
        summary = adapter.evaluate_tasks(tasks)
        self.assertEqual(summary["tasks_evaluated"], 1)
        self.assertEqual(summary["tasks_with_gold_tables"], 1)
        self.assertEqual(summary["average_table_recall"], 1.0)

    def test_workspace_resolves_official_layout_and_oracle_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spider_root = os.path.join(tmpdir, "Spider2")
            os.makedirs(os.path.join(spider_root, "spider2-lite"), exist_ok=True)
            os.makedirs(os.path.join(spider_root, "methods", "gold-tables"), exist_ok=True)

            tasks_path = os.path.join(spider_root, "spider2-lite", "spider2-lite.jsonl")
            oracle_path = os.path.join(
                spider_root,
                "methods",
                "gold-tables",
                "spider2-lite-gold-tables.jsonl",
            )

            with open(tasks_path, "w", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "instance_id": "task-1",
                            "db_id": "pagila_fixture",
                            "question": "Which tables connect customers to the films they rented?",
                        }
                    )
                    + "\n"
                )
            with open(oracle_path, "w", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "instance_id": "task-1",
                            "db_id": "pagila_fixture",
                            "gold_tables": ["customer", "rental", "inventory", "film"],
                        }
                    )
                    + "\n"
                )

            workspace = SpiderLiteWorkspace(spider_root)
            resolved_name = workspace.resolve_tasks_path().name
            tasks = workspace.load_tasks()
            enriched = workspace.attach_oracle_tables(tasks)

        self.assertEqual(resolved_name, "spider2-lite.jsonl")
        self.assertEqual(enriched[0].gold_tables, ["customer", "rental", "inventory", "film"])

    def test_workspace_loads_snapshot_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spider_root = os.path.join(tmpdir, "Spider2")
            os.makedirs(os.path.join(spider_root, "snapshots"), exist_ok=True)

            snapshot_path = os.path.join(spider_root, "snapshots", "pagila_fixture.json")
            manifest_path = os.path.join(spider_root, "snapshot_manifest.json")

            with open(snapshot_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "database_name": "pagila_fixture",
                        "tables": [
                            {
                                "schema": "public",
                                "name": "customer",
                                "row_estimate": 599,
                                "columns": [
                                    {
                                        "schema": "public",
                                        "table": "customer",
                                        "name": "customer_id",
                                        "data_type": "integer",
                                        "is_nullable": False,
                                    }
                                ],
                            }
                        ],
                        "foreign_keys": [],
                    },
                    handle,
                )
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump({"snapshots": {"pagila_fixture": "snapshots/pagila_fixture.json"}}, handle)

            workspace = SpiderLiteWorkspace(spider_root)
            snapshots = workspace.load_snapshot_manifest(manifest_path)

        self.assertIn("pagila_fixture", snapshots)
        self.assertEqual(snapshots["pagila_fixture"].database_name, "pagila_fixture")
        self.assertEqual(snapshots["pagila_fixture"].tables[0].name, "customer")

    def test_sqlite_metadata_loader_builds_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_dir = os.path.join(tmpdir, "Pagila")
            os.makedirs(metadata_dir, exist_ok=True)

            with open(os.path.join(metadata_dir, "customer.json"), "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "table_name": "customer",
                        "column_names": ["customer_id", "address_id", "first_name"],
                        "column_types": ["INT", "INT", "VARCHAR(45)"],
                        "sample_rows": [
                            {
                                "customer_id": 1,
                                "address_id": 5,
                                "first_name": "MARY",
                            }
                        ],
                    },
                    handle,
                )
            with open(os.path.join(metadata_dir, "address.json"), "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "table_name": "address",
                        "column_names": ["address_id", "address"],
                        "column_types": ["INT", "VARCHAR(50)"],
                        "sample_rows": [{"address_id": 5, "address": "Main St"}],
                    },
                    handle,
                )

            snapshot = SpiderLiteSQLiteMetadataLoader().load(metadata_dir, db_id="Pagila")

        self.assertEqual(snapshot.database_name, "Pagila")
        self.assertEqual({table.name for table in snapshot.tables}, {"customer", "address"})
        self.assertTrue(
            any(
                fk.source_table == "customer"
                and fk.source_column == "address_id"
                and fk.target_table == "address"
                for fk in snapshot.foreign_keys
            )
        )

    def test_sqlite_database_loader_builds_exact_foreign_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "Pagila.sqlite")
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(
                    "CREATE TABLE address (address_id INTEGER PRIMARY KEY, address TEXT)"
                )
                connection.execute(
                    """
                    CREATE TABLE customer (
                        customer_id INTEGER PRIMARY KEY,
                        address_id INTEGER,
                        first_name TEXT,
                        FOREIGN KEY(address_id) REFERENCES address(address_id)
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO address(address_id, address) VALUES (1, 'Main St')"
                )
                connection.execute(
                    "INSERT INTO customer(customer_id, address_id, first_name) VALUES (1, 1, 'MARY')"
                )
                connection.commit()
            finally:
                connection.close()

            snapshot = SpiderLiteSQLiteDatabaseLoader().load(db_path, db_id="Pagila")

        self.assertEqual(snapshot.database_name, "Pagila")
        self.assertEqual({table.name for table in snapshot.tables}, {"address", "customer"})
        self.assertTrue(
            any(
                fk.source_table == "customer"
                and fk.source_column == "address_id"
                and fk.target_table == "address"
                and fk.target_column == "address_id"
                for fk in snapshot.foreign_keys
            )
        )

    def test_workspace_resolves_local_sqlite_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spider_root = os.path.join(tmpdir, "Spider2")
            localdb = os.path.join(
                spider_root,
                "spider2-lite",
                "resource",
                "databases",
                "spider2-localdb",
            )
            os.makedirs(localdb, exist_ok=True)
            db_path = os.path.join(localdb, "Pagila.sqlite")
            sqlite3.connect(db_path).close()

            workspace = SpiderLiteWorkspace(spider_root)
            resolved = workspace.resolve_local_sqlite_db("Pagila")

        self.assertEqual(os.path.basename(resolved), "Pagila.sqlite")

    def test_sqlite_metadata_can_enrich_world_cache(self):
        world = snapshot_to_world_model(build_pagila_fixture_snapshot())
        metadata_documents = {
            "DDL.csv": "table_name,DDL\ncustomer,CREATE TABLE customer (...);",
            "customer.json": json.dumps(
                {
                    "table_name": "customer",
                    "column_names": ["customer_id", "address_id", "first_name"],
                    "sample_rows": [{"customer_id": 1, "address_id": 5, "first_name": "MARY"}],
                }
            ),
        }

        enriched = enrich_world_with_spider_sqlite_metadata(
            world,
            db_id="pagila_fixture",
            metadata_documents=metadata_documents,
        )

        document_nodes = {
            node_id: attrs
            for node_id, attrs in enriched.nodes.items()
            if attrs.get("type") == "document"
        }
        self.assertIn("document:pagila_fixture:ddl", document_nodes)
        self.assertIn("document:pagila_fixture:table:customer", document_nodes)
        self.assertTrue(
            any(
                edge[0] == "table:public.customer"
                and edge[1] == "has_metadata_document"
                and edge[2] == "document:pagila_fixture:table:customer"
                for edge in enriched.edges
            )
        )
if __name__ == "__main__":
    unittest.main()
