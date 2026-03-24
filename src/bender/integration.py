from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .models import CognitiveState, ControlPacket, FusedSignal, SemanticFrame, coerce_vector
from .retrieval import embed_text, tokenize


class ModelIntegration(ABC):
    name = "abstract"

    @abstractmethod
    def capture(
        self,
        query: str,
        mode: str = "coprocessor",
        hidden_state: Optional[Sequence[float]] = None,
        decode_step: int = 0,
    ) -> SemanticFrame:
        raise NotImplementedError

    @abstractmethod
    def inject(self, frame: SemanticFrame, state: CognitiveState, fused: FusedSignal) -> ControlPacket:
        raise NotImplementedError


class BlackBoxIntegration(ModelIntegration):
    name = "black_box"

    def capture(
        self,
        query: str,
        mode: str = "coprocessor",
        hidden_state: Optional[Sequence[float]] = None,
        decode_step: int = 0,
        width: int = 8,
    ) -> SemanticFrame:
        del hidden_state
        return SemanticFrame(
            query=query,
            mode=mode,
            decode_step=decode_step,
            semantic_query=query,
            text_embedding=embed_text(query, width=width),
            hidden_state=None,
            token_window=tokenize(query),
            metadata={"integration": self.name},
        )

    def inject(self, frame: SemanticFrame, state: CognitiveState, fused: FusedSignal) -> ControlPacket:
        hints = []
        if state.active_entity_labels():
            hints.append(f"Focus on retrieved entities: {', '.join(state.active_entity_labels())}.")
        if state.constraints:
            hints.append(f"Respect structured constraints: {state.constraints}.")
        if state.hypotheses:
            hints.append(f"Prioritize coprocessor hypotheses: {state.hypothesis_texts()}.")
        hints.append("Treat the packet as world-model guidance, not replacement text retrieval.")
        return ControlPacket(
            integration=self.name,
            prompt_hints=hints,
            active_entities=state.active_entity_labels(),
            hypotheses=state.hypothesis_texts(),
            constraints=dict(state.constraints),
            fused_vector=fused.vector,
            provenance=state.provenance,
            metadata={
                "mode": frame.mode,
                "adapter_action": "structured_control_context",
            },
        )


class NativeIntegration(ModelIntegration):
    name = "native_hidden_state"

    def capture(
        self,
        query: str,
        mode: str = "coprocessor",
        hidden_state: Optional[Sequence[float]] = None,
        decode_step: int = 0,
        width: int = 8,
    ) -> SemanticFrame:
        text_embedding = embed_text(query, width=width)
        actual_width = len(hidden_state) if hidden_state is not None else width
        return SemanticFrame(
            query=query,
            mode=mode,
            decode_step=decode_step,
            semantic_query=query,
            text_embedding=text_embedding,
            hidden_state=coerce_vector(hidden_state, width=actual_width) if hidden_state is not None else text_embedding,
            token_window=tokenize(query),
            metadata={"integration": self.name},
        )

    def inject(self, frame: SemanticFrame, state: CognitiveState, fused: FusedSignal) -> ControlPacket:
        return ControlPacket(
            integration=self.name,
            prompt_hints=[
                "Apply fused world-model delta to the model-side adapter or cross-attention hook.",
                "Preserve base-model decoding while biasing toward structured biomedical state.",
            ],
            active_entities=state.active_entity_labels(),
            hypotheses=state.hypothesis_texts(),
            constraints=dict(state.constraints),
            fused_vector=fused.vector,
            provenance=state.provenance,
            metadata={
                "mode": frame.mode,
                "adapter_action": "hidden_state_delta",
                "hidden_state_present": frame.hidden_state is not None,
            },
        )


@dataclass
class TokenformerCoprocessorContext:
    target_runtime: str = "scalarlm_vllm_tokenformer"
    surgeon_path: str = "../scalarlm/vllm-fork/vllm/tokenformer/tokenformer_surgeon.py"
    manager_path: str = "../scalarlm/vllm-fork/vllm/tokenformer/tokenformer_model_manager.py"
    runner_path: str = "../scalarlm/vllm-fork/vllm/v1/worker/lora_model_runner_mixin.py"
    target_layers: list[str] = field(default_factory=lambda: ["model.layers.*.mlp"])
    injection_mode: str = "residual_delta"
    request_scoped: bool = True
    fused_vector: tuple[float, ...] = field(default_factory=tuple)
    active_entities: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    constraints: dict = field(default_factory=dict)
    provenance: list[str] = field(default_factory=list)
    decode_step: int = 0
    mode: str = "latent"
    world_model_weight: float = 1.0
    refinement_boost: float = 0.0


class NativeTokenformerIntegration(NativeIntegration):
    """Design stub for ScalarLM Tokenformer-native BENDER integration."""

    name = "native_tokenformer"

    def inject(self, frame: SemanticFrame, state: CognitiveState, fused: FusedSignal) -> ControlPacket:
        packet = super().inject(frame=frame, state=state, fused=fused)
        packet.integration = self.name
        packet.prompt_hints = [
            "Inject the BENDER coprocessor delta through Tokenformer-wrapped late MLP blocks.",
            "Use request-scoped context rather than static adapter weights.",
        ]
        packet.metadata.update(
            {
                "adapter_action": "tokenformer_coprocessor_delta",
                "target_runtime": "scalarlm_vllm_tokenformer",
                "surgeon_path": "../scalarlm/vllm-fork/vllm/tokenformer/tokenformer_surgeon.py",
                "manager_path": "../scalarlm/vllm-fork/vllm/tokenformer/tokenformer_model_manager.py",
                "runner_path": "../scalarlm/vllm-fork/vllm/v1/worker/lora_model_runner_mixin.py",
                "request_scoped": True,
            }
        )
        return packet

    def build_tokenformer_context(
        self,
        frame: SemanticFrame,
        state: CognitiveState,
        fused: FusedSignal,
        world_model_weight: float = 1.0,
        refinement_boost: float = 0.0,
    ) -> TokenformerCoprocessorContext:
        return TokenformerCoprocessorContext(
            fused_vector=fused.vector,
            active_entities=state.active_entity_labels(),
            hypotheses=state.hypothesis_texts(),
            constraints=dict(state.constraints),
            provenance=state.provenance,
            decode_step=frame.decode_step,
            mode=frame.mode,
            world_model_weight=world_model_weight,
            refinement_boost=refinement_boost,
        )

    def attach_to_scalarlm(self, *args, **kwargs) -> None:
        del args, kwargs
        raise NotImplementedError(
            "This design stub targets ScalarLM's Tokenformer surgeon path, "
            "but the actual patch must be applied inside ../scalarlm where the "
            "request-scoped adapter context can be wired into vLLM workers."
        )
