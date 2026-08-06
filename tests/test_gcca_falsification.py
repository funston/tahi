"""
Falsification tests for Level 3 (native GCCA residual injection).

These convert architectural claims about Level 3 into assertions that either
pass or fail. Two of them are expected to FAIL against the current
implementation -- that is the point. They mark the exact distance between what
the pitch describes and what the code does, and they turn "Level 3 is a
prototype" from a hand-wave into a test result.

Run:  PYTHONPATH=src python -m pytest tests/test_gcca_falsification.py -v
"""

import os
import sys
import unittest

import torch

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
for p in (ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from octo.integration import NativeIntegration  # noqa: E402
from octo.models import CognitiveState, EntityRef, FusedSignal  # noqa: E402
from octo.native.gcca_layer import GatedChunkedCrossAttention  # noqa: E402


class GCCAIdentityTests(unittest.TestCase):
    """At alpha=0, GCCA is mathematically an identity function."""

    def test_untrained_gcca_is_exactly_identity(self):
        """h + tanh(0) * attn == h, bit-for-bit.

        This is the load-bearing fact about Level 3 as it currently stands:
        an untrained adapter cannot change a single logit. Any benchmark that
        reports a Level 3 vs base-model difference without having trained the
        adapter is reporting noise from somewhere else.
        """
        torch.manual_seed(0)
        gcca = GatedChunkedCrossAttention(d_model=64, d_retriever=64)
        gcca.eval()

        h = torch.randn(2, 8, 64)
        memory = torch.randn(2, 4, 64)

        with torch.no_grad():
            out = gcca(h, memory)

        self.assertTrue(
            torch.equal(out, h),
            "Untrained GCCA must be an exact identity; alpha is zero-initialized.",
        )

    def test_gcca_becomes_active_once_alpha_moves(self):
        """The adapter is wired correctly -- it only needs training to matter."""
        torch.manual_seed(0)
        gcca = GatedChunkedCrossAttention(d_model=64, d_retriever=64)
        gcca.eval()
        with torch.no_grad():
            gcca.alpha.fill_(1.0)

        h = torch.randn(2, 8, 64)
        memory = torch.randn(2, 4, 64)
        with torch.no_grad():
            out = gcca(h, memory)

        self.assertFalse(
            torch.equal(out, h),
            "With alpha != 0 the residual must alter hidden states.",
        )

    def test_only_adapter_params_are_trainable(self):
        """The <2% trainable-overhead claim: verify what actually has grads."""
        gcca = GatedChunkedCrossAttention(d_model=768, d_retriever=768)
        trainable = [n for n, p in gcca.named_parameters() if p.requires_grad]
        self.assertIn("alpha", trainable)
        self.assertTrue(any("w_k" in n for n in trainable))
        self.assertTrue(any("w_v" in n for n in trainable))


class MemorySignalTests(unittest.TestCase):
    """The injected memory tensor must actually carry query-specific information."""

    def _packet_vector(self, query: str, entities: list[str]) -> torch.Tensor:
        integration = NativeIntegration()
        state = CognitiveState(
            entities=[EntityRef(id=e, label=e, type="Concept") for e in entities],
            constraints={},
        )
        # This mirrors how the retracted harness built the fused signal.
        fused = FusedSignal(
            mixer="gcca_fusion",
            token_weight=0.5,
            graph_weight=0.5,
            vector=tuple([0.1] * 768),
            rationale="constant vector -- see test docstring",
        )
        frame = integration.capture(query=query)
        packet = integration.inject(frame=frame, state=state, fused=fused)
        return packet.metadata["native_tensor"]

    def test_memory_tensor_varies_with_query(self):
        """Verify that the injected memory tensor varies with the query and entities.

        Now passes because NativeIntegration.inject() constructs real slot vectors from state entities.
        """
        a = self._packet_vector("Who founded Apple?", ["Apple", "Steve Jobs"])
        b = self._packet_vector("What is the capital of Peru?", ["Peru", "Lima"])
        self.assertFalse(
            torch.equal(a, b),
            "Two unrelated queries must not produce identical memory tensors.",
        )

    def test_memory_tensor_rank_supports_multiple_retrieved_nodes(self):
        """Verify that memory is formatted with K > 1 slots when multiple entities/nodes exist.

        Now passes because NativeIntegration.inject() builds multi-slot tensors [1, K, d].
        """
        tensor = self._packet_vector("Who founded Apple?", ["Apple", "Steve Jobs"])
        self.assertGreater(
            tensor.shape[1], 1, f"Expected K>1 memory slots, got shape {tuple(tensor.shape)}"
        )


class DeviceHonestyTests(unittest.TestCase):
    """Device selection must not silently degrade."""

    def test_gcca_footprint_is_far_below_any_plausible_oom(self):
        """The retracted harness caught every CUDA error as 'memory allocation
        skipped' and fell back to CPU. Quantify why that label was wrong.

        A d_model=768 adapter is ~14 MB in fp32. It cannot OOM a modern GPU.
        The catch-all was hiding a different error (no CUDA context, driver or
        toolkit mismatch) behind a memory-shaped message, and the CPU fallback
        then produced a result file that looked identical to a GPU run.
        """
        gcca = GatedChunkedCrossAttention(d_model=768, d_retriever=768)
        n_params = sum(p.numel() for p in gcca.parameters())
        megabytes = n_params * 4 / 1e6
        self.assertLess(
            megabytes, 50.0,
            f"GCCA is {megabytes:.1f} MB -- an OOM here indicates a different fault.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
