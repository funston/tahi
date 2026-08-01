from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


Vector = Tuple[float, ...]


@dataclass
class EntityRef:
    id: str
    label: str
    type: str
    score: float = 1.0
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationRef:
    source: str
    relation: str
    target: str
    score: float = 1.0
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Hypothesis:
    text: str
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    kind: str = "inference"


@dataclass
class RetrievedMemory:
    node_id: str
    label: str
    node_type: str
    score: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    relations: List[RelationRef] = field(default_factory=list)


@dataclass
class ProvenanceRecord:
    stage: str
    reference: str
    detail: str
    confidence: float = 1.0


@dataclass
class SemanticFrame:
    query: str
    mode: str = "coprocessor"
    decode_step: int = 0
    semantic_query: str = ""
    text_embedding: Vector = field(default_factory=tuple)
    hidden_state: Optional[Vector] = None
    token_window: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FusedSignal:
    mixer: str
    token_weight: float
    graph_weight: float
    vector: Vector
    rationale: str


@dataclass
class ControlPacket:
    integration: str
    prompt_hints: List[str]
    active_entities: List[str]
    hypotheses: List[str]
    constraints: Dict[str, Any]
    fused_vector: Vector
    provenance: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveState:
    mode: str = "coprocessor"
    decode_step: int = 0
    entities: List[EntityRef] = field(default_factory=list)
    relations: List[RelationRef] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    hypotheses: List[Hypothesis] = field(default_factory=list)
    planner_state: Dict[str, Any] = field(default_factory=dict)
    simulation_state: Dict[str, Any] = field(default_factory=dict)
    retrievals: List[RetrievedMemory] = field(default_factory=list)
    provenance_records: List[ProvenanceRecord] = field(default_factory=list)
    confidence: Dict[str, float] = field(default_factory=dict)
    fused_signal: Optional[FusedSignal] = None
    control_packet: Optional[ControlPacket] = None

    @property
    def provenance(self) -> List[str]:
        return [record.reference for record in self.provenance_records]

    def add_provenance(
        self,
        stage: str,
        reference: str,
        detail: str,
        confidence: float = 1.0,
    ) -> None:
        self.provenance_records.append(
            ProvenanceRecord(
                stage=stage,
                reference=reference,
                detail=detail,
                confidence=confidence,
            )
        )

    def active_entity_labels(self) -> List[str]:
        seen = set()
        labels: List[str] = []
        for entity in self.entities:
            key = entity.label.lower()
            if key not in seen:
                labels.append(entity.label)
                seen.add(key)
        return labels

    def hypothesis_texts(self) -> List[str]:
        return [hypothesis.text for hypothesis in self.hypotheses]


def coerce_vector(values: Optional[Sequence[float]], width: int = 8) -> Vector:
    if values is None:
        return tuple(0.0 for _ in range(width))
    items = tuple(float(value) for value in values)
    if len(items) >= width:
        return items[:width]
    return items + tuple(0.0 for _ in range(width - len(items)))
