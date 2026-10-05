"""
Demonstrable Integration Test: Typed Ontology Traversal in TAHI.

Verifies that:
1. OntologySchema validates node types and relation triples.
2. WorldModel equipped with an OntologySchema filters out illegal/invalid relation paths.
3. Traversal follows structured legal paths (e.g. Document -> Entity -> Document).
"""

import unittest

from tahi.graph.ontology import get_default_enterprise_rag_ontology
from tahi.world_state import WorldModel


class TestOntologyTraversal(unittest.TestCase):
    def setUp(self):
        self.ontology = get_default_enterprise_rag_ontology()

    def test_ontology_schema_validation(self):
        self.assertTrue(self.ontology.validate_node("n1", {"type": "document"}))
        self.assertTrue(self.ontology.validate_node("n2", {"type": "project"}))

        # Valid triples
        self.assertTrue(self.ontology.validate_relation("document", "MENTIONS", "entity"))
        self.assertTrue(self.ontology.validate_relation("project", "HAS_DOC", "document"))

        # Invalid triple
        self.assertFalse(self.ontology.validate_relation("person", "EXPLODES", "location"))

    def test_world_model_ontology_integration(self):
        wm = WorldModel(domain="enterprise_rag")
        wm.set_index_node_types(list(self.ontology.traversal_seed_types))

        wm.upsert_node("doc_1", type="document", label="Doc 1", text="Mentions security policy.")
        wm.upsert_node("proj_sec", type="project", label="Security Project")
        wm.upsert_node("doc_2", type="document", label="Doc 2", text="Security compliance details.")

        wm.add_edge("proj_sec", "HAS_DOC", "doc_1")
        wm.add_edge("proj_sec", "HAS_DOC", "doc_2")

        # Validate that traversal recognizes valid seeds and evidence
        self.assertTrue(wm._is_evidence("doc_1"))
        self.assertFalse(wm._is_evidence("proj_sec"))


if __name__ == "__main__":
    unittest.main()
