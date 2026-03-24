from abc import ABC, abstractmethod
from typing import Sequence

from .models import CognitiveState, FusedSignal, Vector, coerce_vector


class FusionModule(ABC):
    @abstractmethod
    def mix(
        self,
        token_signal: Sequence[float],
        graph_signal: Sequence[float],
        state: CognitiveState,
    ) -> FusedSignal:
        raise NotImplementedError


class WeightedBlendFusion(FusionModule):
    def __init__(self, width: int = 8):
        self.width = width

    def mix(
        self,
        token_signal: Sequence[float],
        graph_signal: Sequence[float],
        state: CognitiveState,
    ) -> FusedSignal:
        actual_width = len(graph_signal)
        token = coerce_vector(token_signal, width=actual_width)
        
        # Calculate a relevance-weighted graph signal instead of a simple average
        # This prevents low-scoring distractors from washing out the gold signal
        if state.retrievals:
            total_score = sum(item.score for item in state.retrievals)
            if total_score > 0:
                # Start with a zero vector of the correct dimension
                weighted_graph = [0.0] * actual_width
                for item in state.retrievals:
                    # Retrieve the embedding for this specific node
                    # Note: in a production setting, these would be pre-cached
                    node_text = f"{item.label} {item.attributes.get('summary', '')}"
                    from .retrieval.ann import get_encoder
                    node_vector = get_encoder().encode([node_text])[0]
                    
                    weight = item.score / total_score
                    for i in range(actual_width):
                        weighted_graph[i] += float(node_vector[i]) * weight
                graph = tuple(weighted_graph)
            else:
                graph = coerce_vector(graph_signal, width=actual_width)
        else:
            graph = coerce_vector(graph_signal, width=actual_width)

        retrieval_strength = sum(item.score for item in state.retrievals) / max(len(state.retrievals), 1)
        hypothesis_bonus = 0.05 * len(state.hypotheses)
        constraint_bonus = 0.03 * len(state.constraints)
        graph_weight = min(0.85, max(0.15, retrieval_strength + hypothesis_bonus + constraint_bonus))
        token_weight = max(0.15, 1.0 - graph_weight)
        total = token_weight + graph_weight
        token_weight /= total
        graph_weight /= total
        fused: Vector = tuple(
            token_weight * token_value + graph_weight * graph_value
            for token_value, graph_value in zip(token, graph)
        )
        rationale = (
            "Graph weight rises with retrieved support and reasoning state; "
            "token weight preserves the base-model semantic trajectory."
        )
        return FusedSignal(
            mixer=self.__class__.__name__,
            token_weight=round(token_weight, 4),
            graph_weight=round(graph_weight, 4),
            vector=fused,
            rationale=rationale,
        )
