"""
RED tests for graph-aware retrieval.

These encode the behaviour `WorldModel.retrieve` must have for TAHI to be
anything other than dense retrieval over a polluted index. They are written to
FAIL against the current implementation; each one names the defect it pins.

Current defects, both confirmed on the 511,962-document EnterpriseRAG-Bench run:

  D1  Edges are never traversed for retrieval. `retrieve()` runs ANN search and
      then hydrates `item.relations` for display. 956,232 edges produced zero
      candidates, so "graph retrieval" was vector search wearing a hat.

  D2  Entity nodes share the document index. 107,467 `space::`/`person::`/
      `ticket::` nodes competed with documents for top-k slots, so TAHI's
      effective document budget was smaller than the baseline's at the same k.
      Measured effect: doc_recall 0.408 -> 0.331 against plain dense retrieval.

The fixture is a two-hop world: the query matches a "hub" document lexically,
but the document that ANSWERS it shares only a project edge. Dense retrieval
alone cannot reach it; edge traversal can. That is the entire thesis, reduced to
six documents.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.world_state import WorldModel  # noqa: E402

QUERY = "What is the rollout date for Project Halcyon?"

# doc id -> (text, project)
DOCS = {
    # Lexically close to the query, but does NOT contain the answer.
    "doc::hub": ("Project Halcyon overview and charter. Owner: Dana.", "Halcyon"),
    # Contains the answer, but shares almost no query vocabulary. Reachable
    # only via the shared project edge.
    "doc::answer": ("Ship date confirmed for November 14th following sign-off.", "Halcyon"),
    # Same project, irrelevant -- expansion must not be indiscriminate.
    "doc::noise": ("Catering order for the team offsite.", "Halcyon"),
    # Different projects entirely.
    "doc::other1": ("Project Vega latency budget is 200ms p99.", "Vega"),
    "doc::other2": ("Vega rollout scheduled for March.", "Vega"),
    "doc::other3": ("Unrelated: parking policy update.", "Ops"),
}


def build_world() -> WorldModel:
    wm = WorldModel(domain="test_graph_retrieval")
    for node_id, (text, project) in DOCS.items():
        wm.upsert_node(node_id, type="document", label=node_id,
                       text=text, summary=text)
        proj = f"project::{project}"
        wm.upsert_node(proj, type="project", label=project,
                       text=project, summary=f"project: {project}")
        wm.add_edge(node_id, "in_project", proj)
        wm.add_edge(proj, "has_in_project", node_id)
    # Declare which types are pure traversal nodes, exactly as the real
    # builder does. Without this the project nodes count as evidence and
    # consume result slots.
    wm.set_index_node_types({"project"})
    wm.use_ann = True
    wm.build_index()
    return wm


def doc_ids(records) -> list[str]:
    return [r.node_id for r in records if r.node_id.startswith("doc::")]


class EntityPollutionTests(unittest.TestCase):
    """D2 -- entity nodes must not consume the document budget."""

    def test_retrieve_returns_k_documents_not_k_mixed_nodes(self):
        wm = build_world()
        got = wm.retrieve(QUERY, top_k=4)
        self.assertEqual(
            len(doc_ids(got)), 4,
            f"Asked for 4 documents, got {len(doc_ids(got))} documents plus "
            f"{len(got) - len(doc_ids(got))} entity nodes: "
            f"{[r.node_id for r in got]}. Entity nodes are competing with "
            "documents for retrieval slots, shrinking the effective budget "
            "relative to a baseline retrieving from documents only.",
        )

    def test_entity_nodes_are_never_returned_as_evidence(self):
        wm = build_world()
        got = wm.retrieve(QUERY, top_k=6)
        entities = [r.node_id for r in got if not r.node_id.startswith("doc::")]
        self.assertEqual(
            entities, [],
            f"Entity nodes returned as retrieval results: {entities}. They carry "
            "no evidence text, so they waste both a retrieval slot and a slot in "
            "the answer context.",
        )


class GraphExpansionTests(unittest.TestCase):
    """D1 -- edges must contribute candidates, not just annotation."""

    def test_edges_produce_candidates(self):
        """The answer doc shares a project edge but little query vocabulary."""
        wm = build_world()
        got = doc_ids(wm.retrieve(QUERY, top_k=3))
        self.assertIn(
            "doc::answer", got,
            f"Retrieved {got}. 'doc::answer' holds the answer and is one edge "
            "from the top vector hit, but edges are only hydrated onto results "
            "after search -- they never produce candidates. This is the defect "
            "that made 956,232 edges contribute nothing.",
        )

    def test_expansion_does_not_evict_strong_vector_hits(self):
        """Expansion must ADD to the candidate pool, not displace better hits.

        The measured regression (doc_recall 0.408 -> 0.331) is consistent with
        graph candidates pushing correct documents out of top-k. Expansion has
        to be additive and rank-aware.
        """
        wm = build_world()
        got = doc_ids(wm.retrieve(QUERY, top_k=3))
        self.assertIn(
            "doc::hub", got,
            f"Retrieved {got}. The strongest lexical match was evicted by graph "
            "expansion -- expansion must not cost the results dense retrieval "
            "already had.",
        )

    def test_expansion_is_selective_not_exhaustive(self):
        """Being edge-adjacent is not sufficient to be retrieved.

        `doc::noise` shares the Halcyon project edge but is irrelevant. If every
        neighbour is admitted, a hub entity with thousands of edges floods the
        results -- which is the failure mode behind conflicting_info's
        doc_recall collapse (0.450 -> 0.175).
        """
        wm = build_world()
        got = doc_ids(wm.retrieve(QUERY, top_k=3))
        self.assertNotIn(
            "doc::noise", got,
            f"Retrieved {got}. An irrelevant same-project document was admitted "
            "purely for being edge-adjacent. Expansion must score candidates, "
            "not admit them wholesale.",
        )


class RecallTests(unittest.TestCase):
    """The end-to-end property the thesis actually claims."""

    def test_graph_retrieval_beats_vector_only_on_two_hop(self):
        wm = build_world()
        graph_hits = set(doc_ids(wm.retrieve(QUERY, top_k=3)))

        vector_only = build_world()
        vector_only.use_ann = True
        vector_only.build_index()
        # Simulate no-expansion by asking the ANN index directly.
        q = vector_only._encoder.encode([QUERY])[0]  # noqa: SLF001
        raw = vector_only._ann_index.search(q, QUERY, top_k=3)  # noqa: SLF001
        vec_hits = {m["node_id"] for m in raw if m["node_id"].startswith("doc::")}

        gold = {"doc::answer"}
        self.assertGreater(
            len(graph_hits & gold), len(vec_hits & gold),
            f"graph={sorted(graph_hits)} vector={sorted(vec_hits)}. Graph "
            "retrieval must find the two-hop answer that dense retrieval "
            "misses; that is the whole claim.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
