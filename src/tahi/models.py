from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

Vector = tuple[float, ...]


@dataclass
class EntityRef:
    id: str
    label: str
    type: str
    score: float = 1.0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationRef:
    source: str
    relation: str
    target: str
    score: float = 1.0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hypothesis:
    text: str
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    kind: str = "inference"


@dataclass
class RetrievedMemory:
    node_id: str
    label: str
    node_type: str
    score: float
    attributes: dict[str, Any] = field(default_factory=dict)
    relations: list[RelationRef] = field(default_factory=list)


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
    hidden_state: Vector | None = None
    token_window: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


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
    prompt_hints: list[str]
    active_entities: list[str]
    hypotheses: list[str]
    constraints: dict[str, Any]
    fused_vector: Vector
    provenance: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveState:
    mode: str = "coprocessor"
    decode_step: int = 0
    entities: list[EntityRef] = field(default_factory=list)
    relations: list[RelationRef] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    planner_state: dict[str, Any] = field(default_factory=dict)
    simulation_state: dict[str, Any] = field(default_factory=dict)
    retrievals: list[RetrievedMemory] = field(default_factory=list)
    provenance_records: list[ProvenanceRecord] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)
    fused_signal: FusedSignal | None = None
    control_packet: ControlPacket | None = None

    @property
    def provenance(self) -> list[str]:
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

    def active_entity_labels(self) -> list[str]:
        seen = set()
        labels: list[str] = []
        for entity in self.entities:
            key = entity.label.lower()
            if key not in seen:
                labels.append(entity.label)
                seen.add(key)
        return labels

    def hypothesis_texts(self) -> list[str]:
        return [hypothesis.text for hypothesis in self.hypotheses]


def coerce_vector(values: Sequence[float] | None, width: int = 8) -> Vector:
    if values is None:
        return tuple(0.0 for _ in range(width))
    items = tuple(float(value) for value in values)
    if len(items) >= width:
        return items[:width]
    return items + tuple(0.0 for _ in range(width - len(items)))
