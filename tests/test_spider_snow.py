import os
import sys
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import snapshot_to_world_model  # noqa: E402
from implementations.spider import (  # noqa: E402
    SpiderLiteTask,
    SpiderSnowSQLGenerator,
    SpiderSnowWorkspace,
    SpiderSnowflakeMetadataLoader,
    UnsupportedSpiderSnowSQLGeneration,
    apply_tcga_domain_plan,
    enrich_world_with_spider_snow_metadata,
    resolve_tcga_schema_plan,
)


class SpiderSnowTests(unittest.TestCase):
    def test_metadata_loader_builds_snapshot(self):
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/USA_NAMES",
            db_id="USA_NAMES",
        )

        self.assertEqual(snapshot.database_name, "USA_NAMES")
        self.assertEqual({table.name for table in snapshot.tables}, {"USA_1910_2013", "USA_1910_CURRENT"})
        self.assertTrue(any(column.name == "name" for table in snapshot.tables for column in table.columns))

    def test_workspace_loads_usa_names_task_and_oracle_tables(self):
        workspace = SpiderSnowWorkspace("/Users/richiek/work/Spider2")
        tasks = workspace.attach_oracle_tables(workspace.load_tasks())
        task = next(task for task in tasks if task.task_id == "sf_bq286")

        self.assertEqual(task.db_id, "USA_NAMES")
        self.assertEqual(task.gold_tables, ["USA_NAMES.USA_NAMES.USA_1910_CURRENT"])

    def test_generator_builds_usa_names_query(self):
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/USA_NAMES",
            db_id="USA_NAMES",
        )
        generator = SpiderSnowSQLGenerator()
        task = SpiderLiteTask(
            task_id="sf_bq286",
            db_id="USA_NAMES",
            question="Can you tell me the name of the most popular female baby in Wyoming for the year 2021, based on the proportion of female babies given that name compared to the total number of female babies given the same name across all states?",
            gold_tables=["USA_NAMES.USA_NAMES.USA_1910_CURRENT"],
        )

        sql = generator.generate(
            task=task,
            snapshot=snapshot,
            constraints={"candidate_tables": ["USA_1910_CURRENT"]},
        )

        self.assertIn('FROM "USA_NAMES"."USA_NAMES"."USA_1910_CURRENT"', sql)
        self.assertIn('"state" = \'WY\'', sql)
        self.assertIn('"year" = 2021', sql)
        self.assertIn('"gender" = \'F\'', sql)

    def test_world_enrichment_adds_documents(self):
        workspace = SpiderSnowWorkspace("/Users/richiek/work/Spider2")
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/USA_NAMES",
            db_id="USA_NAMES",
        )
        world = snapshot_to_world_model(snapshot)
        world = enrich_world_with_spider_snow_metadata(
            world,
            db_id="USA_NAMES",
            metadata_documents=workspace.load_metadata_documents("USA_NAMES"),
        )

        self.assertIn("document:USA_NAMES:ddl", world.nodes)
        self.assertIn("document:USA_NAMES:table:USA_1910_CURRENT", world.nodes)

    def test_tcga_domain_plan_prefers_copy_number_and_cytobands(self):
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/TCGA_MITELMAN",
            db_id="TCGA_MITELMAN",
        )
        query = (
            "Using segment-level copy number data from the copy_number_segment_allelic_hg38_gdc_r23 "
            "dataset restricted to TCGA-KIRC samples, merge these segments with the cytogenetic band "
            "definitions in CytoBands_hg38 and calculate aberration frequencies."
        )

        domain_plan = resolve_tcga_schema_plan(query, snapshot)

        self.assertIn("TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23", domain_plan["candidate_tables"])
        self.assertIn("PROD.CYTOBANDS_HG38", domain_plan["candidate_tables"])
        self.assertIn("copy_number_segment_allelic->cytobands_hg38", domain_plan["candidate_join_path"])

    def test_tcga_domain_plan_merges_into_constraints(self):
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/TCGA_MITELMAN",
            db_id="TCGA_MITELMAN",
        )
        planning_result = {
            "constraints": {
                "candidate_tables": ["PROD.CYTOGEN"],
            }
        }
        query = "Identify cytoband names on chromosome 1 in the TCGA-KIRC segment allelic dataset."

        enriched = apply_tcga_domain_plan(
            planning_result,
            query=query,
            snapshot=snapshot,
        )

        self.assertIn(
            "TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23",
            enriched["constraints"]["candidate_tables"],
        )
        self.assertIn("schema_families", enriched["constraints"])
        self.assertIn("domain_hints", enriched["constraints"])

    def test_generator_builds_tcga_overlap_query(self):
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/TCGA_MITELMAN",
            db_id="TCGA_MITELMAN",
        )
        generator = SpiderSnowSQLGenerator()
        task = SpiderLiteTask(
            task_id="sf_bq176",
            db_id="TCGA_MITELMAN",
            question="Identify the case barcodes from the TCGA-LAML study with the highest weighted average copy number in cytoband 15q11 on chromosome 15.",
            gold_tables=["TCGA_MITELMAN.TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23"],
        )

        sql = generator.generate(task=task, snapshot=snapshot, constraints={})

        self.assertIn('"TCGA_MITELMAN"."TCGA_VERSIONED"."COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23"', sql)
        self.assertIn('"TCGA_MITELMAN"."PROD"."CYTOBANDS_HG38"', sql)
        self.assertIn("TCGA-LAML", sql)
        self.assertIn("15q11", sql)

    def test_generator_builds_tcga_ranked_cytoband_query(self):
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/TCGA_MITELMAN",
            db_id="TCGA_MITELMAN",
        )
        generator = SpiderSnowSQLGenerator()
        task = SpiderLiteTask(
            task_id="sf_bq175",
            db_id="TCGA_MITELMAN",
            question="Identify cytoband names on chromosome 1 in the TCGA-KIRC segment allelic dataset.",
            gold_tables=["TCGA_MITELMAN.TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23"],
        )

        sql = generator.generate(task=task, snapshot=snapshot, constraints={})

        self.assertIn("DENSE_RANK()", sql)
        self.assertIn("heterodel_rank", sql)
        self.assertIn("TCGA-KIRC", sql)
        self.assertIn("chr1", sql)

    def test_generator_rejects_unsupported_task_instead_of_select_star_fallback(self):
        loader = SpiderSnowflakeMetadataLoader()
        snapshot = loader.load(
            "/Users/richiek/work/Spider2/spider2-snow/resource/databases/USA_NAMES",
            db_id="USA_NAMES",
        )
        generator = SpiderSnowSQLGenerator()
        task = SpiderLiteTask(
            task_id="sf_unknown999",
            db_id="USA_NAMES",
            question="Find a complex unsupported aggregate over baby names.",
            gold_tables=["USA_NAMES.USA_NAMES.USA_1910_CURRENT"],
        )

        with self.assertRaises(UnsupportedSpiderSnowSQLGeneration):
            generator.generate(
                task=task,
                snapshot=snapshot,
                constraints={"candidate_tables": ["USA_1910_CURRENT"]},
            )


if __name__ == "__main__":
    unittest.main()
