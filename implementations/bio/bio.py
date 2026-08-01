from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from octo.models import Hypothesis
from octo.world_state import WorldModel


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")


def _truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def _result_class(result_text: str) -> str:
    lowered = result_text.lower()
    if any(token in lowered for token in ("amplified", "positive", "overexpress", "detected", "mutated", "pathogenic")):
        return "positive"
    if any(token in lowered for token in ("negative", "not detected", "wild type", "wild-type", "normal")):
        return "negative"
    return "indeterminate"


@dataclass(frozen=True)
class BioEvidenceSource:
    source_id: str
    title: str
    source_type: str
    summary: str
    citation: str = ""
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class BioEntity:
    entity_id: str
    label: str
    entity_type: str
    summary: str
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BioRelation:
    source_id: str
    relation: str
    target_id: str
    confidence: float = 1.0
    source_refs: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BioKnowledgeBase:
    entities: tuple[BioEntity, ...]
    relations: tuple[BioRelation, ...]
    sources: tuple[BioEvidenceSource, ...]


@dataclass(frozen=True)
class BioEvidenceRecord:
    record_id: str
    source: BioEvidenceSource
    entities: tuple[BioEntity, ...]
    relations: tuple[BioRelation, ...]
    question: str = ""
    notes: str = ""


@dataclass(frozen=True)
class BioInterpretationCase:
    case_id: str
    disease: str
    biomarker: str
    assay: str
    result_text: str
    question: str = ""

    def semantic_query(self) -> str:
        parts = [
            self.question or "interpret biomarker significance",
            self.biomarker,
            self.disease,
            self.assay,
            self.result_text,
        ]
        return " ".join(part for part in parts if part).strip()

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "BioInterpretationCase":
        return cls(
            case_id=str(record.get("case_id") or record.get("id") or "case"),
            disease=str(record.get("disease") or ""),
            biomarker=str(record.get("biomarker") or ""),
            assay=str(record.get("assay") or ""),
            result_text=str(record.get("result_text") or record.get("result") or ""),
            question=str(record.get("question") or ""),
        )


@dataclass(frozen=True)
class BioTargetProfileRequest:
    target: str
    disease: str = ""
    question: str = ""

    def semantic_query(self) -> str:
        parts = [
            self.question or "summarize target mechanism and disease relevance",
            self.target,
            self.disease,
        ]
        return " ".join(part for part in parts if part).strip()


def build_bio_world_model(knowledge_base: BioKnowledgeBase) -> WorldModel:
    world = WorldModel(domain="bio_interpretation")
    world.upsert_node(
        "bio_domain",
        label="Biomedical Interpretation",
        type="domain",
        summary="World-model for biomarker, disease, pathway, therapy, and assay interpretation.",
        keywords=["biomarker", "assay", "disease", "pathway", "therapy", "provenance"],
    )
    for source in knowledge_base.sources:
        world.upsert_node(
            source.source_id,
            label=source.title,
            type="evidence_source",
            summary=_truncate_text(source.summary, 1200),
            keywords=list(source.keywords) or [source.source_type, "evidence"],
            source_type=source.source_type,
            citation=source.citation,
        )
        world.add_edge("bio_domain", "has_source", source.source_id, score=0.95)
    for entity in knowledge_base.entities:
        world.upsert_node(
            entity.entity_id,
            label=entity.label,
            type=entity.entity_type,
            summary=entity.summary,
            aliases=list(entity.aliases),
            keywords=list(entity.keywords),
            **dict(entity.metadata),
        )
        world.add_edge("bio_domain", "contains_entity", entity.entity_id, score=0.97)
    for relation in knowledge_base.relations:
        world.add_edge(
            relation.source_id,
            relation.relation,
            relation.target_id,
            score=relation.confidence,
            source_refs=list(relation.source_refs),
            **dict(relation.attributes),
        )
        for source_ref in relation.source_refs:
            world.add_edge(relation.source_id, "supported_by", source_ref, score=relation.confidence)
            world.add_edge(source_ref, "supports_entity", relation.target_id, score=relation.confidence)
    return world


def build_demo_bio_knowledge_base() -> BioKnowledgeBase:
    sources = (
        BioEvidenceSource(
            source_id="source:her2_guideline",
            title="HER2 Breast Cancer Practice Guideline",
            source_type="guideline",
            summary="HER2 amplification or overexpression in breast cancer predicts benefit from HER2-directed therapy such as trastuzumab.",
            citation="Demo guideline summary",
            keywords=("her2", "breast cancer", "trastuzumab", "guideline"),
        ),
        BioEvidenceSource(
            source_id="source:egfr_guideline",
            title="EGFR NSCLC Targeted Therapy Guidance",
            source_type="guideline",
            summary="Activating EGFR mutations in non-small cell lung cancer are actionable and predict response to EGFR inhibitors such as osimertinib.",
            citation="Demo guideline summary",
            keywords=("egfr", "nsclc", "osimertinib", "guideline"),
        ),
        BioEvidenceSource(
            source_id="source:braf_review",
            title="BRAF V600E Targeted Therapy Review",
            source_type="review",
            summary="BRAF V600E in melanoma is a canonical actionable driver linked to response to BRAF and MEK inhibition.",
            citation="Demo review summary",
            keywords=("braf", "melanoma", "dabrafenib", "trametinib"),
        ),
    )
    entities = (
        BioEntity(
            entity_id="target:erbb2",
            label="ERBB2",
            entity_type="target",
            summary="ERBB2 encodes the HER2 receptor tyrosine kinase and is a canonical oncology target in HER2-driven disease.",
            aliases=("HER2",),
            keywords=("erbb2", "her2", "target", "receptor tyrosine kinase"),
        ),
        BioEntity(
            entity_id="target:egfr",
            label="EGFR",
            entity_type="target",
            summary="EGFR is a receptor tyrosine kinase target with actionable activating mutations in NSCLC and other tumors.",
            keywords=("egfr", "target", "receptor tyrosine kinase"),
        ),
        BioEntity(
            entity_id="target:braf",
            label="BRAF",
            entity_type="target",
            summary="BRAF is a kinase target linked to MAPK signaling and canonical driver alterations such as V600E.",
            keywords=("braf", "target", "kinase", "mapk"),
        ),
        BioEntity(
            entity_id="biomarker:her2_amplification",
            label="HER2 amplification",
            entity_type="biomarker",
            summary="ERBB2/HER2 amplification or overexpression is a canonical actionable breast cancer biomarker.",
            aliases=("ERBB2 amplification", "HER2 positive", "HER2 overexpression"),
            keywords=("her2", "erbb2", "amplification", "overexpression", "breast"),
        ),
        BioEntity(
            entity_id="biomarker:egfr_l858r",
            label="EGFR L858R",
            entity_type="biomarker",
            summary="EGFR L858R is an activating EGFR mutation commonly used to guide targeted therapy in NSCLC.",
            aliases=("EGFR activating mutation", "L858R"),
            keywords=("egfr", "l858r", "nsclc", "activating mutation"),
        ),
        BioEntity(
            entity_id="biomarker:braf_v600e",
            label="BRAF V600E",
            entity_type="biomarker",
            summary="BRAF V600E is a canonical oncogenic driver with targeted therapy relevance in melanoma.",
            aliases=("V600E",),
            keywords=("braf", "v600e", "melanoma", "driver"),
        ),
        BioEntity(
            entity_id="disease:breast_cancer",
            label="Breast cancer",
            entity_type="disease",
            summary="Breast cancer includes HER2-positive subtypes with well-established targeted therapy pathways.",
            keywords=("breast cancer", "her2", "oncology"),
        ),
        BioEntity(
            entity_id="disease:nsclc",
            label="Non-small cell lung cancer",
            entity_type="disease",
            summary="Non-small cell lung cancer includes EGFR-driven subsets that respond to targeted EGFR inhibition.",
            aliases=("NSCLC",),
            keywords=("nsclc", "lung cancer", "egfr"),
        ),
        BioEntity(
            entity_id="disease:melanoma",
            label="Melanoma",
            entity_type="disease",
            summary="Melanoma includes BRAF-driven subsets with targeted treatment options.",
            keywords=("melanoma", "braf", "oncology"),
        ),
        BioEntity(
            entity_id="assay:ihc",
            label="Immunohistochemistry",
            entity_type="assay",
            summary="Immunohistochemistry is used to evaluate protein expression such as HER2 overexpression.",
            aliases=("IHC",),
            keywords=("ihc", "assay", "protein expression"),
        ),
        BioEntity(
            entity_id="assay:pcr_ngs",
            label="Targeted NGS Panel",
            entity_type="assay",
            summary="Targeted next-generation sequencing panels detect actionable sequence variants such as EGFR and BRAF mutations.",
            aliases=("NGS", "PCR panel"),
            keywords=("ngs", "sequencing", "variant detection"),
        ),
        BioEntity(
            entity_id="therapy:trastuzumab",
            label="Trastuzumab",
            entity_type="therapy",
            summary="HER2-directed therapy used in HER2-positive breast cancer.",
            keywords=("trastuzumab", "her2", "targeted therapy"),
        ),
        BioEntity(
            entity_id="therapy:osimertinib",
            label="Osimertinib",
            entity_type="therapy",
            summary="EGFR inhibitor used for actionable EGFR-mutant NSCLC.",
            keywords=("osimertinib", "egfr", "targeted therapy"),
        ),
        BioEntity(
            entity_id="therapy:dabrafenib_trametinib",
            label="Dabrafenib plus trametinib",
            entity_type="therapy",
            summary="BRAF and MEK inhibition strategy for BRAF V600E-positive melanoma.",
            keywords=("dabrafenib", "trametinib", "braf", "mek"),
        ),
        BioEntity(
            entity_id="pathway:her2_signaling",
            label="HER2 signaling",
            entity_type="pathway",
            summary="ERBB2/HER2 receptor signaling pathway implicated in HER2-positive disease biology.",
            keywords=("her2", "erbb2", "signaling"),
        ),
        BioEntity(
            entity_id="pathway:mapk_signaling",
            label="MAPK signaling",
            entity_type="pathway",
            summary="MAPK pathway is downstream of BRAF and frequently implicated in targeted oncology reasoning.",
            keywords=("mapk", "braf", "signaling"),
        ),
    )
    relations = (
        BioRelation(
            source_id="target:erbb2",
            relation="has_biomarker",
            target_id="biomarker:her2_amplification",
            confidence=0.99,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="target:erbb2",
            relation="signals_via",
            target_id="pathway:her2_signaling",
            confidence=0.94,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="target:erbb2",
            relation="implicated_in",
            target_id="disease:breast_cancer",
            confidence=0.95,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="target:erbb2",
            relation="targeted_by",
            target_id="therapy:trastuzumab",
            confidence=0.96,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="biomarker:her2_amplification",
            relation="actionable_in",
            target_id="disease:breast_cancer",
            confidence=0.98,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="biomarker:her2_amplification",
            relation="measured_by",
            target_id="assay:ihc",
            confidence=0.93,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="biomarker:her2_amplification",
            relation="predicts_response_to",
            target_id="therapy:trastuzumab",
            confidence=0.98,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="biomarker:her2_amplification",
            relation="signals_via",
            target_id="pathway:her2_signaling",
            confidence=0.88,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="therapy:trastuzumab",
            relation="approved_for",
            target_id="disease:breast_cancer",
            confidence=0.94,
            source_refs=("source:her2_guideline",),
        ),
        BioRelation(
            source_id="target:egfr",
            relation="has_biomarker",
            target_id="biomarker:egfr_l858r",
            confidence=0.99,
            source_refs=("source:egfr_guideline",),
        ),
        BioRelation(
            source_id="target:egfr",
            relation="implicated_in",
            target_id="disease:nsclc",
            confidence=0.96,
            source_refs=("source:egfr_guideline",),
        ),
        BioRelation(
            source_id="target:egfr",
            relation="targeted_by",
            target_id="therapy:osimertinib",
            confidence=0.97,
            source_refs=("source:egfr_guideline",),
        ),
        BioRelation(
            source_id="biomarker:egfr_l858r",
            relation="actionable_in",
            target_id="disease:nsclc",
            confidence=0.97,
            source_refs=("source:egfr_guideline",),
        ),
        BioRelation(
            source_id="biomarker:egfr_l858r",
            relation="measured_by",
            target_id="assay:pcr_ngs",
            confidence=0.91,
            source_refs=("source:egfr_guideline",),
        ),
        BioRelation(
            source_id="biomarker:egfr_l858r",
            relation="predicts_response_to",
            target_id="therapy:osimertinib",
            confidence=0.97,
            source_refs=("source:egfr_guideline",),
        ),
        BioRelation(
            source_id="therapy:osimertinib",
            relation="approved_for",
            target_id="disease:nsclc",
            confidence=0.94,
            source_refs=("source:egfr_guideline",),
        ),
        BioRelation(
            source_id="target:braf",
            relation="has_biomarker",
            target_id="biomarker:braf_v600e",
            confidence=0.98,
            source_refs=("source:braf_review",),
        ),
        BioRelation(
            source_id="target:braf",
            relation="signals_via",
            target_id="pathway:mapk_signaling",
            confidence=0.95,
            source_refs=("source:braf_review",),
        ),
        BioRelation(
            source_id="target:braf",
            relation="implicated_in",
            target_id="disease:melanoma",
            confidence=0.95,
            source_refs=("source:braf_review",),
        ),
        BioRelation(
            source_id="target:braf",
            relation="targeted_by",
            target_id="therapy:dabrafenib_trametinib",
            confidence=0.95,
            source_refs=("source:braf_review",),
        ),
        BioRelation(
            source_id="biomarker:braf_v600e",
            relation="actionable_in",
            target_id="disease:melanoma",
            confidence=0.96,
            source_refs=("source:braf_review",),
        ),
        BioRelation(
            source_id="biomarker:braf_v600e",
            relation="predicts_response_to",
            target_id="therapy:dabrafenib_trametinib",
            confidence=0.95,
            source_refs=("source:braf_review",),
        ),
        BioRelation(
            source_id="biomarker:braf_v600e",
            relation="signals_via",
            target_id="pathway:mapk_signaling",
            confidence=0.92,
            source_refs=("source:braf_review",),
        ),
        BioRelation(
            source_id="therapy:dabrafenib_trametinib",
            relation="approved_for",
            target_id="disease:melanoma",
            confidence=0.91,
            source_refs=("source:braf_review",),
        ),
    )
    return BioKnowledgeBase(entities=entities, relations=relations, sources=sources)


def load_bio_knowledge_base(path: str | Path) -> BioKnowledgeBase:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entities = tuple(
        BioEntity(
            entity_id=str(record["entity_id"]),
            label=str(record["label"]),
            entity_type=str(record["entity_type"]),
            summary=str(record.get("summary", "")),
            aliases=tuple(str(item) for item in record.get("aliases", [])),
            keywords=tuple(str(item) for item in record.get("keywords", [])),
            metadata=dict(record.get("metadata", {})),
        )
        for record in payload.get("entities", [])
    )
    relations = tuple(
        BioRelation(
            source_id=str(record["source_id"]),
            relation=str(record["relation"]),
            target_id=str(record["target_id"]),
            confidence=float(record.get("confidence", 1.0)),
            source_refs=tuple(str(item) for item in record.get("source_refs", [])),
            attributes=dict(record.get("attributes", {})),
        )
        for record in payload.get("relations", [])
    )
    sources = tuple(
        BioEvidenceSource(
            source_id=str(record["source_id"]),
            title=str(record["title"]),
            source_type=str(record.get("source_type", "evidence")),
            summary=str(record.get("summary", "")),
            citation=str(record.get("citation", "")),
            keywords=tuple(str(item) for item in record.get("keywords", [])),
        )
        for record in payload.get("sources", [])
    )
    return BioKnowledgeBase(entities=entities, relations=relations, sources=sources)


class BioCaseLoader:
    def load(self, path: str | Path) -> list[BioInterpretationCase]:
        path = Path(path)
        if path.suffix == ".jsonl":
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                records = payload
            elif isinstance(payload, dict) and isinstance(payload.get("cases"), list):
                records = payload["cases"]
            else:
                raise ValueError(f"Unsupported bio case payload format in {path}")
        return [BioInterpretationCase.from_record(record) for record in records]


class BioEvidenceRecordLoader:
    def load(self, path: str | Path) -> list[BioEvidenceRecord]:
        path = Path(path)
        if path.suffix == ".jsonl":
            payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                payloads = payload
            elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
                payloads = payload["records"]
            else:
                raise ValueError(f"Unsupported bio evidence payload format in {path}")
        return [build_bio_evidence_record(record) for record in payloads]


def build_bio_evidence_record(payload: dict[str, Any]) -> BioEvidenceRecord:
    source_payload = dict(payload.get("source", {}))
    source = BioEvidenceSource(
        source_id=str(source_payload["source_id"]),
        title=str(source_payload["title"]),
        source_type=str(source_payload.get("source_type", "evidence")),
        summary=str(source_payload.get("summary", "")),
        citation=str(source_payload.get("citation", "")),
        keywords=tuple(str(item) for item in source_payload.get("keywords", [])),
    )
    entities = tuple(
        BioEntity(
            entity_id=str(record["entity_id"]),
            label=str(record["label"]),
            entity_type=str(record["entity_type"]),
            summary=str(record.get("summary", "")),
            aliases=tuple(str(item) for item in record.get("aliases", [])),
            keywords=tuple(str(item) for item in record.get("keywords", [])),
            metadata=dict(record.get("metadata", {})),
        )
        for record in payload.get("entities", [])
    )
    relations = tuple(
        BioRelation(
            source_id=str(record["source_id"]),
            relation=str(record["relation"]),
            target_id=str(record["target_id"]),
            confidence=float(record.get("confidence", 1.0)),
            source_refs=tuple(str(item) for item in record.get("source_refs", [])) or (source.source_id,),
            attributes=dict(record.get("attributes", {})),
        )
        for record in payload.get("relations", [])
    )
    return BioEvidenceRecord(
        record_id=str(payload.get("record_id") or source.source_id),
        source=source,
        entities=entities,
        relations=relations,
        question=str(payload.get("question", "")),
        notes=str(payload.get("notes", "")),
    )


def build_bio_knowledge_base_from_records(records: list[BioEvidenceRecord]) -> BioKnowledgeBase:
    entity_index: dict[str, BioEntity] = {}
    relation_index: dict[tuple[str, str, str, tuple[str, ...]], BioRelation] = {}
    source_index: dict[str, BioEvidenceSource] = {}

    for record in records:
        source_index[record.source.source_id] = record.source
        for entity in record.entities:
            entity_index[entity.entity_id] = entity
        for relation in record.relations:
            key = (
                relation.source_id,
                relation.relation,
                relation.target_id,
                tuple(sorted(relation.source_refs)),
            )
            relation_index[key] = relation

    return BioKnowledgeBase(
        entities=tuple(entity_index.values()),
        relations=tuple(relation_index.values()),
        sources=tuple(source_index.values()),
    )


@dataclass(frozen=True)
class BioWorkspace:
    repo_root: Path | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", Path(self.repo_root))

    def resolve_knowledge_base_path(self) -> Path:
        candidates = [
            self.repo_root / "demo_biomarker_kb.json",
            self.repo_root / "data" / "demo_biomarker_kb.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not resolve a bio knowledge base under {self.repo_root}")

    def resolve_cases_path(self) -> Path:
        candidates = [
            self.repo_root / "demo_cases.json",
            self.repo_root / "data" / "demo_cases.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not resolve bio demo cases under {self.repo_root}")

    def resolve_evidence_records_path(self) -> Path:
        candidates = [
            self.repo_root / "demo_evidence_records.jsonl",
            self.repo_root / "data" / "demo_evidence_records.jsonl",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not resolve bio evidence records under {self.repo_root}")

    def load_knowledge_base(self) -> BioKnowledgeBase:
        return load_bio_knowledge_base(self.resolve_knowledge_base_path())

    def load_cases(self) -> list[BioInterpretationCase]:
        return BioCaseLoader().load(self.resolve_cases_path())

    def load_evidence_records(self) -> list[BioEvidenceRecord]:
        return BioEvidenceRecordLoader().load(self.resolve_evidence_records_path())


class BioInterpretationAdapter:
    def __init__(self, world_model: WorldModel) -> None:
        self.world_model = world_model

    def run_case(self, case: BioInterpretationCase, *, top_k: int = 8) -> dict[str, Any]:
        biomarker_id = self._resolve_entity(case.biomarker, entity_type="biomarker")
        disease_id = self._resolve_entity(case.disease, entity_type="disease")
        assay_id = self._resolve_entity(case.assay, entity_type="assay") if case.assay else None
        result_class = _result_class(case.result_text)
        retrievals = self.world_model.retrieve(case.semantic_query(), top_k=top_k)
        hypotheses = self._derive_hypotheses(
            biomarker_id=biomarker_id,
            disease_id=disease_id,
            assay_id=assay_id,
            result_class=result_class,
        )
        provenance = self._collect_provenance(hypotheses)
        return {
            "case_id": case.case_id,
            "normalized_entities": {
                "biomarker": biomarker_id,
                "disease": disease_id,
                "assay": assay_id,
            },
            "result_class": result_class,
            "retrieved_entities": [
                {
                    "node_id": item.node_id,
                    "label": item.label,
                    "type": item.node_type,
                    "score": item.score,
                }
                for item in retrievals
            ],
            "hypotheses": [
                {
                    "text": hypothesis.text,
                    "confidence": hypothesis.confidence,
                    "kind": hypothesis.kind,
                    "evidence": list(hypothesis.evidence),
                }
                for hypothesis in hypotheses
            ],
            "provenance": provenance,
        }

    def run_target_profile(self, request: BioTargetProfileRequest, *, top_k: int = 8) -> dict[str, Any]:
        target_id = self._resolve_entity(request.target, entity_type="target")
        disease_id = self._resolve_entity(request.disease, entity_type="disease") if request.disease else None
        retrievals = self.world_model.retrieve(request.semantic_query(), top_k=top_k)
        linked_entities = self._collect_linked_entities(target_id)
        hypotheses = self._derive_target_profile_hypotheses(target_id=target_id, disease_id=disease_id)
        provenance = self._collect_provenance(hypotheses)
        return {
            "target": request.target,
            "disease": request.disease,
            "normalized_entities": {
                "target": target_id,
                "disease": disease_id,
            },
            "retrieved_entities": [
                {
                    "node_id": item.node_id,
                    "label": item.label,
                    "type": item.node_type,
                    "score": item.score,
                }
                for item in retrievals
            ],
            "linked_entities": linked_entities,
            "hypotheses": [
                {
                    "text": hypothesis.text,
                    "confidence": hypothesis.confidence,
                    "kind": hypothesis.kind,
                    "evidence": list(hypothesis.evidence),
                }
                for hypothesis in hypotheses
            ],
            "provenance": provenance,
        }

    def _resolve_entity(self, text: str, *, entity_type: str) -> str | None:
        normalized = _normalize_identifier(text)
        best_id = None
        best_score = float("-inf")
        for node_id, node in self.world_model.nodes.items():
            if node.get("type") != entity_type:
                continue
            candidates = [str(node.get("label", "")), *[str(alias) for alias in node.get("aliases", [])]]
            score = 0.0
            for candidate in candidates:
                candidate_norm = _normalize_identifier(candidate)
                if candidate_norm == normalized:
                    score += 20.0
                elif normalized and normalized in candidate_norm:
                    score += 8.0
                elif candidate_norm and candidate_norm in normalized:
                    score += 6.0
            if score > best_score:
                best_score = score
                best_id = node_id
        if best_score <= 0.0:
            return None
        return best_id

    def _collect_linked_entities(self, target_id: str | None) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {
            "biomarkers": [],
            "pathways": [],
            "therapies": [],
            "diseases": [],
        }
        if target_id is None:
            return grouped
        relation_to_group = {
            "has_biomarker": "biomarkers",
            "signals_via": "pathways",
            "targeted_by": "therapies",
            "implicated_in": "diseases",
        }
        for src, rel, dst, attrs in self.world_model.edges:
            if src != target_id or rel not in relation_to_group:
                continue
            grouped[relation_to_group[rel]].append(
                {
                    "node_id": dst,
                    "label": self.world_model.nodes.get(dst, {}).get("label", dst),
                    "confidence": float(attrs.get("score", 0.8)),
                    "evidence": list(attrs.get("source_refs", [])),
                }
            )
        return grouped

    def _derive_hypotheses(
        self,
        *,
        biomarker_id: str | None,
        disease_id: str | None,
        assay_id: str | None,
        result_class: str,
    ) -> list[Hypothesis]:
        if biomarker_id is None:
            return []
        if result_class != "positive":
            return [
                Hypothesis(
                    text="The reported biomarker result is not clearly positive, so actionability should not be asserted without more context.",
                    confidence=0.55,
                    evidence=[],
                    kind="guardrail",
                )
            ]
        biomarker_label = self.world_model.nodes[biomarker_id]["label"]
        disease_label = self.world_model.nodes.get(disease_id or "", {}).get("label", "the stated disease")
        hypotheses: list[Hypothesis] = []
        for src, rel, dst, attrs in self.world_model.edges:
            if src != biomarker_id:
                continue
            source_refs = [str(item) for item in attrs.get("source_refs", [])]
            score = float(attrs.get("score", 0.8))
            if rel == "actionable_in" and (disease_id is None or dst == disease_id):
                hypotheses.append(
                    Hypothesis(
                        text=f"{biomarker_label} appears actionable in {disease_label}.",
                        confidence=score,
                        evidence=source_refs,
                        kind="actionability",
                    )
                )
            if rel == "predicts_response_to":
                therapy_label = self.world_model.nodes.get(dst, {}).get("label", dst)
                hypotheses.append(
                    Hypothesis(
                        text=f"{biomarker_label} supports considering {therapy_label} in the appropriate disease context.",
                        confidence=score,
                        evidence=source_refs,
                        kind="therapy_response",
                    )
                )
            if assay_id is not None and rel == "measured_by" and dst == assay_id:
                assay_label = self.world_model.nodes.get(dst, {}).get("label", dst)
                hypotheses.append(
                    Hypothesis(
                        text=f"{assay_label} is a compatible assay context for interpreting {biomarker_label}.",
                        confidence=score,
                        evidence=source_refs,
                        kind="assay_context",
                    )
                )
            if rel == "signals_via":
                pathway_label = self.world_model.nodes.get(dst, {}).get("label", dst)
                hypotheses.append(
                    Hypothesis(
                        text=f"{biomarker_label} is linked to {pathway_label}, which may help explain mechanism and downstream reasoning.",
                        confidence=score,
                        evidence=source_refs,
                        kind="mechanism",
                    )
                )
        return hypotheses

    def _derive_target_profile_hypotheses(
        self,
        *,
        target_id: str | None,
        disease_id: str | None,
    ) -> list[Hypothesis]:
        if target_id is None:
            return []
        target_label = self.world_model.nodes[target_id]["label"]
        disease_label = self.world_model.nodes.get(disease_id or "", {}).get("label", "the requested disease")
        hypotheses: list[Hypothesis] = []
        biomarker_ids: list[str] = []

        for src, rel, dst, attrs in self.world_model.edges:
            if src != target_id:
                continue
            source_refs = [str(item) for item in attrs.get("source_refs", [])]
            score = float(attrs.get("score", 0.8))
            if rel == "has_biomarker":
                biomarker_ids.append(dst)
                biomarker_label = self.world_model.nodes.get(dst, {}).get("label", dst)
                hypotheses.append(
                    Hypothesis(
                        text=f"{target_label} is linked to biomarker evidence through {biomarker_label}.",
                        confidence=score,
                        evidence=source_refs,
                        kind="biomarker_link",
                    )
                )
            elif rel == "signals_via":
                pathway_label = self.world_model.nodes.get(dst, {}).get("label", dst)
                hypotheses.append(
                    Hypothesis(
                        text=f"{target_label} is mechanistically tied to {pathway_label}.",
                        confidence=score,
                        evidence=source_refs,
                        kind="mechanism",
                    )
                )
            elif rel == "implicated_in" and (disease_id is None or dst == disease_id):
                hypotheses.append(
                    Hypothesis(
                        text=f"{target_label} appears relevant in {disease_label}.",
                        confidence=score,
                        evidence=source_refs,
                        kind="disease_relevance",
                    )
                )
            elif rel == "targeted_by":
                therapy_label = self.world_model.nodes.get(dst, {}).get("label", dst)
                hypotheses.append(
                    Hypothesis(
                        text=f"{target_label} is directly connected to therapeutic strategy via {therapy_label}.",
                        confidence=score,
                        evidence=source_refs,
                        kind="therapy_strategy",
                    )
                )

        for biomarker_id in biomarker_ids:
            biomarker_label = self.world_model.nodes.get(biomarker_id, {}).get("label", biomarker_id)
            actionable = False
            therapies: list[tuple[str, float, list[str]]] = []
            for src, rel, dst, attrs in self.world_model.edges:
                if src != biomarker_id:
                    continue
                source_refs = [str(item) for item in attrs.get("source_refs", [])]
                score = float(attrs.get("score", 0.8))
                if rel == "actionable_in" and (disease_id is None or dst == disease_id):
                    actionable = True
                    hypotheses.append(
                        Hypothesis(
                            text=f"In {disease_label}, {biomarker_label} makes {target_label} look actionable rather than merely relevant.",
                            confidence=score,
                            evidence=source_refs,
                            kind="actionability",
                        )
                    )
                elif rel == "predicts_response_to":
                    therapies.append((dst, score, source_refs))
            if actionable:
                for therapy_id, score, source_refs in therapies:
                    therapy_label = self.world_model.nodes.get(therapy_id, {}).get("label", therapy_id)
                    hypotheses.append(
                        Hypothesis(
                            text=f"{biomarker_label} provides a plausible bridge from {target_label} biology to {therapy_label} in {disease_label}.",
                            confidence=score,
                            evidence=source_refs,
                            kind="therapy_bridge",
                        )
                    )
        return hypotheses

    def _collect_provenance(self, hypotheses: list[Hypothesis]) -> list[dict[str, Any]]:
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hypothesis in hypotheses:
            for source_ref in hypothesis.evidence:
                if source_ref in seen:
                    continue
                seen.add(source_ref)
                node = self.world_model.nodes.get(source_ref, {})
                ordered.append(
                    {
                        "source_id": source_ref,
                        "title": node.get("label", source_ref),
                        "source_type": node.get("source_type", "evidence"),
                        "citation": node.get("citation", ""),
                    }
                )
        return ordered
