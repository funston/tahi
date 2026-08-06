"""
Demonstrable Integration Test: W3C OWL / RDF Ontology Integration via RDFLib.

Verifies that:
1. OWLOntology loads and parses standard W3C Turtle (.ttl) files using RDFLib.
2. OWL Classes, subClassOf hierarchies, and ObjectProperties are correctly extracted.
3. OWLOntology generates valid Kùzu Property Graph schema DDLs.
"""

import unittest
from pathlib import Path

from octo.graph.owl_ontology import OWLOntology


class TestOWLOntology(unittest.TestCase):
    def setUp(self):
        self.ttl_path = Path("data/ontologies/enterprise_rag.ttl")
        self.assertTrue(self.ttl_path.exists(), "enterprise_rag.ttl ontology file missing.")
        self.ontology = OWLOntology(self.ttl_path)

    def test_owl_class_extraction(self):
        classes = self.ontology.classes()
        self.assertIn("Document", classes)
        self.assertIn("Project", classes)
        self.assertIn("Topic", classes)
        self.assertIn("Person", classes)

    def test_owl_subclass_hierarchy(self):
        evidence_subs = self.ontology.sub_classes("EvidenceNode")
        self.assertIn("document", evidence_subs)

        entity_subs = self.ontology.sub_classes("EntityNode")
        self.assertIn("project", entity_subs)
        self.assertIn("topic", entity_subs)

    def test_owl_object_properties(self):
        props = self.ontology.object_properties()
        prop_names = [p[1] for p in props]
        self.assertIn("MENTIONS", prop_names)
        self.assertIn("HAS_DOC", prop_names)
        self.assertIn("COVERS", prop_names)

    def test_kuzu_ddl_generation(self):
        ddl = self.ontology.to_kuzu_ddl()
        self.assertGreater(len(ddl), 0)
        self.assertTrue(any("CREATE NODE TABLE" in s for s in ddl))


if __name__ == "__main__":
    unittest.main()
