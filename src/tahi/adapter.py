from collections.abc import Sequence
from dataclasses import dataclass

from .engine import TahiEngine
from .fusion import FusionModule
from .integration import BlackBoxIntegration, ModelIntegration
from .planner import Planner
from .rules import RuleEngine
from .simulator import Simulator
from .world_state import WorldModel


@dataclass
class WrappedLLM:
    model_name: str
    engine: TahiEngine

    def ask(
        self,
        query: str,
        mode: str = "coprocessor",
        trace: bool = False,
        hidden_state: Sequence[float] | None = None,
        decode_step: int = 0,
    ):
        state = self.engine.infer(
            query=query,
            mode=mode,
            hidden_state=hidden_state,
            decode_step=decode_step,
        )
        result = {
            "model": self.model_name,
            "mode": mode,
            "entities": state.active_entity_labels(),
            "relations": [
                {"source": rel.source, "relation": rel.relation, "target": rel.target, "score": rel.score}
                for rel in state.relations
            ],
            "hypotheses": [
                {"text": hypothesis.text, "confidence": hypothesis.confidence, "kind": hypothesis.kind}
                for hypothesis in state.hypotheses
            ],
            "planner_steps": state.planner_state.get("steps", []),
            "constraints": state.constraints,
            "retrievals": [
                {"node_id": item.node_id, "label": item.label, "score": round(item.score, 4)}
                for item in state.retrievals
            ],
            "simulation": state.simulation_state,
            "fusion": {
                "mixer": state.fused_signal.mixer if state.fused_signal else None,
                "token_weight": state.fused_signal.token_weight if state.fused_signal else None,
                "graph_weight": state.fused_signal.graph_weight if state.fused_signal else None,
            },
            "control_packet": {
                "integration": state.control_packet.integration if state.control_packet else None,
                "prompt_hints": state.control_packet.prompt_hints if state.control_packet else [],
                "active_entities": state.control_packet.active_entities if state.control_packet else [],
                "hypotheses": state.control_packet.hypotheses if state.control_packet else [],
                "constraints": state.control_packet.constraints if state.control_packet else {},
                "metadata": state.control_packet.metadata if state.control_packet else {},
            },
        }
        if trace:
            result["provenance"] = [
                {
                    "stage": record.stage,
                    "reference": record.reference,
                    "detail": record.detail,
                    "confidence": record.confidence,
                }
                for record in state.provenance_records
            ]
        return result


def wrap_llm(
    model_name: str,
    world_model: WorldModel | None = None,
    integration: ModelIntegration | None = None,
    fusion: FusionModule | None = None,
    planner: Planner | None = None,
    rules: RuleEngine | None = None,
    simulator: Simulator | None = None,
    top_k: int = 3,
) -> WrappedLLM:
    wm = world_model or WorldModel()
    runtime = TahiEngine(
        world_model=wm,
        integration=integration or BlackBoxIntegration(),
        fusion=fusion,
        planner=planner,
        rules=rules,
        simulator=simulator,
        top_k=top_k,
    )
    return WrappedLLM(model_name=model_name, engine=runtime)
