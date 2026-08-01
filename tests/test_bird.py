import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import (  # noqa: E402
    SQLSchemaSnapshot,
    SQLTableProfile,
    SQLColumnProfile,
    snapshot_to_world_model,
)
from implementations.bird import (  # noqa: E402
    BirdABBenchmarkRunner,
    BirdBenchmarkAdapter,
    BirdExecutionPacket,
    BirdHFWorkspace,
    BirdHeuristicSQLCandidateGenerator,
    BirdSQLiteDatabaseLoader,
    BirdSQLCandidate,
    BirdTaskLoader,
    BirdWorkspace,
    EnsembleSQLGeneratorCoprocessor,
    FallbackSQLGeneratorCoprocessor,
    HeuristicSQLGeneratorCoprocessor,
    SQLGeneratorCoprocessor,
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

    def test_hf_workspace_uses_validation_split_and_cached_database(self):
        records = [
            {
                "db_id": "california_schools",
                "question": "How many schools are there?",
                "evidence": "Use schools.",
                "SQL": "SELECT COUNT(*) FROM schools",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            db_dir = os.path.join(tmpdir, "dev", "california_schools")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "california_schools.sqlite")
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("CREATE TABLE schools (school_id INTEGER PRIMARY KEY, name TEXT)")
                connection.commit()
            finally:
                connection.close()

            workspace = BirdHFWorkspace(repo_id="Sudnya/bird-sql", cache_dir=tmpdir)
            with patch("datasets.load_dataset", return_value=records) as mock_load_dataset:
                tasks = workspace.load_tasks(split="dev")

            resolved_db = workspace.resolve_local_sqlite_db("california_schools", split="dev")

        self.assertEqual(tasks[0].db_id, "california_schools")
        self.assertEqual(os.path.basename(resolved_db), "california_schools.sqlite")
        mock_load_dataset.assert_called_once()
        self.assertEqual(mock_load_dataset.call_args.kwargs["split"], "validation")

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

    def test_ab_benchmark_runner_produces_comparison_report(self):
        snapshot = SQLSchemaSnapshot(
            database_name="california_schools",
            tables=[
                SQLTableProfile(
                    schema="main",
                    name="schools",
                    columns=[
                        SQLColumnProfile(schema="main", table="schools", name="name", data_type="TEXT"),
                    ],
                )
            ],
            foreign_keys=[],
        )
        baseline_world = snapshot_to_world_model(snapshot)
        octo_world = enrich_world_with_bird_metadata(
            snapshot_to_world_model(snapshot),
            db_id="california_schools",
            metadata_documents={"schools.csv": "table,column,description\nschools,name,School name\n"},
        )
        task = type(
            "Task",
            (),
            {
                "task_id": "1",
                "db_id": "california_schools",
                "question": "Which table contains school names?",
                "evidence": "Use schools.",
                "difficulty": "easy",
                "gold_tables": ["schools"],
                "gold_sql": "",
            },
        )()
        report = BirdABBenchmarkRunner(
            baseline_adapter=BirdBenchmarkAdapter(
                snapshots_by_db={"california_schools": snapshot},
                worlds_by_db={"california_schools": baseline_world},
                top_k=8,
            ),
            octo_adapter=BirdBenchmarkAdapter(
                snapshots_by_db={"california_schools": snapshot},
                worlds_by_db={"california_schools": octo_world},
                top_k=8,
            ),
            evidence_adapter=BirdBenchmarkAdapter(
                snapshots_by_db={"california_schools": snapshot},
                worlds_by_db={"california_schools": octo_world},
                top_k=8,
                include_evidence=True,
            ),
        ).run([task])

        self.assertEqual(report["benchmark_name"], "bird_ab_grounding")
        self.assertEqual(len(report["systems"]), 4)
        self.assertIn("| System | Tasks | Accuracy |", report["markdown_summary"])


class SQLGeneratorCoprocessorTests(unittest.TestCase):
    """Tests that SQL generators behave as composable OCTO coprocessors."""

    def _make_packet(self) -> BirdExecutionPacket:
        snapshot = SQLSchemaSnapshot(
            database_name="demo",
            tables=[
                SQLTableProfile(
                    schema="main",
                    name="schools",
                    description="",
                    columns=[
                        SQLColumnProfile(
                            schema="main",
                            table="schools",
                            name="school_id",
                            data_type="INTEGER",
                            is_nullable=True,
                            ordinal_position=1,
                        ),
                        SQLColumnProfile(
                            schema="main",
                            table="schools",
                            name="name",
                            data_type="TEXT",
                            is_nullable=True,
                            ordinal_position=2,
                        ),
                    ],
                )
            ],
            foreign_keys=[],
        )
        return BirdExecutionPacket(
            task_id="demo_1",
            db_id="demo",
            question="How many schools are there?",
            evidence="",
            candidate_tables=["schools"],
            snapshot=snapshot,
        )

    def test_heuristic_coprocessor_generates_count_sql(self):
        packet = self._make_packet()
        coprocessor = HeuristicSQLGeneratorCoprocessor()
        candidates = coprocessor.generate(packet)

        self.assertEqual(coprocessor.name, "heuristic")
        self.assertEqual(len(candidates), 1)
        self.assertIn("COUNT", candidates[0].sql.upper())
        self.assertEqual(candidates[0].metadata["coprocessor"], "heuristic")

    def test_ensemble_aggregates_candidates_from_multiple_coprocessors(self):
        packet = self._make_packet()

        class MockLLMCoprocessor(SQLGeneratorCoprocessor):
            @property
            def name(self) -> str:
                return "mock_llm"

            def generate(
                self, packet: BirdExecutionPacket, *, max_candidates: int = 4
            ) -> list[BirdSQLCandidate]:
                return [
                    BirdSQLCandidate(
                        sql="SELECT school_id FROM schools LIMIT 5",
                        strategy="mock",
                        rationale="Mock LLM candidate.",
                    )
                ]

        ensemble = EnsembleSQLGeneratorCoprocessor(
            coprocessors=[
                HeuristicSQLGeneratorCoprocessor(),
                MockLLMCoprocessor(),
            ]
        )
        candidates = ensemble.generate(packet, max_candidates=4)

        self.assertIn("ensemble(heuristic,mock_llm)", ensemble.name)
        self.assertEqual(len(candidates), 2)
        strategies = {c.strategy for c in candidates}
        self.assertIn("heuristic", strategies)
        self.assertIn("mock", strategies)
        self.assertEqual(candidates[0].metadata["coprocessor"], "heuristic")
        self.assertEqual(candidates[1].metadata["coprocessor"], "mock_llm")

    def test_fallback_uses_backup_when_primary_is_empty(self):
        packet = self._make_packet()

        class EmptyCoprocessor(SQLGeneratorCoprocessor):
            @property
            def name(self) -> str:
                return "empty"

            def generate(
                self, packet: BirdExecutionPacket, *, max_candidates: int = 4
            ) -> list[BirdSQLCandidate]:
                return []

        fallback = FallbackSQLGeneratorCoprocessor(
            primary=EmptyCoprocessor(),
            fallback=HeuristicSQLGeneratorCoprocessor(),
        )
        candidates = fallback.generate(packet)

        self.assertEqual(fallback.name, "fallback(empty,heuristic)")
        self.assertEqual(len(candidates), 1)
        self.assertIn("COUNT", candidates[0].sql.upper())


if __name__ == "__main__":
    unittest.main()
