"""TAHI — a knowledge graph consulted during and after LLM generation.

Two mechanisms put the graph inside the generation loop:

    validate.constrained.GraphConstrainedLogits   masks logits at every decode
                                                  step, so entities the graph
                                                  does not support cannot be
                                                  emitted
    native.gcca_layer.GatedCrossAttention         gated cross-attention from a
                                                  graph memory tensor into the
                                                  model's hidden states

Everything else here is the retrieval and scoring that feeds them.
"""
from ._version import __version__
from .adapter import wrap_llm
from .fusion import FusionModule, WeightedBlendFusion
from .integration import BlackBoxIntegration, ModelIntegration, NativeIntegration
from .runtime import TahiRuntime
from .world_model_store import WorldModelManifest, WorldModelStore
from .world_state import WorldModel

__all__ = [
    "__version__",
    "BlackBoxIntegration",
    "FusionModule",
    "ModelIntegration",
    "NativeIntegration",
    "TahiRuntime",
    "WeightedBlendFusion",
    "WorldModel",
    "WorldModelManifest",
    "WorldModelStore",
    "wrap_llm",
]
