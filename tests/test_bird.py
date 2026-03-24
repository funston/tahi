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

from bender import (  # noqa: E402
    SQLSchemaSnapshot,
    SQLTableProfile,
    SQLColumnProfile,
    snapshot_to_world_model,
)
from implementations.bird import (  # noqa: E402
    BirdBenchmarkAdapter,
    BirdSQLiteDatabaseLoader,
    BirdTaskLoader,
    BirdWorkspace,
    enrich_world_with_bird_metadata,
)


class BirdTests(unittest.TestCase):
    def test_loader_supports_bird_json(self):
        payload = [
            {
                "question_id": 7,
                "db_id": "california_schools",
                "question": "How many schools are there?",
                "evidence": "Use the schools table.",
                "SQL": "SELECT COUNT(*) FROM schools",
                "difficulty": "easy",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dev.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            tasks = BirdTaskLoader().load(path)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].task_id, "7")
        self.assertEqual(tasks[0].db_id, "california_schools")
        self.assertEqual(tasks[0].gold_sql, "SELECT COUNT(*) FROM schools")
        self.assertEqual(tasks[0].difficulty, "easy")

    def test_loader_assigns_stable_fallback_task_ids(self):
        payload = [
            {
                "db_id": "cs_semester",
                "question": "How many courses are there?",
            },
            {
                "db_id": "cs_semester",
                "question": "How many professors are there?",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dev.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            tasks = BirdTaskLoader().load(path)

        self.assertEqual(tasks[0].task_id, "cs_semester_0001")
        self.assertEqual(tasks[1].task_id, "cs_semester_0002")

    def test_workspace_resolves_mini_dev_layout_and_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bird_root = os.path.join(tmpdir, "BIRD")
            db_dir = os.path.join(
                bird_root,
                "mini_dev",
                "dev_databases",
                "california_schools",
            )
            os.makedirs(os.path.join(db_dir, "database_description"), exist_ok=True)
            tasks_path = os.path.join(bird_root, "mini_dev", "dev.json")
            db_path = os.path.join(db_dir, "california_schools.sqlite")
            description_path = os.path.join(db_dir, "database_description", "schools.csv")

            os.makedirs(os.path.dirname(tasks_path), exist_ok=True)
            with open(tasks_path, "w", encoding="utf-8") as handle:
                json.dump(
                    [
                        {
                            "question_id": 1,
                            "db_id": "california_schools",
                            "question": "How many schools are there?",
                        }
                    ],
                    handle,
                )
            with open(description_path, "w", encoding="utf-8") as handle:
                handle.write("table,column,description\nschools,name,School name\n")
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("CREATE TABLE schools (school_id INTEGER PRIMARY KEY, name TEXT)")
                connection.commit()
            finally:
                connection.close()

            workspace = BirdWorkspace(bird_root)
            tasks = workspace.load_tasks()
            resolved_db = workspace.resolve_local_sqlite_db("california_schools")
            docs = workspace.load_database_documents("california_schools")

        self.assertEqual(tasks[0].db_id, "california_schools")
        self.assertEqual(os.path.basename(resolved_db), "california_schools.sqlite")
        self.assertIn("schools.csv", docs)

    def test_sqlite_loader_builds_snapshot_from_bird_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "schools.sqlite")
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("CREATE TABLE districts (district_id INTEGER PRIMARY KEY, name TEXT)")
                connection.execute(
                    "CREATE TABLE schools (school_id INTEGER PRIMARY KEY, district_id INTEGER, name TEXT, "
                    "FOREIGN KEY(district_id) REFERENCES districts(district_id))"
                )
                connection.commit()
            finally:
                connection.close()

            snapshot = BirdSQLiteDatabaseLoader().load(db_path, db_id="california_schools")

        self.assertEqual(snapshot.database_name, "california_schools")
        self.assertEqual({table.name for table in snapshot.tables}, {"districts", "schools"})
        self.assertTrue(any(fk.source_table == "schools" and fk.target_table == "districts" for fk in snapshot.foreign_keys))

    def test_adapter_and_world_enrichment_run(self):
        snapshot = SQLSchemaSnapshot(
            database_name="california_schools",
            tables=[
                SQLTableProfile(
                    schema="main",
                    name="schools",
                    columns=[
                        SQLColumnProfile(schema="main", table="schools", name="school_id", data_type="INTEGER"),
                        SQLColumnProfile(schema="main", table="schools", name="name", data_type="TEXT"),
                    ],
                )
            ],
            foreign_keys=[],
        )
        world = snapshot_to_world_model(snapshot)
        world = enrich_world_with_bird_metadata(
            world,
            db_id="california_schools",
            metadata_documents={"schools.csv": "table,column,description\nschools,name,School name\n"},
        )
        adapter = BirdBenchmarkAdapter(
            snapshots_by_db={"california_schools": snapshot},
            worlds_by_db={"california_schools": world},
            top_k=8,
        )
        task = BirdTaskLoader().load(
            os.path.join(ROOT, "tests", "fixtures_missing.json")
        ) if False else None
        result = adapter.run_task(
            type(
                "Task",
                (),
                {
                    "task_id": "1",
                    "db_id": "california_schools",
                    "question": "Which table contains school names?",
                    "evidence": "Use schools.",
                    "difficulty": "easy",
                    "gold_tables": ["schools"],
                },
            )()
        )

        self.assertEqual(result["task_id"], "1")
        self.assertEqual(result["table_recall"], 1.0)
        document_nodes = [node_id for node_id in world.nodes if node_id.startswith("document:california_schools:")]
        self.assertTrue(document_nodes)

    def test_adapter_infers_gold_tables_from_sql(self):
        snapshot = SQLSchemaSnapshot(
            database_name="cs_semester",
            tables=[
                SQLTableProfile(
                    schema="main",
                    name="course",
                    columns=[
                        SQLColumnProfile(schema="main", table="course", name="name", data_type="TEXT"),
                        SQLColumnProfile(schema="main", table="course", name="diff", data_type="INTEGER"),
                    ],
                )
            ],
            foreign_keys=[],
        )
        adapter = BirdBenchmarkAdapter(
            snapshots_by_db={"cs_semester": snapshot},
            worlds_by_db={"cs_semester": snapshot_to_world_model(snapshot)},
            top_k=8,
        )
        result = adapter.run_task(
            type(
                "Task",
                (),
                {
                    "task_id": "2",
                    "db_id": "cs_semester",
                    "question": "Which course is more difficult, Intro to BlockChain or Computer Network?",
                    "evidence": "",
                    "difficulty": "",
                    "gold_tables": [],
                    "gold_sql": "SELECT name FROM course WHERE name = 'Intro to BlockChain' ORDER BY diff DESC LIMIT 1",
                },
            )()
        )

        self.assertEqual(result["gold_tables"], ["course"])
        self.assertEqual(result["table_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
