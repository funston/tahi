from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bender.benchmarking import BenchmarkCaseResult, benchmark_report_to_dict, render_markdown_summary_table, summarize_system_results
from bender.models import Hypothesis
from bender.world_state import WorldModel


PROTON_MASS = 1.007276
SODIUM_MASS = 22.989218


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")


def _truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


@dataclass(frozen=True)
class MassSpecEvidenceSource:
    source_id: str
    title: str
    source_type: str
    summary: str
    citation: str = ""
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class MassSpecEntity:
    entity_id: str
    label: str
    entity_type: str
    summary: str
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MassSpecRelation:
    source_id: str
    relation: str
    target_id: str
    confidence: float = 1.0
    source_refs: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MassSpecKnowledgeBase:
    entities: tuple[MassSpecEntity, ...]
    relations: tuple[MassSpecRelation, ...]
    sources: tuple[MassSpecEvidenceSource, ...]


@dataclass(frozen=True)
class MassSpecSpectrumCase:
    case_id: str
    observed_mz: float
    polarity: str
    instrument_mode: str
    sample_type: str = ""
    question: str = ""
    expected_analyte_id: str = ""
    expected_adduct_id: str = ""

    def semantic_query(self) -> str:
        parts = [
            self.question or "explain mass spectrometry peak",
            f"mz {self.observed_mz:.4f}",
            self.polarity,
            self.instrument_mode,
            self.sample_type,
        ]
        return " ".join(part for part in parts if part).strip()

    @classmethod
    def from_record(cls, payload: dict[str, Any]) -> "MassSpecSpectrumCase":
        return cls(
            case_id=str(payload.get("case_id") or payload.get("id") or "spectrum_case"),
            observed_mz=float(payload.get("observed_mz")),
            polarity=str(payload.get("polarity") or ""),
            instrument_mode=str(payload.get("instrument_mode") or ""),
            sample_type=str(payload.get("sample_type") or ""),
            question=str(payload.get("question") or ""),
            expected_analyte_id=str(payload.get("expected_analyte_id") or ""),
            expected_adduct_id=str(payload.get("expected_adduct_id") or ""),
        )


@dataclass(frozen=True)
class MassSpecAnalyteProfileRequest:
    analyte: str
    polarity: str = ""
    instrument_mode: str = ""
    question: str = ""

    def semantic_query(self) -> str:
        parts = [
            self.question or "profile analyte in mass spectrometry",
            self.analyte,
            self.polarity,
            self.instrument_mode,
        ]
        return " ".join(part for part in parts if part).strip()


def build_mass_spec_world_model(knowledge_base: MassSpecKnowledgeBase) -> WorldModel:
    world = WorldModel(domain="mass_spec_interpretation")
    world.upsert_node(
        "mass_spec_domain",
        label="Mass Spectrometry Interpretation",
        type="domain",
        summary="World-model for analytes, adducts, instrument modes, sample context, and peak interpretation.",
        keywords=["mass spectrometry", "analyte", "adduct", "fragment", "instrument", "provenance"],
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
        world.add_edge("mass_spec_domain", "has_source", source.source_id, score=0.95)
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
        world.add_edge("mass_spec_domain", "contains_entity", entity.entity_id, score=0.97)
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


def build_demo_mass_spec_knowledge_base() -> MassSpecKnowledgeBase:
    sources = (
        MassSpecEvidenceSource(
            source_id="source:esi_adduct_reference",
            title="ESI Adduct Reference",
            source_type="reference",
            summary="Common LC-MS electrospray adducts include protonated and sodiated ions in positive mode and deprotonated ions in negative mode.",
            citation="Demo reference summary",
            keywords=("esi", "adduct", "positive mode", "negative mode"),
        ),
        MassSpecEvidenceSource(
            source_id="source:caffeine_note",
            title="Caffeine Standard Note",
            source_type="lab_note",
            summary="Caffeine commonly appears as a protonated species in positive-mode LC-MS around m/z 195.0877.",
            citation="Demo standard note",
            keywords=("caffeine", "positive mode", "standard"),
        ),
        MassSpecEvidenceSource(
            source_id="source:glucose_note",
            title="Glucose Sodium Adduct Note",
            source_type="lab_note",
            summary="Glucose often appears as a sodium adduct in positive-mode measurements around m/z 203.0526.",
            citation="Demo standard note",
            keywords=("glucose", "sodium adduct", "positive mode"),
        ),
    )
    entities = (
        MassSpecEntity(
            entity_id="instrument:lcms_positive",
            label="LC-MS positive mode",
            entity_type="instrument_mode",
            summary="Positive-mode LC-MS is commonly used for protonated and sodiated analytes.",
            aliases=("ESI positive", "positive mode"),
            keywords=("lcms", "positive", "esi"),
            metadata={"polarity": "positive"},
        ),
        MassSpecEntity(
            entity_id="instrument:lcms_negative",
            label="LC-MS negative mode",
            entity_type="instrument_mode",
            summary="Negative-mode LC-MS often favors deprotonated species.",
            aliases=("ESI negative", "negative mode"),
            keywords=("lcms", "negative", "esi"),
            metadata={"polarity": "negative"},
        ),
        MassSpecEntity(
            entity_id="adduct:m_plus_h",
            label="[M+H]+",
            entity_type="adduct",
            summary="Protonated molecular ion common in positive-mode electrospray.",
            aliases=("protonated", "M+H"),
            keywords=("adduct", "protonated", "positive"),
            metadata={"polarity": "positive", "mass_shift": PROTON_MASS, "charge": 1},
        ),
        MassSpecEntity(
            entity_id="adduct:m_plus_na",
            label="[M+Na]+",
            entity_type="adduct",
            summary="Sodiated molecular ion common in positive-mode electrospray, especially with sugars and salt-rich matrices.",
            aliases=("sodiated", "M+Na"),
            keywords=("adduct", "sodium", "positive"),
            metadata={"polarity": "positive", "mass_shift": SODIUM_MASS, "charge": 1},
        ),
        MassSpecEntity(
            entity_id="adduct:m_minus_h",
            label="[M-H]-",
            entity_type="adduct",
            summary="Deprotonated molecular ion common in negative-mode electrospray.",
            aliases=("deprotonated", "M-H"),
            keywords=("adduct", "deprotonated", "negative"),
            metadata={"polarity": "negative", "mass_shift": -PROTON_MASS, "charge": 1},
        ),
        MassSpecEntity(
            entity_id="analyte:caffeine",
            label="Caffeine",
            entity_type="analyte",
            summary="Small molecule stimulant frequently used as a reference analyte in LC-MS demos.",
            keywords=("caffeine", "alkaloid", "standard"),
            metadata={"neutral_mass": 194.0804},
        ),
        MassSpecEntity(
            entity_id="analyte:glucose",
            label="Glucose",
            entity_type="analyte",
            summary="Common sugar with frequent sodium-adduct behavior in positive-mode LC-MS.",
            keywords=("glucose", "sugar", "metabolite"),
            metadata={"neutral_mass": 180.0634},
        ),
        MassSpecEntity(
            entity_id="analyte:salicylic_acid",
            label="Salicylic acid",
            entity_type="analyte",
            summary="Acidic small molecule that often appears in negative mode as a deprotonated ion.",
            aliases=("2-hydroxybenzoic acid",),
            keywords=("salicylic acid", "negative mode", "acid"),
            metadata={"neutral_mass": 138.0317},
        ),
        MassSpecEntity(
            entity_id="sample:metabolomics_plasma",
            label="Plasma metabolomics sample",
            entity_type="sample_type",
            summary="Typical small-molecule metabolomics sample with salt matrix effects that can influence adduct prevalence.",
            keywords=("plasma", "metabolomics", "sample"),
        ),
    )
    relations = (
        MassSpecRelation(
            source_id="instrument:lcms_positive",
            relation="supports_adduct",
            target_id="adduct:m_plus_h",
            confidence=0.97,
            source_refs=("source:esi_adduct_reference",),
        ),
        MassSpecRelation(
            source_id="instrument:lcms_positive",
            relation="supports_adduct",
            target_id="adduct:m_plus_na",
            confidence=0.93,
            source_refs=("source:esi_adduct_reference",),
        ),
        MassSpecRelation(
            source_id="instrument:lcms_negative",
            relation="supports_adduct",
            target_id="adduct:m_minus_h",
            confidence=0.97,
            source_refs=("source:esi_adduct_reference",),
        ),
        MassSpecRelation(
            source_id="analyte:caffeine",
            relation="commonly_forms",
            target_id="adduct:m_plus_h",
            confidence=0.98,
            source_refs=("source:caffeine_note",),
        ),
        MassSpecRelation(
            source_id="analyte:glucose",
            relation="commonly_forms",
            target_id="adduct:m_plus_na",
            confidence=0.96,
            source_refs=("source:glucose_note",),
        ),
        MassSpecRelation(
            source_id="analyte:salicylic_acid",
            relation="commonly_forms",
            target_id="adduct:m_minus_h",
            confidence=0.95,
            source_refs=("source:esi_adduct_reference",),
        ),
        MassSpecRelation(
            source_id="sample:metabolomics_plasma",
            relation="can_bias_toward",
            target_id="adduct:m_plus_na",
            confidence=0.84,
            source_refs=("source:esi_adduct_reference",),
        ),
    )
    return MassSpecKnowledgeBase(entities=entities, relations=relations, sources=sources)


def load_mass_spec_knowledge_base(path: str | Path) -> MassSpecKnowledgeBase:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entities = tuple(
        MassSpecEntity(
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
        MassSpecRelation(
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
        MassSpecEvidenceSource(
            source_id=str(record["source_id"]),
            title=str(record["title"]),
            source_type=str(record.get("source_type", "evidence")),
            summary=str(record.get("summary", "")),
            citation=str(record.get("citation", "")),
            keywords=tuple(str(item) for item in record.get("keywords", [])),
        )
        for record in payload.get("sources", [])
    )
    return MassSpecKnowledgeBase(entities=entities, relations=relations, sources=sources)


class MassSpecCaseLoader:
    def load(self, path: str | Path) -> list[MassSpecSpectrumCase]:
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else payload.get("cases", [])
        return [MassSpecSpectrumCase.from_record(record) for record in records]


@dataclass(frozen=True)
class MassSpecWorkspace:
    repo_root: Path | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", Path(self.repo_root))

    def resolve_knowledge_base_path(self) -> Path:
        candidates = [
            self.repo_root / "demo_mass_spec_kb.json",
            self.repo_root / "data" / "demo_mass_spec_kb.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not resolve a mass spec knowledge base under {self.repo_root}")

    def resolve_cases_path(self) -> Path:
        candidates = [
            self.repo_root / "demo_cases.json",
            self.repo_root / "data" / "demo_cases.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not resolve mass spec demo cases under {self.repo_root}")

    def load_knowledge_base(self) -> MassSpecKnowledgeBase:
        return load_mass_spec_knowledge_base(self.resolve_knowledge_base_path())

    def load_cases(self) -> list[MassSpecSpectrumCase]:
        return MassSpecCaseLoader().load(self.resolve_cases_path())


class MassSpecInterpretationAdapter:
    def __init__(self, world_model: WorldModel) -> None:
        self.world_model = world_model

    def run_spectrum_case(self, case: MassSpecSpectrumCase, *, top_k: int = 8, tolerance_da: float = 0.01) -> dict[str, Any]:
        instrument_id = self._resolve_entity(case.instrument_mode, entity_type="instrument_mode")
        sample_id = self._resolve_entity(case.sample_type, entity_type="sample_type") if case.sample_type else None
        retrievals = self.world_model.retrieve(case.semantic_query(), top_k=top_k)
        candidates = self._rank_peak_candidates(
            observed_mz=case.observed_mz,
            polarity=case.polarity,
            instrument_id=instrument_id,
            sample_id=sample_id,
            tolerance_da=tolerance_da,
        )
        hypotheses = self._candidate_hypotheses(candidates)
        provenance = self._collect_provenance(hypotheses)
        return {
            "case_id": case.case_id,
            "observed_mz": case.observed_mz,
            "normalized_entities": {
                "instrument_mode": instrument_id,
                "sample_type": sample_id,
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
            "candidate_explanations": candidates,
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

    def run_retrieval_baseline(self, case: MassSpecSpectrumCase, *, top_k: int = 8) -> dict[str, Any]:
        retrievals = self.world_model.retrieve(case.semantic_query(), top_k=top_k)
        analyte = next((item for item in retrievals if item.node_type == "analyte"), None)
        adduct = next(
            (
                item
                for item in retrievals
                if item.node_type == "adduct"
                and str(item.attributes.get("polarity", "")).lower() == case.polarity.lower()
            ),
            None,
        )
        candidate = None
        if analyte is not None and adduct is not None:
            candidate = {
                "analyte_id": analyte.node_id,
                "analyte_label": analyte.label,
                "adduct_id": adduct.node_id,
                "adduct_label": adduct.label,
                "confidence": round((analyte.score + adduct.score) / 2.0, 4),
            }
        return {
            "case_id": case.case_id,
            "retrieved_entities": [
                {
                    "node_id": item.node_id,
                    "label": item.label,
                    "type": item.node_type,
                    "score": item.score,
                }
                for item in retrievals
            ],
            "candidate_explanation": candidate,
        }

    def run_analyte_profile(self, request: MassSpecAnalyteProfileRequest, *, top_k: int = 8) -> dict[str, Any]:
        analyte_id = self._resolve_entity(request.analyte, entity_type="analyte")
        retrievals = self.world_model.retrieve(request.semantic_query(), top_k=top_k)
        hypotheses = self._derive_analyte_profile(analyte_id=analyte_id, polarity=request.polarity)
        provenance = self._collect_provenance(hypotheses)
        return {
            "analyte": request.analyte,
            "normalized_entities": {"analyte": analyte_id},
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

    def _rank_peak_candidates(
        self,
        *,
        observed_mz: float,
        polarity: str,
        instrument_id: str | None,
        sample_id: str | None,
        tolerance_da: float,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        polarity_normalized = polarity.lower()
        instrument_supported_adducts = {
            dst
            for src, rel, dst, _attrs in self.world_model.edges
            if src == instrument_id and rel == "supports_adduct"
        }
        sample_bias = {
            dst
            for src, rel, dst, _attrs in self.world_model.edges
            if src == sample_id and rel == "can_bias_toward"
        }
        for analyte_id, analyte_node in self.world_model.nodes.items():
            if analyte_node.get("type") != "analyte":
                continue
            neutral_mass = analyte_node.get("neutral_mass")
            if neutral_mass is None:
                continue
            for adduct_id, adduct_node in self.world_model.nodes.items():
                if adduct_node.get("type") != "adduct":
                    continue
                if adduct_node.get("polarity", "").lower() != polarity_normalized:
                    continue
                theoretical_mz = float(neutral_mass) + float(adduct_node.get("mass_shift", 0.0))
                mass_error = abs(observed_mz - theoretical_mz)
                if mass_error > tolerance_da:
                    continue
                confidence = max(0.4, 1.0 - (mass_error / max(tolerance_da, 1e-6)))
                if adduct_id in instrument_supported_adducts:
                    confidence += 0.08
                if adduct_id in sample_bias:
                    confidence += 0.04
                if self._relation_exists(analyte_id, "commonly_forms", adduct_id):
                    confidence += 0.08
                confidence = min(confidence, 0.99)
                evidence = self._collect_relation_evidence(analyte_id, adduct_id)
                candidates.append(
                    {
                        "analyte_id": analyte_id,
                        "analyte_label": analyte_node.get("label", analyte_id),
                        "adduct_id": adduct_id,
                        "adduct_label": adduct_node.get("label", adduct_id),
                        "theoretical_mz": round(theoretical_mz, 4),
                        "mass_error_da": round(mass_error, 5),
                        "confidence": round(confidence, 4),
                        "evidence": evidence,
                    }
                )
        candidates.sort(key=lambda item: (-item["confidence"], item["mass_error_da"], item["analyte_label"]))
        return candidates[:5]

    def _derive_analyte_profile(self, *, analyte_id: str | None, polarity: str) -> list[Hypothesis]:
        if analyte_id is None:
            return []
        analyte_label = self.world_model.nodes[analyte_id]["label"]
        hypotheses: list[Hypothesis] = []
        polarity_normalized = polarity.lower().strip()
        for src, rel, dst, attrs in self.world_model.edges:
            if src != analyte_id:
                continue
            source_refs = [str(item) for item in attrs.get("source_refs", [])]
            score = float(attrs.get("score", 0.8))
            if rel == "commonly_forms":
                adduct_node = self.world_model.nodes.get(dst, {})
                adduct_polarity = str(adduct_node.get("polarity", "")).lower()
                if polarity_normalized and adduct_polarity and adduct_polarity != polarity_normalized:
                    continue
                hypotheses.append(
                    Hypothesis(
                        text=f"{analyte_label} commonly appears as {adduct_node.get('label', dst)} under compatible ionization conditions.",
                        confidence=score,
                        evidence=source_refs,
                        kind="adduct_preference",
                    )
                )
        neutral_mass = self.world_model.nodes[analyte_id].get("neutral_mass")
        if neutral_mass is not None:
            hypotheses.append(
                Hypothesis(
                    text=f"{analyte_label} has neutral mass {float(neutral_mass):.4f}, which enables deterministic m/z checks against candidate adducts.",
                    confidence=0.95,
                    evidence=[],
                    kind="mass_constraint",
                )
            )
        return hypotheses

    def _relation_exists(self, source_id: str, relation: str, target_id: str) -> bool:
        return any(src == source_id and rel == relation and dst == target_id for src, rel, dst, _attrs in self.world_model.edges)

    def _collect_relation_evidence(self, analyte_id: str, adduct_id: str) -> list[str]:
        evidence: list[str] = []
        for src, rel, dst, attrs in self.world_model.edges:
            if src == analyte_id and dst == adduct_id and rel == "commonly_forms":
                evidence.extend(str(item) for item in attrs.get("source_refs", []))
        return sorted(set(evidence))

    def _candidate_hypotheses(self, candidates: list[dict[str, Any]]) -> list[Hypothesis]:
        hypotheses: list[Hypothesis] = []
        for candidate in candidates[:3]:
            hypotheses.append(
                Hypothesis(
                    text=(
                        f"{candidate['analyte_label']} as {candidate['adduct_label']} is a strong explanation for the observed peak "
                        f"because theoretical m/z {candidate['theoretical_mz']:.4f} is within {candidate['mass_error_da']:.5f} Da."
                    ),
                    confidence=float(candidate["confidence"]),
                    evidence=list(candidate["evidence"]),
                    kind="peak_assignment",
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


def render_mass_spec_rag_baseline(case: MassSpecSpectrumCase) -> dict[str, Any]:
    return {
        "query": case.semantic_query(),
        "steps": [
            "retrieve top-k adduct and analyte passages from a vector database",
            "stuff retrieved text into a prompt",
            "ask the LLM to infer which analyte/adduct best explains the peak",
            "trust the model to apply polarity, adduct chemistry, and mass arithmetic correctly in-context",
        ],
    }


@dataclass
class MassSpecABBenchmarkRunner:
    adapter: MassSpecInterpretationAdapter

    def run(self, cases: list[MassSpecSpectrumCase]) -> dict[str, Any]:
        retrieval_results: list[BenchmarkCaseResult] = []
        bender_results: list[BenchmarkCaseResult] = []
        for case in cases:
            retrieval = self.adapter.run_retrieval_baseline(case)
            bender = self.adapter.run_spectrum_case(case)
            retrieval_candidate = retrieval.get("candidate_explanation") or {}
            bender_candidates = bender.get("candidate_explanations", [])
            bender_candidate = bender_candidates[0] if bender_candidates else {}
            retrieval_correct = (
                retrieval_candidate.get("analyte_id") == case.expected_analyte_id
                and retrieval_candidate.get("adduct_id") == case.expected_adduct_id
            )
            bender_correct = (
                bender_candidate.get("analyte_id") == case.expected_analyte_id
                and bender_candidate.get("adduct_id") == case.expected_adduct_id
            )
            retrieval_results.append(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    system="retrieval_only",
                    correct=retrieval_correct,
                    metrics={"top1_exact": 1.0 if retrieval_correct else 0.0},
                    detail=retrieval,
                )
            )
            bender_results.append(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    system="bender",
                    correct=bender_correct,
                    metrics={
                        "top1_exact": 1.0 if bender_correct else 0.0,
                        "top1_mass_error_da": bender_candidate.get("mass_error_da"),
                    },
                    detail=bender,
                )
            )
        summaries = [
            summarize_system_results("retrieval_only", retrieval_results, metric_names=["top1_exact"]),
            summarize_system_results("bender", bender_results, metric_names=["top1_exact", "top1_mass_error_da"]),
        ]
        payload = benchmark_report_to_dict(
            benchmark_name="mass_spec_ab_peak_assignment",
            summaries=summaries,
            results_by_system={
                "retrieval_only": retrieval_results,
                "bender": bender_results,
            },
        )
        payload["markdown_summary"] = render_markdown_summary_table(summaries)
        return payload
