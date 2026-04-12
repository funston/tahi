import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from implementations.mass_spec import (  # noqa: E402
    MassSpecABBenchmarkRunner,
    MassSpecAnalyteProfileRequest,
    MassSpecInterpretationAdapter,
    MassSpecWorkspace,
    build_demo_mass_spec_knowledge_base,
    build_mass_spec_world_model,
    load_mass_spec_knowledge_base,
    render_mass_spec_rag_baseline,
)


class MassSpecImplementationTests(unittest.TestCase):
    def test_demo_world_contains_expected_entities(self):
        knowledge_base = build_demo_mass_spec_knowledge_base()
        world = build_mass_spec_world_model(knowledge_base)

        self.assertIn("analyte:caffeine", world.nodes)
        self.assertIn("adduct:m_plus_h", world.nodes)
        self.assertTrue(any(edge[1] == "supports_adduct" for edge in world.edges))

    def test_workspace_loads_demo_assets(self):
        workspace = MassSpecWorkspace(os.path.join(ROOT, "implementations", "mass_spec"))
        knowledge_base = workspace.load_knowledge_base()
        cases = workspace.load_cases()

        self.assertTrue(knowledge_base.entities)
        self.assertTrue(knowledge_base.relations)
        self.assertEqual(cases[0].case_id, "demo_caffeine_positive")

    def test_spectrum_case_assigns_caffeine_protonated_peak(self):
        workspace = MassSpecWorkspace(os.path.join(ROOT, "implementations", "mass_spec"))
        world = build_mass_spec_world_model(workspace.load_knowledge_base())
        adapter = MassSpecInterpretationAdapter(world)
        case = next(candidate for candidate in workspace.load_cases() if candidate.case_id == "demo_caffeine_positive")

        result = adapter.run_spectrum_case(case)

        top = result["candidate_explanations"][0]
        self.assertEqual(top["analyte_id"], "analyte:caffeine")
        self.assertEqual(top["adduct_id"], "adduct:m_plus_h")
        self.assertTrue(any("caffeine" in item["text"].lower() for item in result["hypotheses"]))
        self.assertTrue(result["provenance"])

    def test_analyte_profile_explains_glucose_adduct_preference(self):
        workspace = MassSpecWorkspace(os.path.join(ROOT, "implementations", "mass_spec"))
        world = build_mass_spec_world_model(workspace.load_knowledge_base())
        adapter = MassSpecInterpretationAdapter(world)

        result = adapter.run_analyte_profile(
            MassSpecAnalyteProfileRequest(
                analyte="Glucose",
                polarity="positive",
                question="How should I expect this analyte to ionize?",
            )
        )

        self.assertEqual(result["normalized_entities"]["analyte"], "analyte:glucose")
        self.assertTrue(any("m+na" in item["text"].lower() or "sodium" in item["text"].lower() for item in result["hypotheses"]))

    def test_load_knowledge_base_and_rag_baseline(self):
        path = os.path.join(ROOT, "implementations", "mass_spec", "data", "demo_mass_spec_kb.json")
        knowledge_base = load_mass_spec_knowledge_base(path)
        workspace = MassSpecWorkspace(os.path.join(ROOT, "implementations", "mass_spec"))
        case = next(candidate for candidate in workspace.load_cases() if candidate.case_id == "demo_glucose_sodium")
        rag = render_mass_spec_rag_baseline(case)

        self.assertTrue(any(entity.entity_id == "analyte:glucose" for entity in knowledge_base.entities))
        self.assertIn("retrieve top-k adduct and analyte passages from a vector database", rag["steps"][0])

    def test_ab_benchmark_runner_reports_retrieval_vs_bender(self):
        workspace = MassSpecWorkspace(os.path.join(ROOT, "implementations", "mass_spec"))
        world = build_mass_spec_world_model(workspace.load_knowledge_base())
        cases = workspace.load_cases()

        report = MassSpecABBenchmarkRunner(
            adapter=MassSpecInterpretationAdapter(world)
        ).run(cases)

        self.assertEqual(report["benchmark_name"], "mass_spec_ab_peak_assignment")
        self.assertEqual(len(report["systems"]), 2)
        self.assertIn("| System | Tasks | Accuracy |", report["markdown_summary"])
