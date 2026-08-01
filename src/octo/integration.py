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


