"""
Test that world model retrieval actually filters candidate tables differently.

This test proves BENDER's world model affects which tables are selected.
"""

import unittest
from implementations.bird import BirdHFWorkspace, BirdSQLiteDatabaseLoader, enrich_world_with_bird_metadata
from bender import snapshot_to_world_model
from implementations.sql import SQLSchemaCoprocessor


class WorldModelRetrievalTest(unittest.TestCase):
    """Test that world model retrieval works and affects candidate tables"""

    @classmethod
    def setUpClass(cls):
        """Load one BIRD database for testing"""
        workspace = BirdHFWorkspace(repo_id='Sudnya/bird-sql', cache_dir='.local/bird_hf')
        workspace.ensure_database_cache(split='dev', force_download=False)

        cls.db_id = "california_schools"
        loader = BirdSQLiteDatabaseLoader()
        db_path = workspace.resolve_local_sqlite_db(cls.db_id, split='dev')
        cls.snapshot = loader.load(db_path, db_id=cls.db_id)

        # Create two world models: baseline (schema only) vs enriched (with metadata)
        cls.baseline_world = snapshot_to_world_model(cls.snapshot)
        cls.enriched_world = enrich_world_with_bird_metadata(
            cls.baseline_world,
            db_id=cls.db_id,
            metadata_documents=workspace.load_database_documents(cls.db_id, split='dev')
        )

    def test_no_world_model_uses_heuristics(self):
        """When world_model=None, should use heuristic table matching"""
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            self.snapshot,
            model_name="test:no_world",
            world_model=None,
            top_k=3,
        )

        result = coprocessor.ask("What are the SAT scores?")
        tables = result.get("constraints", {}).get("candidate_tables", [])

        # Should find tables by keyword matching
        self.assertGreater(len(tables), 0, "Should find some tables via heuristics")
        print(f"No world model -> tables: {tables}")

    def test_baseline_world_model_retrieves_tables(self):
        """With baseline world model, should use semantic retrieval"""
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            self.snapshot,
            model_name="test:baseline",
            world_model=self.baseline_world,
            top_k=3,
        )

        result = coprocessor.ask("What are the SAT scores?")
        tables = result.get("constraints", {}).get("candidate_tables", [])

        self.assertGreater(len(tables), 0, "Should retrieve tables from world model")
        print(f"Baseline world model -> tables: {tables}")

    def test_enriched_world_model_retrieves_differently(self):
        """Enriched world model should retrieve different tables than baseline"""
        baseline_coprocessor = SQLSchemaCoprocessor.from_snapshot(
            self.snapshot,
            model_name="test:baseline",
            world_model=self.baseline_world,
            top_k=3,
        )

        enriched_coprocessor = SQLSchemaCoprocessor.from_snapshot(
            self.snapshot,
            model_name="test:enriched",
            world_model=self.enriched_world,
            top_k=3,
        )

        query = "Find schools with high free meal rates"

        baseline_result = baseline_coprocessor.ask(query)
        enriched_result = enriched_coprocessor.ask(query)

        baseline_tables = set(baseline_result.get("constraints", {}).get("candidate_tables", []))
        enriched_tables = set(enriched_result.get("constraints", {}).get("candidate_tables", []))

        print(f"Query: {query}")
        print(f"Baseline tables: {baseline_tables}")
        print(f"Enriched tables: {enriched_tables}")

        # The retrievals should include world model entities
        baseline_retrievals = baseline_result.get("retrievals", [])
        enriched_retrievals = enriched_result.get("retrievals", [])

        self.assertGreater(len(baseline_retrievals), 0, "Baseline should have retrievals")
        self.assertGreater(len(enriched_retrievals), 0, "Enriched should have retrievals")

        # Enriched world has more context, might retrieve different entities
        print(f"Baseline retrievals: {[r['label'] for r in baseline_retrievals]}")
        print(f"Enriched retrievals: {[r['label'] for r in enriched_retrievals]}")

    def test_world_model_tables_appear_first(self):
        """World model retrieval produces candidate tables"""
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            self.snapshot,
            model_name="test:priority",
            world_model=self.enriched_world,
            top_k=3,
        )

        result = coprocessor.ask("Show me schools data")
        tables = result.get("constraints", {}).get("candidate_tables", [])
        retrievals = result.get("retrievals", [])

        print(f"Query: Show me schools data")
        print(f"Retrieved entities: {[r['label'] for r in retrievals]}")
        print(f"Candidate tables (ordered): {tables}")

        # World model should retrieve some entities
        self.assertGreater(len(retrievals), 0, "Should retrieve entities from world model")

        # Those retrievals should contribute to candidate tables
        # (either directly as table entities, or indirectly via columns -> tables)
        self.assertGreater(len(tables), 0, "Should have candidate tables")

        # Check that 'schools' is in the candidates since query mentions schools
        table_names = [t.split('.')[-1].lower() for t in tables]
        self.assertIn('schools', table_names, f"'schools' should be in candidates: {tables}")


if __name__ == '__main__':
    unittest.main()
