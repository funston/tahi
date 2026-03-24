import importlib.util
import json
import logging
import os
import sys
import types
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import torch
from torch import nn

from bender.demo_worlds import build_hello_world_animal_model
from bender.integration import NativeTokenformerIntegration
from bender.runtime import BenderRuntime


SCALARLM_ROOT = (
    Path(__file__).resolve().parents[2] / "scalarlm" / "vllm-fork" / "vllm" / "tokenformer"
)


def _ensure_vllm_logger_stub() -> None:
    if "vllm" not in sys.modules:
        sys.modules["vllm"] = types.ModuleType("vllm")
    if "vllm.logger" in sys.modules:
        return

    logger_mod = types.ModuleType("vllm.logger")

    def init_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(name)

    logger_mod.init_logger = init_logger
    sys.modules["vllm.logger"] = logger_mod


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_ensure_vllm_logger_stub()
_bender_coprocessor_mod = _load_module(
    "prototype_bender_coprocessor",
    SCALARLM_ROOT / "bender_coprocessor.py",
)
_tokenformer_surgeon_mod = _load_module(
    "prototype_tokenformer_surgeon",
    SCALARLM_ROOT / "tokenformer_surgeon.py",
)

BenderCoprocessorContext = _bender_coprocessor_mod.BenderCoprocessorContext
BenderCoprocessorSurgeon = _tokenformer_surgeon_mod.BenderCoprocessorSurgeon


class PrototypeActiveBenderBatch:
    def __init__(self, fused_width: int = 8, summary_width: int = 8) -> None:
        self.fused_width = fused_width
        self.summary_width = summary_width
        self.feature_width = fused_width + summary_width
        self.clear()

    def clear(self) -> None:
        self._token_features: list[tuple[float, ...]] = []
        self._token_scales: list[float] = []

    def set_active_contexts(
        self,
        request_contexts: tuple[BenderCoprocessorContext | None, ...],
        num_scheduled_tokens: tuple[int, ...],
    ) -> None:
        self.clear()
        for context, token_count in zip(request_contexts, num_scheduled_tokens):
            if context is None:
                feature = (0.0,) * self.feature_width
                scale = 0.0
            else:
                feature = context.feature_vector(
                    fused_width=self.fused_width,
                    summary_width=self.summary_width,
                )
                scale = context.influence_scale()
            self._token_features.extend([feature] * token_count)
            self._token_scales.extend([scale] * token_count)

    def get_token_inputs(
        self,
        num_tokens: int,
        device: torch.device,
        dtype: torch.dtype,
    ):
        if not self._token_features:
            return None

        features = self._token_features[:num_tokens]
        scales = self._token_scales[:num_tokens]
        if len(features) < num_tokens:
            padding = [(0.0,) * self.feature_width] * (num_tokens - len(features))
            features.extend(padding)
            scales.extend([0.0] * (num_tokens - len(scales)))

        feature_tensor = torch.tensor(features, device=device, dtype=dtype)
        scale_tensor = torch.tensor(scales, device=device, dtype=dtype)
        return feature_tensor, scale_tensor


class ToyLayer(nn.Module):
    def __init__(self, hidden_size: int):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, hidden_size),
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        return self.mlp(hidden_states)


class ToyInnerModel(nn.Module):
    def __init__(self, hidden_size: int, num_layers: int):
        super().__init__()
        self.layers = nn.ModuleList(ToyLayer(hidden_size) for _ in range(num_layers))

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        for layer in self.layers:
            hidden_states = layer(hidden_states)
        return hidden_states


class ToyTokenformerModel(nn.Module):
    def __init__(self, hidden_size: int = 8, num_layers: int = 2):
        super().__init__()
        self.config = SimpleNamespace(
            hidden_size=hidden_size,
            num_hidden_layers=num_layers,
        )
        self.model = ToyInnerModel(hidden_size, num_layers)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        return self.model(hidden_states)


def build_request_context(
    runtime: BenderRuntime,
    query: str,
    hidden_state: list[float],
) -> tuple[dict, BenderCoprocessorContext]:
    state = runtime.infer(
        query=query,
        mode="latent",
        hidden_state=hidden_state,
        decode_step=0,
    )
    packet = state.control_packet
    if packet is None:
        raise RuntimeError("BENDER runtime did not emit a control packet")

    context = BenderCoprocessorContext(
        fused_vector=tuple(packet.fused_vector),
        active_entities=tuple(packet.active_entities),
        hypotheses=tuple(packet.hypotheses),
        constraints=packet.constraints,
        provenance=tuple(packet.provenance),
        decode_step=state.decode_step,
        mode=state.mode,
    )

    return {
        "query": query,
        "active_entities": packet.active_entities,
        "hypotheses": packet.hypotheses,
        "constraints": packet.constraints,
        "fused_vector": list(packet.fused_vector),
    }, context


def tensor_summary(tensor: torch.Tensor) -> list[list[float]]:
    return [[round(float(value), 4) for value in row] for row in tensor.tolist()]


if __name__ == "__main__":
    os.environ.setdefault("BENDER_TOKENFORMER_LATE_LAYER_COUNT", "2")
    torch.manual_seed(7)

    world_model = build_hello_world_animal_model()
    integration = NativeTokenformerIntegration()
    runtime = BenderRuntime(world_model=world_model, integration=integration, top_k=5)

    penguin_packet, penguin_context = build_request_context(
        runtime,
        "Can a penguin fly?",
        [0.7, 0.1, 0.2, 0.9, 0.0, 0.3, 0.5, 0.8],
    )
    antarctica_packet, antarctica_context = build_request_context(
        runtime,
        "What animals in Antarctica eat fish?",
        [0.2, 0.9, 0.1, 0.4, 0.8, 0.3, 0.6, 0.5],
    )

    base_model = ToyTokenformerModel()
    active_batch = PrototypeActiveBenderBatch()
    wrapped_model = deepcopy(base_model)
    wrapped_model = BenderCoprocessorSurgeon(
        wrapped_model,
        device=torch.device("cpu"),
        active_batch=active_batch,
    ).insert_adapter_modules()

    hidden_states = torch.tensor(
        [
            [0.1, 0.5, 0.2, 0.0, 0.3, 0.4, 0.1, 0.9],
            [0.6, 0.2, 0.8, 0.1, 0.4, 0.3, 0.7, 0.5],
        ],
        dtype=torch.float32,
    )

    with torch.no_grad():
        baseline = base_model(hidden_states)

        active_batch.clear()
        no_context = wrapped_model(hidden_states)

        active_batch.set_active_contexts((penguin_context, None), (1, 1))
        penguin_only = wrapped_model(hidden_states)

        active_batch.set_active_contexts(
            (penguin_context, antarctica_context),
            (1, 1),
        )
        two_request_contexts = wrapped_model(hidden_states)

    result = {
        "scalarlm_files": {
            "context": str(SCALARLM_ROOT / "bender_coprocessor.py"),
            "surgeon": str(SCALARLM_ROOT / "tokenformer_surgeon.py"),
        },
        "bender_packets": {
            "penguin": penguin_packet,
            "antarctica": antarctica_packet,
        },
        "prototype_checks": {
            "no_context_matches_base": torch.allclose(baseline, no_context),
            "penguin_context_changes_output": not torch.allclose(
                baseline,
                penguin_only,
            ),
            "second_request_context_changes_batch_output": not torch.allclose(
                penguin_only,
                two_request_contexts,
            ),
        },
        "outputs": {
            "baseline": tensor_summary(baseline),
            "no_context": tensor_summary(no_context),
            "penguin_only": tensor_summary(penguin_only),
            "two_request_contexts": tensor_summary(two_request_contexts),
        },
        "delta_norms": {
            "penguin_only_vs_base": round(
                float(torch.norm(penguin_only - baseline).item()),
                6,
            ),
            "two_request_contexts_vs_base": round(
                float(torch.norm(two_request_contexts - baseline).item()),
                6,
            ),
            "two_request_contexts_vs_penguin_only": round(
                float(torch.norm(two_request_contexts - penguin_only).item()),
                6,
            ),
        },
    }

    print(json.dumps(result, indent=2))
