"""
The validator must be right about a graph we fully control.

Every metric this project has retracted was one nobody had checked against a
known answer: `fact_coverage` moved 0.0000 when every gold answer was negated,
and the NLI evaluator scored +0.826 with and without supporting evidence. Both
would have died here on day one.

So these tests use a tiny hand-built graph where the correct verdict is not a
matter of opinion, and assert the three outcomes plus the distinction that
matters most -- CONTRADICTED (the graph knows and disagrees) versus
NOT_COVERED (the graph does not know).
"""

import unittest

from tahi.validate import GraphFactValidator, Verdict


class _Graph:
    """Minimal stand-in with the `WorldModel` surface the validator uses."""

    def __init__(self):
        self.nodes = {}
        self.edges = []
        self._adj = {}

    def add_node(self, node_id, **attrs):
        self.nodes[node_id] = attrs

    def add_edge(self, src, rel, dst):
        self.edges.append((src, rel, dst))
        self._adj.setdefault(src, []).append((src, rel, dst, {}))

    def neighbors(self, node_id):
        return self._adj.get(node_id, [])


def _drug_graph():
    g = _Graph()
    g.add_node("compound::aspirin", label="Aspirin")
    g.add_node("gene::COX1", label="COX-1")
    g.add_node("gene::COX2", label="COX-2")
    g.add_node("gene::EGFR", label="EGFR")
    g.add_node("disease::inflammation", label="Inflammation")
    g.add_node("pathway::arachidonic", label="Arachidonic acid pathway")

    g.add_edge("compound::aspirin", "binds", "gene::COX1")
    g.add_edge("compound::aspirin", "binds", "gene::COX2")
    g.add_edge("gene::COX1", "participates_in", "pathway::arachidonic")
    g.add_edge("pathway::arachidonic", "implicated_in", "disease::inflammation")
    return g


class TestGraphFactValidator(unittest.TestCase):
    def setUp(self):
        self.v = GraphFactValidator(_drug_graph())

    def test_alias_index_built(self):
        self.assertGreater(self.v.n_aliases, 0)

    def test_entity_resolution_prefers_longest_alias(self):
        """`COX-1` must not be shadowed by a shorter overlapping alias."""
        found = self.v.entities_in("Aspirin inhibits COX-1 activity")
        self.assertIn("compound::aspirin", found)
        self.assertIn("gene::COX1", found)

    def test_true_claim_is_supported(self):
        r = self.v.validate("It binds COX-1.",
                            subject="compound::aspirin", relation="binds")
        self.assertIs(r.verdict, Verdict.SUPPORTED)
        self.assertIn(("compound::aspirin", "binds", "gene::COX1"),
                      r.supporting_edges)
        self.assertTrue(r.is_valid)

    def test_wrong_value_is_contradicted(self):
        """The graph covers (aspirin, binds) and does not list EGFR.

        This is the case `fact_coverage` could not detect: a fluent, plausible,
        wrong answer.
        """
        r = self.v.validate("It binds EGFR.",
                            subject="compound::aspirin", relation="binds")
        self.assertIs(r.verdict, Verdict.CONTRADICTED)
        self.assertIn("gene::EGFR", r.matched_entities)
        self.assertFalse(r.is_valid)

    def test_uncovered_relation_is_not_contradicted(self):
        """Open world: the graph having no `causes` edge is not a denial."""
        r = self.v.validate("It causes inflammation.",
                            subject="compound::aspirin", relation="causes")
        self.assertIs(r.verdict, Verdict.NOT_COVERED)
        self.assertTrue(r.is_valid,
                        "Absence of an edge must not be reported as a false claim.")

    def test_span_with_no_entity_is_not_covered(self):
        r = self.v.validate("It is widely used.",
                            subject="compound::aspirin", relation="binds")
        self.assertIs(r.verdict, Verdict.NOT_COVERED)
        self.assertEqual(r.matched_entities, [])

    def test_multi_hop_reaches_indirect_answer(self):
        """aspirin -> COX1 -> arachidonic -> inflammation is 3 hops.

        Single-hop validation must NOT find it; multi-hop must.
        """
        one = self.v.validate("This concerns Inflammation.",
                              subject="compound::aspirin", relation="binds",
                              hops=1)
        self.assertIsNot(one.verdict, Verdict.SUPPORTED)

        many = self.v.validate("This concerns Inflammation.",
                               subject="compound::aspirin", relation="binds",
                               hops=3)
        self.assertIs(many.verdict, Verdict.SUPPORTED)
        self.assertEqual(many.hops, 3)

    def test_unscoped_requires_two_entities(self):
        r = self.v.validate("Aspirin is a drug.")
        self.assertIs(r.verdict, Verdict.NOT_COVERED)

    def test_unscoped_connected_pair_is_supported(self):
        r = self.v.validate("Aspirin binds COX-2 in tissue.")
        self.assertIs(r.verdict, Verdict.SUPPORTED)

    def test_negation_is_not_silently_accepted(self):
        """The failure that killed `fact_coverage`.

        A negated claim names the same entity, so a lexical-overlap metric
        scores it identically. This validator reports SUPPORTED for the edge
        that exists -- which is correct for an edge check -- so the caller must
        know that polarity is out of scope. Asserting it here keeps that limit
        explicit rather than discovered later in a benchmark.
        """
        r = self.v.validate("It does not bind COX-1.",
                            subject="compound::aspirin", relation="binds")
        self.assertIs(r.verdict, Verdict.SUPPORTED)
        self.assertIn(("compound::aspirin", "binds", "gene::COX1"),
                      r.supporting_edges)


if __name__ == "__main__":
    unittest.main()
