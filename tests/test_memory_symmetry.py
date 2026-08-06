"""
The train/eval memory representation must be bit-identical.

This is a regression test for the defect that voided the 2026-08-03 L3 run:
`train_gcca.py` encoded `memory_texts` with SentenceTransformer directly while
`run_l3_native.py` built memory through `build_memory_tensor` and, after the
RGAT landed, through a randomly-initialised graph encoder. The adapter was
trained on one distribution and scored on another, so the reported -0.0117
token-F1 delta measured the mismatch rather than the architecture.

Nothing in the harness could have caught it, because both paths were correct in
isolation. These tests assert the property that actually matters: the two sides
receive the same numbers.
"""

import unittest

import numpy as np
import torch

from octo.native.memory_store import (
    MemoryStore, MemoryStoreError, encode_texts, load_memory_store,
    save_memory_store,
)


class _FakeEncoder:
    """Deterministic stand-in for SentenceTransformer.

    Real embeddings are not needed to test that both sides read the same bytes,
    and a fake keeps the test fast and offline.
    """

    dimension = 8

    @staticmethod
    def encode(texts):
        out = []
        for t in texts:
            rng = np.random.RandomState(abs(hash(t)) % (2 ** 31))
            out.append(rng.rand(_FakeEncoder.dimension).astype(np.float32))
        return np.stack(out)


def _make_store(tmpdir, name="memory_vectors.npz"):
    vectors = {
        "qst_0001": encode_texts(_FakeEncoder, ["alpha doc", "beta doc"]),
        "qst_0002": encode_texts(_FakeEncoder, ["gamma doc"]),
        "qst_0003": encode_texts(_FakeEncoder, ["delta doc", "eps doc", "zeta doc"]),
    }
    path = tmpdir / name
    sha = save_memory_store(path, vectors, {
        "memory_source": "oracle", "encoder": "fake-8d",
        "max_slots": 16, "gnn": "off",
    })
    return path, vectors, sha


class TestMemorySymmetry(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_train_and_eval_read_identical_bytes(self):
        """The core guarantee: same question id -> bit-identical tensor."""
        path, _, _ = _make_store(self.tmpdir)

        # Two independent loads stand in for the trainer and the benchmark,
        # which load the file in separate processes.
        train_side = load_memory_store(path)
        eval_side = load_memory_store(path)

        for qid in train_side.question_ids:
            a = train_side.tensor(qid)
            b = eval_side.tensor(qid)
            self.assertIsNotNone(a)
            self.assertEqual(a.shape, b.shape)
            self.assertTrue(
                torch.equal(a, b),
                f"{qid}: train and eval memory differ -- the L3 comparison "
                "would measure a representation mismatch, not the architecture.",
            )

    def test_shape_is_batch_slots_dim(self):
        """GCCA expects [1, K, d]; K varies per question and must not be padded."""
        path, vectors, _ = _make_store(self.tmpdir)
        store = load_memory_store(path)
        for qid, vec in vectors.items():
            t = store.tensor(qid)
            self.assertEqual(t.shape, (1, vec.shape[0], vec.shape[1]))

    def test_slots_are_l2_normalised(self):
        """Matches `build_memory_tensor`, so a retrieved-source store is
        numerically interchangeable with the live retrieval path."""
        path, _, _ = _make_store(self.tmpdir)
        store = load_memory_store(path)
        for qid in store.question_ids:
            norms = np.linalg.norm(store.slots(qid), axis=1)
            np.testing.assert_allclose(norms, 1.0, rtol=1e-5)

    def test_content_hash_detects_divergence(self):
        """Two stores built from different memory must not compare equal.

        This is what `run_l3_native.py` checks against the sha recorded in the
        checkpoint before it will score an adapter.
        """
        path_a, _, sha_a = _make_store(self.tmpdir, "a.npz")

        different = {
            "qst_0001": encode_texts(_FakeEncoder, ["alpha doc", "DIFFERENT doc"]),
            "qst_0002": encode_texts(_FakeEncoder, ["gamma doc"]),
            "qst_0003": encode_texts(_FakeEncoder, ["delta doc", "eps doc", "zeta doc"]),
        }
        path_b = self.tmpdir / "b.npz"
        sha_b = save_memory_store(path_b, different, {
            "memory_source": "oracle", "encoder": "fake-8d",
            "max_slots": 16, "gnn": "off",
        })

        self.assertNotEqual(
            sha_a, sha_b,
            "A single changed memory slot must change the store hash, or the "
            "checkpoint/benchmark cross-check cannot detect a mismatch.",
        )

    def test_hash_is_order_independent(self):
        """Insertion order must not change the hash, or the cross-check would
        produce false alarms between runs that saw identical memory."""
        _, vectors, sha = _make_store(self.tmpdir, "a.npz")
        reordered = dict(reversed(list(vectors.items())))
        path_b = self.tmpdir / "b.npz"
        sha_b = save_memory_store(path_b, reordered, {
            "memory_source": "oracle", "encoder": "fake-8d",
            "max_slots": 16, "gnn": "off",
        })
        self.assertEqual(sha, sha_b)

    def test_refuses_store_without_provenance(self):
        """An unlabelled store is how a run becomes uninterpretable."""
        with self.assertRaises(MemoryStoreError):
            save_memory_store(
                self.tmpdir / "bad.npz",
                {"qst_0001": encode_texts(_FakeEncoder, ["a doc"])},
                {"encoder": "fake-8d"},   # missing memory_source, max_slots, gnn
            )

    def test_detects_tampering(self):
        """A store edited after the fact must not load silently."""
        path, vectors, _ = _make_store(self.tmpdir)
        with np.load(path, allow_pickle=False) as npz:
            payload = {k: npz[k] for k in npz.files}
        payload["qst_0002"] = payload["qst_0002"] * 2.0   # corrupt one entry
        np.savez_compressed(path, **payload)

        with self.assertRaises(MemoryStoreError):
            load_memory_store(path)

    def test_gnn_transform_would_break_symmetry(self):
        """Demonstrates the actual 2026-08-03 defect.

        Passing stored vectors through an untrained graph encoder produces
        different numbers. This test exists so the property is asserted rather
        than assumed -- `run_l3_native.py` refuses `--memory-store` with
        `--gnn on` for exactly this reason.
        """
        path, _, _ = _make_store(self.tmpdir)
        store = load_memory_store(path)
        trained_side = store.tensor("qst_0001")

        torch.manual_seed(0)
        random_projection = torch.nn.Linear(store.d_model, store.d_model, bias=False)
        with torch.no_grad():
            eval_side = random_projection(trained_side)

        self.assertFalse(
            torch.equal(trained_side, eval_side),
            "If a random projection did not change the memory, this test could "
            "not detect the defect it exists to guard against.",
        )


if __name__ == "__main__":
    unittest.main()
