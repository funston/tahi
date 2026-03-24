from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bender.database import SQLSchemaSnapshot
from bender.schema_compression import SchemaCompressionPlan, build_schema_compression_plan, score_schema_families


PROJECT_PATTERN = re.compile(r"\bTCGA-[A-Z0-9]+\b", re.IGNORECASE)
RELEASE_PATTERN = re.compile(r"\b(?:release|r)\s*(\d{1,2})\b", re.IGNORECASE)
CHROMOSOME_PATTERN = re.compile(r"\bchromosome\s+([0-9]{1,2}|x|y)\b", re.IGNORECASE)
CYTOBAND_PATTERN = re.compile(r"\b([0-9]{1,2}|x|y)([pq][0-9.]+)\b", re.IGNORECASE)


@dataclass
class TCGAQueryHints:
    project_short_name: str | None = None
    release: str | None = None
    chromosome: str | None = None
    cytoband: str | None = None
    modalities: list[str] | None = None


def parse_tcga_query_hints(query: str) -> TCGAQueryHints:
    project_match = PROJECT_PATTERN.search(query)
    release_match = RELEASE_PATTERN.search(query)
    chromosome_match = CHROMOSOME_PATTERN.search(query)
    cytoband_match = CYTOBAND_PATTERN.search(query.lower())
    lowered = query.lower()
    modalities: list[str] = []
    if "copy number segment allelic" in lowered or "segment allelic" in lowered:
        modalities.append("copy_number_segment_allelic")
    if "copy number segment masked" in lowered or "segment masked" in lowered:
        modalities.append("copy_number_segment_masked")
    if "copy number" in lowered and not modalities:
        modalities.append("copy_number")
    if ("weighted average copy number" in lowered or "maximum copy number" in lowered) and "cytoband" in lowered:
        modalities.append("copy_number_segment_allelic")
    if "cytoband" in lowered or "cytobands" in lowered:
        modalities.append("cytobands")
    if "mitelman" in lowered:
        modalities.append("mitelman")
    if "pearson correlation" in lowered or "morph" in lowered or "topo" in lowered:
        modalities.append("mitelman_correlation")
    return TCGAQueryHints(
        project_short_name=project_match.group(0).upper() if project_match else None,
        release=release_match.group(1) if release_match else None,
        chromosome=chromosome_match.group(1).upper() if chromosome_match else None,
        cytoband=cytoband_match.group(0).upper() if cytoband_match else None,
        modalities=modalities or None,
    )


def _score_member(member_name: str, hints: TCGAQueryHints) -> float:
    lowered = member_name.lower()
    score = 0.0
    if hints.release and f"r{hints.release}".lower() in lowered:
        score += 4.0
    if hints.chromosome and f"chr{hints.chromosome}".lower() in lowered:
        score += 3.0
    if hints.modalities:
        for modality in hints.modalities:
            if modality == "copy_number_segment_allelic" and "copy_number_segment_allelic" in lowered:
                score += 5.0
            elif modality == "copy_number_segment_masked" and "copy_number_segment_masked" in lowered:
                score += 5.0
            elif modality == "cytobands" and "cytobands" in lowered:
                score += 5.0
            elif modality == "mitelman" and lowered.startswith("prod."):
                score += 2.0
            elif modality == "copy_number" and "copy_number" in lowered:
                score += 2.5
    return score


def resolve_tcga_schema_plan(
    query: str,
    snapshot: SQLSchemaSnapshot,
    *,
    compression_plan: SchemaCompressionPlan | None = None,
    top_k_families: int = 6,
    top_k_tables: int = 8,
) -> dict[str, Any]:
    hints = parse_tcga_query_hints(query)
    plan = compression_plan or build_schema_compression_plan(snapshot)
    ranked_families = score_schema_families(query, plan)
    selected_families = [family for family, _ in ranked_families[:top_k_families]]

    member_scores: dict[str, float] = {}
    selected_family_labels: list[str] = []
    for family in selected_families:
        selected_family_labels.append(family.label)
        for member in family.members:
            name = member.full_name
            member_scores[name] = member_scores.get(name, 0.0) + _score_member(name, hints) + 1.0

    if hints.modalities:
        for table in snapshot.tables:
            full_name = f"{table.schema}.{table.name}"
            member_scores[full_name] = member_scores.get(full_name, 0.0) + _score_member(full_name, hints)

    if hints.modalities and "mitelman_correlation" in hints.modalities:
        for table_name in (
            "PROD.CYTOGENINVVALID",
            "PROD.REFERENCE",
            "PROD.CYTOGEN",
            "PROD.KODER",
            "PROD.CYTOCONVERTED",
            "PROD.CYTOBANDS_HG38",
            "TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23",
        ):
            member_scores[table_name] = member_scores.get(table_name, 0.0) + 8.0

    if hints.project_short_name and ("TCGA-LAML" in hints.project_short_name or "TCGA-KIRC" in hints.project_short_name):
        member_scores["TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23"] = (
            member_scores.get("TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23", 0.0) + 6.0
        )
        member_scores["PROD.CYTOBANDS_HG38"] = member_scores.get("PROD.CYTOBANDS_HG38", 0.0) + 4.0

    candidate_tables = [
        full_name
        for full_name, _ in sorted(member_scores.items(), key=lambda item: (-item[1], item[0]))
        if _ > 0.0
    ][:top_k_tables]

    preferred_join_path: list[str] = []
    if any("copy_number_segment_allelic" in table.lower() for table in candidate_tables) and any(
        "cytobands" in table.lower() for table in candidate_tables
    ):
        preferred_join_path.append("copy_number_segment_allelic->cytobands_hg38")
    if "mitelman_correlation" in (hints.modalities or []):
        preferred_join_path.extend(
            [
                "cytogeninvvalid->reference",
                "cytogen->koder",
                "copy_number_segment_allelic->cytobands_hg38",
            ]
        )

    return {
        "schema_families": selected_family_labels,
        "candidate_tables": candidate_tables,
        "candidate_join_path": preferred_join_path,
        "domain_hints": {
            "project_short_name": hints.project_short_name,
            "release": hints.release,
            "chromosome": hints.chromosome,
            "cytoband": hints.cytoband,
            "modalities": list(hints.modalities or []),
        },
    }


def apply_tcga_domain_plan(
    planning_result: dict[str, Any],
    *,
    query: str,
    snapshot: SQLSchemaSnapshot,
    compression_plan: SchemaCompressionPlan | None = None,
) -> dict[str, Any]:
    domain_plan = resolve_tcga_schema_plan(
        query,
        snapshot,
        compression_plan=compression_plan,
    )
    constraints = planning_result.setdefault("constraints", {})
    existing_tables = list(constraints.get("candidate_tables", []))
    merged_tables: list[str] = []
    for table in domain_plan["candidate_tables"] + existing_tables:
        normalized = table.split(".")[-1].lower()
        if normalized in {item.split(".")[-1].lower() for item in merged_tables}:
            continue
        merged_tables.append(table)
    constraints["candidate_tables"] = merged_tables[:8]
    if domain_plan["candidate_join_path"]:
        existing_join_path = list(constraints.get("candidate_join_path", []))
        constraints["candidate_join_path"] = list(
            dict.fromkeys(domain_plan["candidate_join_path"] + existing_join_path)
        )[:8]
    constraints["schema_families"] = list(domain_plan["schema_families"])
    constraints["domain_hints"] = dict(domain_plan["domain_hints"])
    planning_result.setdefault("bender_debug", {})["tcga_domain_plan"] = domain_plan
    return planning_result
