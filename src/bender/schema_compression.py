from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from .database import SQLSchemaSnapshot, SQLTableProfile


VOLATILE_TOKEN_PATTERNS = (
    re.compile(r"r\d+$"),
    re.compile(r"v\d+$"),
    re.compile(r"\d{4}$"),
    re.compile(r"\d{2}$"),
    re.compile(r"\d{4}_\d{2}$"),
)

ASSEMBLY_TOKENS = {"hg19", "hg38", "grch37", "grch38"}
SOURCE_TOKENS = {"gdc", "pdc", "dcc", "mc3"}
DATASET_TOKENS = {"tcga", "mitelman", "prod"}


def _tokenize_identifier(value: str) -> list[str]:
    return [part for part in re.split(r"[_\W]+", value.lower()) if part]


def _normalize_token(token: str) -> str:
    if token in ASSEMBLY_TOKENS:
        return "<assembly>"
    if token in SOURCE_TOKENS:
        return "<source>"
    if token in DATASET_TOKENS:
        return ""
    for pattern in VOLATILE_TOKEN_PATTERNS:
        if pattern.fullmatch(token):
            return "<release>"
    return token


def _table_name_signature(table: SQLTableProfile) -> tuple[str, ...]:
    normalized: list[str] = []
    for token in _tokenize_identifier(f"{table.schema}_{table.name}"):
        token = _normalize_token(token)
        if token:
            normalized.append(token)
    return tuple(normalized)


def _column_name_signature(table: SQLTableProfile) -> tuple[str, ...]:
    return tuple(sorted(column.name.lower() for column in table.columns))


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


@dataclass(frozen=True)
class SchemaFamilyMember:
    schema: str
    table: str
    name_signature: tuple[str, ...]
    column_signature: tuple[str, ...]

    @property
    def full_name(self) -> str:
        return f"{self.schema}.{self.table}"


@dataclass
class SchemaFamily:
    family_id: str
    label: str
    prototype_tokens: tuple[str, ...]
    members: list[SchemaFamilyMember] = field(default_factory=list)
    common_columns: list[str] = field(default_factory=list)
    distinguishing_tokens: list[str] = field(default_factory=list)

    def summary(self) -> str:
        member_names = ", ".join(member.full_name for member in self.members[:6])
        common = ", ".join(self.common_columns[:10]) if self.common_columns else "n/a"
        distinguishing = ", ".join(self.distinguishing_tokens[:10]) if self.distinguishing_tokens else "n/a"
        return (
            f"Schema family {self.label} with {len(self.members)} related tables. "
            f"Representative members: {member_names}. "
            f"Common columns: {common}. "
            f"Distinguishing tokens: {distinguishing}."
        )


@dataclass
class SchemaCompressionPlan:
    families: list[SchemaFamily]
    table_to_family: dict[str, str]

    def family_map(self) -> dict[str, SchemaFamily]:
        return {family.family_id: family for family in self.families}


def _family_label(tokens: tuple[str, ...]) -> str:
    if not tokens:
        return "generic schema family"
    return " ".join(tokens)


def _family_id(tokens: tuple[str, ...]) -> str:
    label = "_".join(tokens) if tokens else "generic"
    return f"schema_family:{label}"


def build_schema_compression_plan(
    snapshot: SQLSchemaSnapshot,
    *,
    min_shared_columns: int = 3,
    min_column_jaccard: float = 0.75,
    min_name_jaccard: float = 0.5,
) -> SchemaCompressionPlan:
    members = [
        SchemaFamilyMember(
            schema=table.schema,
            table=table.name,
            name_signature=_table_name_signature(table),
            column_signature=_column_name_signature(table),
        )
        for table in snapshot.tables
    ]

    families: list[SchemaFamily] = []
    table_to_family: dict[str, str] = {}

    for member in members:
        matched_family: SchemaFamily | None = None
        for family in families:
            family_name_similarity = _jaccard(member.name_signature, family.prototype_tokens)
            family_column_similarity = _jaccard(
                member.column_signature,
                family.common_columns,
            )
            shared_columns = len(set(member.column_signature) & set(family.common_columns))
            if (
                family_name_similarity >= min_name_jaccard
                and family_column_similarity >= min_column_jaccard
                and shared_columns >= min_shared_columns
            ):
                matched_family = family
                break

        if matched_family is None:
            matched_family = SchemaFamily(
                family_id=_family_id(member.name_signature),
                label=_family_label(member.name_signature),
                prototype_tokens=member.name_signature,
                members=[],
                common_columns=list(member.column_signature),
                distinguishing_tokens=[],
            )
            families.append(matched_family)

        matched_family.members.append(member)
        matched_family.common_columns = sorted(
            set(matched_family.common_columns) & set(member.column_signature)
        ) or list(member.column_signature)
        table_to_family[member.full_name.lower()] = matched_family.family_id

    for family in families:
        prototype_token_set = set(family.prototype_tokens)
        distinguishing: set[str] = set()
        for member in family.members:
            distinguishing.update(token for token in member.name_signature if token not in prototype_token_set)
        family.distinguishing_tokens = sorted(distinguishing)

    families.sort(key=lambda family: (-len(family.members), family.label))
    return SchemaCompressionPlan(families=families, table_to_family=table_to_family)


def score_schema_families(query: str, plan: SchemaCompressionPlan) -> list[tuple[SchemaFamily, float]]:
    query_tokens = set(_tokenize_identifier(query))
    scored: list[tuple[SchemaFamily, float]] = []
    for family in plan.families:
        token_pool = set(family.prototype_tokens) | set(family.common_columns) | set(family.distinguishing_tokens)
        score = 0.0
        for token in query_tokens:
            if token in token_pool:
                score += 2.0
            if any(token in member.full_name.lower() for member in family.members[:10]):
                score += 1.0
        if score > 0.0:
            scored.append((family, score))
    scored.sort(key=lambda item: (-item[1], item[0].label))
    return scored
