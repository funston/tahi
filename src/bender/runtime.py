from typing import Optional, Sequence

from .fusion import FusionModule, WeightedBlendFusion
from .integration import BlackBoxIntegration, ModelIntegration
from .models import CognitiveState
from .planner import Planner
from .rules import RuleEngine
from .simulator import Simulator
from .world_state import WorldModel


class BenderRuntime:
    def __init__(
        self,
        world_model: WorldModel,
        integration: Optional[ModelIntegration] = None,
        fusion: Optional[FusionModule] = None,
        planner: Optional[Planner] = None,
        rules: Optional[RuleEngine] = None,
        simulator: Optional[Simulator] = None,
        top_k: int = 3,
    ):
        self.world_model = world_model
        self.integration = integration or BlackBoxIntegration()
        self.fusion = fusion or WeightedBlendFusion()
        self.planner = planner or Planner()
        self.rules = rules or RuleEngine()
        self.simulator = simulator or Simulator()
        self.top_k = top_k

    def infer(
        self,
        query: str,
        mode: str = "coprocessor",
        hidden_state: Optional[Sequence[float]] = None,
        decode_step: int = 0,
    ) -> CognitiveState:
        width = 8
        if self.world_model.use_ann and self.world_model._encoder:
            width = self.world_model._encoder.dimension
        elif self.world_model.use_ann:
            # Rebuild index or at least load encoder to get dimension
            self.world_model.build_index()
            width = self.world_model._encoder.dimension

        frame = self.integration.capture(
            query=query,
            mode=mode,
            hidden_state=hidden_state,
            decode_step=decode_step,
            width=width,
        )
        state = CognitiveState(mode=mode, decode_step=frame.decode_step)
        state.add_provenance(
            "capture",
            f"integration:{self.integration.name}",
            "Captured a semantic frame from the model-side query state.",
        )

        retrievals = self.world_model.retrieve(
            query=frame.semantic_query or query,
            top_k=self.top_k,
            query_embedding=frame.hidden_state or frame.text_embedding,
        )
        state.retrievals = retrievals
        self.planner.plan(query, state)

        seen_relations = set()
        for retrieval in state.retrievals:
            state.entities.append(self.world_model.entity_ref(retrieval.node_id, score=retrieval.score))
            for relation in retrieval.relations:
                relation_key = (relation.source, relation.relation, relation.target)
                if relation_key in seen_relations:
                    continue
                seen_relations.add(relation_key)
                state.relations.append(relation)
            state.add_provenance(
                "retrieval",
                f"retrieval:{retrieval.node_id}",
                f"Retrieved {retrieval.label} from the world model.",
                confidence=retrieval.score,
            )

        self.rules.apply(state)
        self.simulator.run(state)

        # Post-reasoning retrieval refinement:
        # Use planning context (constraints, active entities) to weight retrievals
        if state.constraints and state.retrievals:
            # If the planner identified a specific DB, penalize others
            target_db = state.constraints.get("db_id", "").lower()
            if target_db:
                for item in state.retrievals:
                    if target_db not in item.node_id.lower():
                        # Penalize distractor scores
                        item.score *= 0.1

        token_signal = frame.hidden_state or frame.text_embedding
        width = 8
        if self.world_model.use_ann and self.world_model._encoder:
            width = self.world_model._encoder.dimension
            
        graph_signal = self.world_model.graph_signal(state.retrievals, width=width)
        state.fused_signal = self.fusion.mix(token_signal=token_signal, graph_signal=graph_signal, state=state)
        state.add_provenance(
            "fusion",
            f"fusion:{state.fused_signal.mixer}",
            "Mixed model-side state with graph-side state into a coprocessor signal.",
            confidence=state.fused_signal.graph_weight,
        )

        state.control_packet = self.integration.inject(frame=frame, state=state, fused=state.fused_signal)
        state.add_provenance(
            "integration",
            f"inject:{self.integration.name}",
            "Prepared the model-specific packet for inference-time integration.",
        )
        return state
