import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from implementations.bio import (  # noqa: E402
    BioEvidenceRecordLoader,
    BioInterpretationAdapter,
    BioWorkspace,
    BioInterpretationCase,
    BioTargetProfileRequest,
    build_bio_knowledge_base_from_records,
    build_bio_world_model,
    build_demo_bio_knowledge_base,
    load_bio_knowledge_base,
)


class BioImplementationTests(unittest.TestCase):
    def test_demo_bio_world_contains_expected_entities(self):
        knowledge_base = build_demo_bio_knowledge_base()
        world = build_bio_world_model(knowledge_base)

        self.assertIn("biomarker:her2_amplification", world.nodes)
        self.assertIn("disease:breast_cancer", world.nodes)
        self.assertIn("therapy:trastuzumab", world.nodes)
        self.assertTrue(any(edge[1] == "predicts_response_to" for edge in world.edges))

    def test_adapter_interprets_her2_positive_breast_case(self):
        knowledge_base = build_demo_bio_knowledge_base()
        world = build_bio_world_model(knowledge_base)
        adapter = BioInterpretationAdapter(world)
        case = BioInterpretationCase(
            case_id="case_001",
            biomarker="HER2 positive",
            disease="breast cancer",
            assay="IHC",
            result_text="HER2 positive by IHC with overexpression detected",
            question="Interpret the significance of this result.",
        )

        result = adapter.run_case(case)

        self.assertEqual(result["normalized_entities"]["biomarker"], "biomarker:her2_amplification")
        self.assertEqual(result["normalized_entities"]["disease"], "disease:breast_cancer")
        self.assertEqual(result["result_class"], "positive")
        self.assertTrue(any("actionable" in item["text"].lower() for item in result["hypotheses"]))
        self.assertTrue(any("trastuzumab" in item["text"].lower() for item in result["hypotheses"]))
        self.assertTrue(result["provenance"])

    def test_file_backed_bio_workspace_loads_demo_assets(self):
        workspace = BioWorkspace(os.path.join(ROOT, "implementations", "bio"))

        knowledge_base = workspace.load_knowledge_base()
        cases = workspace.load_cases()

        self.assertTrue(knowledge_base.entities)
        self.assertTrue(knowledge_base.relations)
        self.assertTrue(knowledge_base.sources)
        self.assertEqual(cases[0].case_id, "demo_her2_breast")

    def test_load_bio_knowledge_base_from_json(self):
        path = os.path.join(ROOT, "implementations", "bio", "data", "demo_biomarker_kb.json")
        knowledge_base = load_bio_knowledge_base(path)

        self.assertTrue(any(entity.entity_id == "biomarker:egfr_l858r" for entity in knowledge_base.entities))
        self.assertTrue(any(source.source_id == "source:braf_review" for source in knowledge_base.sources))

    def test_target_profile_connects_target_pathway_and_therapy(self):
        workspace = BioWorkspace(os.path.join(ROOT, "implementations", "bio"))
        world = build_bio_world_model(workspace.load_knowledge_base())
        adapter = BioInterpretationAdapter(world)

        result = adapter.run_target_profile(
            BioTargetProfileRequest(
                target="EGFR",
                disease="NSCLC",
                question="Why does this target matter in this disease?",
            )
        )

        self.assertEqual(result["normalized_entities"]["target"], "target:egfr")
        self.assertEqual(result["normalized_entities"]["disease"], "disease:nsclc")
        self.assertTrue(any("actionable" in item["text"].lower() for item in result["hypotheses"]))
        self.assertTrue(any("osimertinib" in item["text"].lower() for item in result["hypotheses"]))
        self.assertTrue(result["linked_entities"]["biomarkers"])
        self.assertTrue(result["provenance"])

    def test_evidence_record_loader_builds_knowledge_base(self):
        path = os.path.join(ROOT, "implementations", "bio", "data", "demo_evidence_records.jsonl")
        records = BioEvidenceRecordLoader().load(path)
        knowledge_base = build_bio_knowledge_base_from_records(records)

        self.assertEqual(len(records), 3)
        self.assertTrue(any(entity.entity_id == "target:braf" for entity in knowledge_base.entities))
        self.assertTrue(any(source.source_id == "source:egfr_guideline" for source in knowledge_base.sources))

    def test_workspace_loaded_evidence_records_support_target_profile(self):
        workspace = BioWorkspace(os.path.join(ROOT, "implementations", "bio"))
        records = workspace.load_evidence_records()
        knowledge_base = build_bio_knowledge_base_from_records(records)
        world = build_bio_world_model(knowledge_base)
        adapter = BioInterpretationAdapter(world)

        result = adapter.run_target_profile(
            BioTargetProfileRequest(
                target="BRAF",
                disease="Melanoma",
                question="Why is this target relevant in this disease?",
            )
        )

        self.assertEqual(result["normalized_entities"]["target"], "target:braf")
        self.assertTrue(any("mapk" in item["text"].lower() for item in result["hypotheses"]))
        self.assertTrue(any("trametinib" in item["text"].lower() for item in result["hypotheses"]))
