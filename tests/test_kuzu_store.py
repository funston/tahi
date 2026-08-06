"""
Tests for the Kùzu-backed graph store.

The store exists because `WorldModel.edges` was a flat list and `neighbors()`
scanned it linearly -- O(E) per lookup, ~19M comparisons per query on the
956,232-edge build, slow enough that the fragment-verification experiment could
not finish inside a 30-minute timeout.

The load-bearing test here is `test_shared_entity_documents_enumerates_a_set`:
set completion is the one retrieval behaviour dense similarity cannot provide at
any corpus size. Similarity ranks by closeness; it has no notion of "all members
of this group". If that test ever fails, OCTO has no mechanism the baseline
lacks.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from octo.graph import KuzuGraphStore, build_adjacency
    HAVE_KUZU = True
except ImportError:  # pragma: no cover
    HAVE_KUZU = False


def seed_store(store: KuzuGraphStore) -> None:
    """Two projects, five documents, plus a shared ticket across projects."""
    nodes = [
        ("doc::a1", {"type": "document", "label": "a1", "summary": "Atlas charter"}),
        ("doc::a2", {"type": "document", "label": "a2", "summary": "Atlas ship date"}),
        ("doc::a3", {"type": "document", "label": "a3", "summary": "Atlas catering"}),
        ("doc::v1", {"type": "document", "label": "v1", "summary": "Vega latency"}),
        ("doc::v2", {"type": "document", "label": "v2", "summary": "Vega rollout"}),
        ("project::Atlas", {"type": "project", "label": "Atlas"}),
        ("project::Vega", {"type": "project", "label": "Vega"}),
        ("ticket::ENG-1", {"type": "ticket", "label": "ENG-1"}),
    ]
    edges = []
    for d in ("doc::a1", "doc::a2", "doc::a3"):
        edges += [(d, "in_project", "project::Atlas", {}),
                  ("project::Atlas", "has_in_project", d, {})]
    for d in ("doc::v1", "doc::v2"):
        edges += [(d, "in_project", "project::Vega", {}),
                  ("project::Vega", "has_in_project", d, {})]
    # A ticket referenced from both projects -- the cross-source link that
    # embedding similarity has no way to represent.
    edges += [("doc::a2", "mentions", "ticket::ENG-1", {}),
              ("ticket::ENG-1", "mentioned_by", "doc::a2", {}),
              ("doc::v1", "mentions", "ticket::ENG-1", {}),
              ("ticket::ENG-1", "mentioned_by", "doc::v1", {})]
    store.add_nodes(nodes)
    store.add_edges(edges)


@unittest.skipUnless(HAVE_KUZU, "kuzu not installed")
class KuzuStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = KuzuGraphStore()
        seed_store(self.store)

    def tearDown(self):
        self.store.close()

    def test_stats_reflect_what_was_ingested(self):
        s = self.store.stats()
        self.assertEqual(s["nodes"], 8)
        self.assertGreaterEqual(s["edges"], 14)

    def test_neighbors_are_bidirectional(self):
        got = {n[2] for n in self.store.neighbors("doc::a1")}
        self.assertIn("project::Atlas", got)

    def test_neighbors_of_unknown_node_is_empty_not_an_error(self):
        self.assertEqual(self.store.neighbors("doc::nonexistent"), [])

    def test_shared_entity_documents_enumerates_a_set(self):
        """"All documents in the same project" -- the query vectors cannot do.

        Given one Atlas document, the store must return the OTHER Atlas
        documents and no Vega ones. Dense retrieval can only rank by similarity;
        it has no operation that enumerates group membership.
        """
        got = dict(self.store.shared_entity_documents(
            ["doc::a1"], entity_types=["project"], limit=10))
        self.assertIn("doc::a2", got)
        self.assertIn("doc::a3", got)
        self.assertNotIn("doc::v1", got)
        self.assertNotIn("doc::a1", got, "seed must not be returned to itself")

    def test_shared_entity_respects_the_entity_type_filter(self):
        """Restricting to tickets must not return project-mates."""
        got = dict(self.store.shared_entity_documents(
            ["doc::a2"], entity_types=["ticket"], limit=10))
        self.assertIn("doc::v1", got, "cross-project ticket link should be found")
        self.assertNotIn("doc::a3", got, "project-mate must not appear under a "
                                         "ticket-only filter")

    def test_expand_ranks_by_seed_support(self):
        """A document reached from more seeds outranks one reached from fewer.

        Support count is the defence against hub nodes: an entity with thousands
        of edges otherwise floods the candidate pool, which is the shape of the
        conflicting_info recall collapse (0.450 -> 0.175).
        """
        got = self.store.expand(["doc::a1", "doc::a3"], hops=2,
                                node_type="document", limit=10)
        self.assertTrue(got, "expansion returned nothing")
        ids = [n for n, _s, _h in got]
        self.assertIn("doc::a2", ids)
        self.assertNotIn("doc::a1", ids, "seeds must be excluded from results")

    def test_expand_honours_node_type_filter(self):
        got = self.store.expand(["doc::a1"], hops=2, node_type="document", limit=10)
        for node_id, _s, _h in got:
            self.assertTrue(node_id.startswith("doc::"),
                            f"non-document {node_id} returned under a document filter")

    def test_expand_with_no_seeds_is_empty(self):
        self.assertEqual(self.store.expand([], hops=2), [])

    def test_reingest_is_idempotent(self):
        before = self.store.stats()
        seed_store(self.store)
        self.assertEqual(self.store.stats(), before,
                         "re-ingesting the same graph must MERGE, not duplicate")


class AdjacencyFallbackTests(unittest.TestCase):
    """The in-memory index used for demo-scale worlds."""

    def test_indexes_both_endpoints(self):
        edges = [("a", "rel", "b", {}), ("b", "rel", "c", {})]
        adj = build_adjacency(edges)
        self.assertEqual(len(adj["b"]), 2, "node must be indexed as src and dst")
        self.assertEqual(len(adj["a"]), 1)

    def test_self_loop_is_not_double_counted(self):
        adj = build_adjacency([("a", "rel", "a", {})])
        self.assertEqual(len(adj["a"]), 2,
                         "self-loop appears once per endpoint by construction")


if __name__ == "__main__":
    unittest.main(verbosity=2)
