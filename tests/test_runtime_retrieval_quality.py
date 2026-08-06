"""
Regression test: OctoRuntime must not degrade its own retrieval.

`WorldModel.retrieve` lets a caller supply `query_embedding`, which overrides
the sentence-transformer encoding. `OctoRuntime.infer` used to pass
`frame.text_embedding` -- the character-sum hash from
`octo.retrieval.legacy.embed_text`, generated at the encoder's width so the
dimensions matched and nothing raised.

Effect: every OCTO arm retrieved with a hash while the RAG baseline it was
compared against used real embeddings. That is a confounded comparison, and it
is consistent with OCTO never beating a baseline anywhere in this repo.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from octo.runtime import OctoRuntime  # noqa: E402
from octo.world_state import WorldModel  # noqa: E402

DOCS = {
    "doc::kickoff": "Kickoff for Project Atlas. Owner Dana.",
    "doc::latency": "Atlas latency budget is 200ms p99.",
    "doc::snacks": "Unrelated: office snacks poll.",
    "doc::revenue": "Q3 revenue for Northwind closed at 1.2M.",
}
QUERY = "What is the latency budget for Project Atlas?"


def _world() -> WorldModel:
    wm = WorldModel(domain="test")
    for node_id, text in DOCS.items():
        wm.upsert_node(node_id, type="document", label=node_id,
                       text=text, summary=text)
    wm.use_ann = True
    wm.build_index()
    return wm


class RuntimeRetrievalQualityTests(unittest.TestCase):
    def test_runtime_retrieval_matches_world_model_retrieval(self):
        """infer() must not retrieve worse than calling the world model directly."""
        wm = _world()
        direct = [r.node_id for r in wm.retrieve(QUERY, top_k=2)]
        runtime = OctoRuntime(world_model=_world(), top_k=2)
        via_runtime = [r.node_id for r in runtime.infer(query=QUERY).retrievals]
        self.assertEqual(
            direct, via_runtime,
            "OctoRuntime returned different results than WorldModel.retrieve -- "
            "it is overriding the real encoder with a hash embedding.",
        )

    def test_runtime_finds_the_relevant_document(self):
        """The document that answers the question must be retrieved."""
        runtime = OctoRuntime(world_model=_world(), top_k=2)
        found = [r.node_id for r in runtime.infer(query=QUERY).retrievals]
        self.assertIn("doc::latency", found, f"relevant doc missing; got {found}")

    def test_runtime_does_not_surface_the_obvious_distractor(self):
        runtime = OctoRuntime(world_model=_world(), top_k=2)
        found = [r.node_id for r in runtime.infer(query=QUERY).retrievals]
        self.assertNotIn("doc::snacks", found, f"distractor retrieved; got {found}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
