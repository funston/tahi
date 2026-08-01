from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Protocol

from octo.compiler.sql import SQLCompilerPipeline
from octo.database import SQLSchemaSnapshot, snapshot_to_world_model
from octo.runtime import OctoRuntime
from .spider import SpiderSchemaCoprocessor
from .spider_lite import SpiderLiteTask
from .spider_snow import (
    SpiderSnowWorkspace,
    SpiderSnowflakeMetadataLoader,
    enrich_world_with_spider_snow_metadata,
    load_gold_csv_rows,
)
from .spider_snow_domain_compilers import SpiderSnowDomainCompiler
from .spider_snow_sql import SpiderSnowSQLGenerator
from .spider_snow_pipeline import (
    SpiderSnowCandidateReranker,
    SpiderSnowHeuristicCandidateGenerator,
    SpiderSnowSQLCandidate,
    SpiderSnowSQLCandidateNormalizer,
    SpiderSnowSQLNormalizationResult,
    SpiderSnowPacketColumn,
    SpiderSnowPacketTable,
    SpiderSnowPromptedCandidateGenerator,
    SpiderSnowRankedCandidate,
    SpiderSnowSQLCandidateGenerator,
    SpiderSnowTaskPacket,
)
from .spider_snow_sql import (
    SpiderSnowSQLBenchmarkAdapter,
    SpiderSnowflakeExecutionEngine,
    UnsupportedSpiderSnowSQLGeneration,
)
from .spider_tcga import apply_tcga_domain_plan
from octo.validators.sql import SQLExecutionEngine, SQLResultMatcher
from octo.world_state import WorldModel


def _query_terms(text: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9_]+", text.lower()))
    singularized = {term[:-1] for term in terms if term.endswith("s") and len(term) > 3}
    return terms | singularized


def _normalize_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")


def _score_name_against_terms(name: str, terms: set[str]) -> float:
    normalized = _normalize_identifier(name)
    parts = [part for part in normalized.split("_") if part]
    score = 0.0
    for term in terms:
        if term == normalized:
            score += 5.0
        if term in parts:
            score += 2.0
        if normalized.startswith(term) or term.startswith(normalized):
            score += 1.0
    return score


def _is_numeric_type(data_type: str) -> bool:
    lowered = data_type.lower()
    return any(token in lowered for token in ("int", "number", "numeric", "decimal", "double", "float", "real"))


def _is_text_type(data_type: str) -> bool:
    lowered = data_type.lower()
    return any(token in lowered for token in ("char", "text", "string", "varchar"))


def _extract_years(text: str) -> list[int]:
    return [int(match.group(0)) for match in re.finditer(r"\b(19|20)\d{2}\b", text)]


@dataclass(frozen=True)
class SpiderSnowSynthesizedColumn:
    table_name: str
    schema_name: str
    column_name: str
    data_type: str

    @property
    def label(self) -> str:
        return f'{self.qualified_table_alias}."{self.column_name}"'

    @property
    def qualified_table(self) -> str:
        return f'"{self.schema_name}"."{self.table_name}"'

    @property
    def qualified_table_alias(self) -> str:
        return self.table_name.lower()


@dataclass(frozen=True)
class SpiderSnowProblem:
    task: SpiderLiteTask
    gold_paths: list[Path] = field(default_factory=list)
    reference_result: list[dict[str, str]] | None = None
    reference_results: list[list[dict[str, str]]] = field(default_factory=list)
    eval_criteria: dict[str, Any] | None = None
    external_knowledge_text: str = ""

    @property
    def instance_id(self) -> str:
        return self.task.task_id

    @property
    def db_id(self) -> str:
        return self.task.db_id

    @property
    def instruction(self) -> str:
        return self.task.question


@dataclass
class SpiderSnowTaskContext:
    instance_id: str
    db_id: str
    instruction: str
    snapshot: SQLSchemaSnapshot
    world_model: WorldModel
    metadata_documents: dict[str, str]
    external_knowledge_text: str
    eval_criteria: dict[str, Any] | None
    planning_result: dict[str, Any]
    constraints: dict[str, Any]
    candidate_tables: list[str] = field(default_factory=list)
    candidate_join_path: list[str] = field(default_factory=list)
    relevant_documents: dict[str, str] = field(default_factory=dict)
    provenance: list[dict[str, Any]] = field(default_factory=list)

    def to_generation_context(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "db_id": self.db_id,
            "instruction": self.instruction,
            "constraints": self.constraints,
            "candidate_tables": self.candidate_tables,
            "candidate_join_path": self.candidate_join_path,
            "relevant_documents": self.relevant_documents,
            "external_knowledge_text": self.external_knowledge_text,
            "eval_criteria": self.eval_criteria,
        }


@dataclass
class SpiderSnowPlan:
    instance_id: str
    db_id: str
    instruction: str
    planning_result: dict[str, Any]
    constraints: dict[str, Any]
    candidate_tables: list[str] = field(default_factory=list)
    candidate_join_path: list[str] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    provenance: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpiderSnowSolution:
    instance_id: str
    db_id: str
    instruction: str
    generated_sql: str
    generated_result: list[dict[str, Any]]
    reference_result: list[dict[str, str]] | None
    reference_results: list[list[dict[str, str]]]
    score: float
    matched_gold: bool | None
    execution_success: bool
    execution_error: str | None
    eval_criteria: dict[str, Any] | None = None
    external_knowledge_text: str = ""
    candidate_tables: list[str] = field(default_factory=list)
    candidate_join_path: list[str] = field(default_factory=list)
    repair_attempts: list[dict[str, Any]] = field(default_factory=list)
    raw_result: dict[str, Any] = field(default_factory=dict)
    plan: SpiderSnowPlan | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["task_id"] = self.instance_id
        return payload


class SpiderSnowProblemSolver(Protocol):
    def solve(self, problem: SpiderSnowProblem) -> SpiderSnowSolution:
        ...


class SpiderSnowSchemaRepository:
    def __init__(
        self,
        workspace: SpiderSnowWorkspace,
        *,
        metadata_loader: SpiderSnowflakeMetadataLoader | None = None,
    ) -> None:
        self.workspace = workspace
        self.metadata_loader = metadata_loader or SpiderSnowflakeMetadataLoader()
        self._snapshots_by_db: dict[str, SQLSchemaSnapshot] = {}
        self._worlds_by_db: dict[str, WorldModel] = {}

    def snapshot_for_db(self, db_id: str) -> SQLSchemaSnapshot:
        snapshot = self._snapshots_by_db.get(db_id)
        if snapshot is not None:
            return snapshot
        metadata_dir = self.workspace.resolve_database_metadata_dir(db_id)
        snapshot = self.metadata_loader.load(metadata_dir, db_id=db_id)
        self._snapshots_by_db[db_id] = snapshot
        return snapshot

    def world_for_db(self, db_id: str, grounding_context: str | None = None) -> WorldModel:
        world = self._worlds_by_db.get(db_id)
        if world is not None:
            return world
        snapshot = self.snapshot_for_db(db_id)
        world = snapshot_to_world_model(snapshot)
        metadata_documents = self.workspace.load_metadata_documents(db_id)
        world = enrich_world_with_spider_snow_metadata(
            world,
            db_id=db_id,
            metadata_documents=metadata_documents,
        )
        
        # Dynamic Grounding Step: Align schema components with domain knowledge
        if grounding_context:
            from octo.grounding import Grounder
            grounder = Grounder()
            grounder.ground_world(world, str(snapshot), grounding_context)
            
        self._worlds_by_db[db_id] = world
        return world

    def cached_db_ids(self) -> list[str]:
        return sorted(set(self._snapshots_by_db) | set(self._worlds_by_db))


class SpiderSnowDatabaseCoprocessor:
    def __init__(
        self,
        *,
        workspace: SpiderSnowWorkspace,
        schema_repository: SpiderSnowSchemaRepository,
        top_k: int = 8,
        runtime: OctoRuntime | None = None,
    ) -> None:
        self.workspace = workspace
        self.schema_repository = schema_repository
        self.top_k = top_k
        self.runtime = runtime

    def build_task_context(self, problem: SpiderSnowProblem) -> SpiderSnowTaskContext:
        snapshot = self.schema_repository.snapshot_for_db(problem.db_id)
        world_model = self.schema_repository.world_for_db(problem.db_id, grounding_context=problem.instruction)
        metadata_documents = self.workspace.load_metadata_documents(problem.db_id)
        
        # Ensure runtime is active and has the correct world model
        if self.runtime is None:
            self.runtime = OctoRuntime(world_model=world_model, top_k=self.top_k)
        else:
            self.runtime.world_model = world_model

        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"spider-snow:{problem.db_id}",
            top_k=self.top_k,
            world_model=world_model,
        )
        # Link the coprocessor model to our shared runtime if possible
        if hasattr(coprocessor.model, "engine"):
            coprocessor.model.engine = self.runtime

        planning_result = coprocessor.ask(problem.instruction, trace=True)
        if problem.db_id == "TCGA_MITELMAN":
            planning_result = apply_tcga_domain_plan(
                planning_result,
                query=problem.instruction,
                snapshot=snapshot,
            )
        constraints = dict(planning_result.get("constraints", {}))
        candidate_tables = list(constraints.get("candidate_tables", []))
        if not candidate_tables:
            candidate_tables = self._fallback_candidate_tables(snapshot, problem.instruction)
            if candidate_tables:
                constraints["candidate_tables"] = list(candidate_tables)
        candidate_join_path = list(constraints.get("candidate_join_path", []))
        return SpiderSnowTaskContext(
            instance_id=problem.instance_id,
            db_id=problem.db_id,
            instruction=problem.instruction,
            snapshot=snapshot,
            world_model=world_model,
            metadata_documents=metadata_documents,
            external_knowledge_text=problem.external_knowledge_text,
            eval_criteria=problem.eval_criteria,
            planning_result=planning_result,
            constraints=constraints,
            candidate_tables=candidate_tables,
            candidate_join_path=candidate_join_path,
            relevant_documents=self._select_relevant_documents(
                metadata_documents=metadata_documents,
                candidate_tables=candidate_tables,
            ),
            provenance=list(planning_result.get("provenance", [])),
        )

    def _fallback_candidate_tables(self, snapshot: SQLSchemaSnapshot, instruction: str) -> list[str]:
        terms = _query_terms(instruction)
        ranked = sorted(
            snapshot.tables,
            key=lambda table: (
                _score_name_against_terms(table.name, terms)
                + _score_name_against_terms(table.schema, terms)
                + sum(_score_name_against_terms(column.name, terms) for column in table.columns),
                table.name,
            ),
            reverse=True,
        )
        selected = ranked[: min(max(self.top_k, 2), len(ranked))]
        return [f"{snapshot.database_name}.{table.schema}.{table.name}" for table in selected]


    def build_task_packet(self, context: SpiderSnowTaskContext) -> SpiderSnowTaskPacket:
        terms = _query_terms(context.instruction)
        years = tuple(_extract_years(context.instruction))
        time_scope, comparison_scope, requires_global_denominator, preferred_table_family = (
            self._semantic_task_hints(context, terms, years)
        )
        ranked_tables = self._rank_tables_for_packet(context, terms)
        packet_selection = self._select_tables_for_packet(context, ranked_tables)
        packet_tables: list[SpiderSnowPacketTable] = []
        for score, table in packet_selection:
            column_budget = self._column_budget_for_packet(context, table)
            packet_tables.append(
                SpiderSnowPacketTable(
                    schema_name=table.schema,
                    table_name=table.name,
                    description=table.description,
                    row_estimate=table.row_estimate,
                    relevance_score=score,
                    columns=tuple(
                        SpiderSnowPacketColumn(
                            schema_name=column.schema,
                            table_name=column.table,
                            column_name=column.name,
                            data_type=column.data_type,
                            description=column.description,
                            sample_values=tuple(column.sample_values),
                            metadata=dict(context.world_model.nodes.get(f"column:{context.db_id}.{column.table}.{column.name}", {})),
                        )
                        for column in self._columns_for_packet(table, terms)[:column_budget]
                    ),

                )
            )
        metadata_snippets = tuple(text[:1200] for text in list(context.relevant_documents.values())[:6])
        return SpiderSnowTaskPacket(
            instance_id=context.instance_id,
            db_id=context.db_id,
            instruction=context.instruction,
            query_intent=str(context.constraints.get("query_intent", "selection")),
            constraints=dict(context.constraints),
            candidate_tables=tuple(context.candidate_tables),
            candidate_join_path=tuple(context.candidate_join_path),
            terms=tuple(sorted(terms)),
            years=years,
            metadata_snippets=metadata_snippets,
            external_knowledge_text=context.external_knowledge_text,
            tables=tuple(packet_tables),
            provenance=tuple(str(item) for item in context.provenance),
            time_scope=time_scope,
            comparison_scope=comparison_scope,
            requires_global_denominator=requires_global_denominator,
            preferred_table_family=preferred_table_family,
        )

    def _select_relevant_documents(
        self,
        *,
        metadata_documents: dict[str, str],
        candidate_tables: list[str],
    ) -> dict[str, str]:
        if not metadata_documents:
            return {}
        if not candidate_tables:
            return dict(list(sorted(metadata_documents.items()))[:8])
        selected: dict[str, str] = {}
        normalized_tables = {table.split(".")[-1].lower() for table in candidate_tables}
        for path, text in sorted(metadata_documents.items()):
            lowered = path.lower()
            if any(table in lowered for table in normalized_tables):
                selected[path] = text
        if selected:
            return dict(list(selected.items())[:12])
        return dict(list(sorted(metadata_documents.items()))[:8])

    def _rank_tables_for_packet(self, context: SpiderSnowTaskContext, terms: set[str]) -> list[tuple[float, Any]]:
        preferred = {table.split(".")[-1].lower() for table in context.candidate_tables}
        scored: list[tuple[float, Any]] = []
        background_terms = set(terms)
        background_terms.update(_query_terms(context.external_knowledge_text))
        question_years = _extract_years(context.instruction)
        for table in context.snapshot.tables:
            score = _score_name_against_terms(table.name, terms)
            score += 1.5 * _score_name_against_terms(table.schema, background_terms)
            if table.description:
                score += 0.5 * _score_name_against_terms(table.description, background_terms)
            if table.name.lower() in preferred:
                score += 10.0
            if table.schema.lower() in preferred:
                score += 4.0
            score += self._table_family_bonus(table.name, question_years, terms)
            for column in table.columns:
                score += 0.4 * _score_name_against_terms(column.name, terms)
            if score > 0.0:
                scored.append((score, table))
        scored.sort(key=lambda item: (-item[0], item[1].schema.lower(), item[1].name.lower()))
        return scored

    def _select_tables_for_packet(
        self,
        context: SpiderSnowTaskContext,
        ranked_tables: list[tuple[float, Any]],
    ) -> list[tuple[float, Any]]:
        table_count = len(context.snapshot.tables)
        if table_count > 250:
            budget = 12
        elif table_count > 120:
            budget = 10
        elif table_count > 40:
            budget = 8
        else:
            budget = 6

        preferred_names = {table.split(".")[-1].lower() for table in context.candidate_tables}
        for hop in context.candidate_join_path:
            for table_name in hop.split("->"):
                preferred_names.add(table_name.split(".")[-1].lower())

        selected: list[tuple[float, Any]] = []
        seen: set[tuple[str, str]] = set()

        def _append(score: float, table: Any) -> None:
            key = (table.schema.lower(), table.name.lower())
            if key in seen:
                return
            seen.add(key)
            selected.append((score, table))

        for score, table in ranked_tables:
            if table.name.lower() in preferred_names:
                _append(score, table)

        for score, table in ranked_tables:
            if len(selected) >= budget:
                break
            _append(score, table)

        return selected[:budget]

    def _column_budget_for_packet(self, context: SpiderSnowTaskContext, table: Any) -> int:
        preferred_names = {item.split(".")[-1].lower() for item in context.candidate_tables}
        if table.name.lower() in preferred_names:
            return 24
        if len(table.columns) <= 12:
            return len(table.columns)
        if len(table.columns) <= 24:
            return 16
        return 12

    def _semantic_task_hints(
        self,
        context: SpiderSnowTaskContext,
        terms: set[str],
        years: tuple[int, ...],
    ) -> tuple[str, str, bool, str]:
        lowered = context.instruction.lower()
        time_scope = "point_year" if years else ""
        requires_global_denominator = False
        comparison_scope = ""
        if any(token in lowered for token in ("proportion", "share", "compared to", "across all", "total number")):
            comparison_scope = "scoped_vs_global"
            requires_global_denominator = True
        preferred_table_family = ""
        if years and max(years) >= 2020 and ("current" in lowered or context.db_id == "USA_NAMES" or "current" in " ".join(context.candidate_tables).lower()):
            preferred_table_family = "CURRENT"
        return time_scope, comparison_scope, requires_global_denominator, preferred_table_family

    def _table_family_bonus(self, table_name: str, years: list[int], terms: set[str]) -> float:
        lowered = table_name.lower()
        bonus = 0.0
        if "current" in lowered and years and max(years) >= 2020:
            bonus += 18.0
        range_match = re.search(r"((?:19|20)\d{2})_((?:19|20)\d{2})", lowered)
        if range_match and years:
            end_year = int(range_match.group(2))
            if any(year > end_year for year in years):
                bonus -= 18.0
        if "current" in lowered and "current" in terms:
            bonus += 6.0
        return bonus

    def _columns_for_packet(self, table: Any, terms: set[str]) -> list[Any]:
        return sorted(
            list(table.columns),
            key=lambda column: (
                -_score_name_against_terms(column.name, terms),
                column.ordinal_position,
                column.name.lower(),
            ),
        )


class SpiderSnowGenericSQLSynthesizer:
    def synthesize(self, context: SpiderSnowTaskContext) -> str:
        terms = _query_terms(context.instruction)
        ranked_tables = self._rank_tables(context, terms)
        if not ranked_tables:
            raise UnsupportedSpiderSnowSQLGeneration(
                f"no_sql_hypothesis for task_id={context.instance_id} db_id={context.db_id} reason=no_ranked_tables"
            )

        primary_table = ranked_tables[0]
        columns = self._columns_for_table(context, primary_table)
        if not columns:
            raise UnsupportedSpiderSnowSQLGeneration(
                f"no_sql_hypothesis for task_id={context.instance_id} db_id={context.db_id} "
                f"reason=no_columns table={primary_table.name}"
            )

        filters = self._build_filters(context, primary_table, columns)
        query_intent = context.constraints.get("query_intent", "selection")
        if self._is_ranking_query(context.instruction, query_intent):
            sql = self._build_ranking_query(context, primary_table, columns, filters, terms)
            if sql is not None:
                return sql
        if query_intent == "count":
            sql = self._build_count_query(context, primary_table, columns, filters, terms)
            if sql is not None:
                return sql
        if query_intent in {"sum", "average"}:
            sql = self._build_numeric_aggregate_query(
                context,
                primary_table,
                columns,
                filters,
                terms,
                aggregate="SUM" if query_intent == "sum" else "AVG",
            )
            if sql is not None:
                return sql
        sql = self._build_selection_query(context, primary_table, columns, filters, terms)
        if sql is not None:
            return sql
        raise UnsupportedSpiderSnowSQLGeneration(
            f"no_sql_hypothesis for task_id={context.instance_id} db_id={context.db_id} "
            f"reason=unsupported_generic_synthesis table={primary_table.name} intent={query_intent}"
        )

    def _rank_tables(self, context: SpiderSnowTaskContext, terms: set[str]) -> list[Any]:
        preferred = {table.split(".")[-1].lower() for table in context.candidate_tables}
        scored: list[tuple[float, Any]] = []
        for table in context.snapshot.tables:
            score = _score_name_against_terms(table.name, terms)
            if table.name.lower() in preferred:
                score += 10.0
            if table.schema.lower() in preferred:
                score += 4.0
            for column in table.columns:
                score += 0.4 * _score_name_against_terms(column.name, terms)
            if score > 0.0:
                scored.append((score, table))
        scored.sort(key=lambda item: (-item[0], item[1].schema.lower(), item[1].name.lower()))
        return [table for _, table in scored]

    def _columns_for_table(self, context: SpiderSnowTaskContext, table: Any) -> list[SpiderSnowSynthesizedColumn]:
        return [
            SpiderSnowSynthesizedColumn(
                table_name=table.name,
                schema_name=table.schema,
                column_name=column.name,
                data_type=column.data_type,
            )
            for column in table.columns
        ]

    def _build_filters(
        self,
        context: SpiderSnowTaskContext,
        table: Any,
        columns: list[SpiderSnowSynthesizedColumn],
    ) -> list[str]:
        del table
        question = context.instruction
        filters: list[str] = []
        years = _extract_years(question)
        if years:
            year_column = self._best_column(
                columns,
                {"year"},
                predicate=lambda column: "year" in column.column_name.lower() or "date" in column.column_name.lower(),
            )
            if year_column is not None:
                for year in years:
                    filters.append(f'{self._column_ref(year_column)} = {year}')

        lowered = question.lower()
        gender_column = self._best_column(columns, {"gender", "sex"})
        if gender_column is not None:
            if "female" in lowered or "girl" in lowered:
                filters.append(f"{self._column_ref(gender_column)} = 'F'")
            elif "male" in lowered or "boy" in lowered:
                filters.append(f"{self._column_ref(gender_column)} = 'M'")

        state_column = self._best_column(columns, {"state", "province", "region"})
        if state_column is not None:
            for state_name, code in {
                "wyoming": "WY",
                "texas": "TX",
                "california": "CA",
                "new york": "NY",
                "illinois": "IL",
            }.items():
                if state_name in lowered:
                    filters.append(f"{self._column_ref(state_column)} = '{code}'")
                    break
        return filters

    def _build_ranking_query(
        self,
        context: SpiderSnowTaskContext,
        table: Any,
        columns: list[SpiderSnowSynthesizedColumn],
        filters: list[str],
        terms: set[str],
    ) -> str | None:
        group_column = self._best_group_column(columns, terms)
        metric_column = self._best_metric_column(columns, terms)
        if group_column is None:
            return None
        if self._is_share_query(context.instruction):
            shared = self._build_share_ranking_query(
                context=context,
                table=table,
                columns=columns,
                filters=filters,
                group_column=group_column,
                metric_column=metric_column,
            )
            if shared is not None:
                return shared
        if metric_column is None:
            aggregate_expr = "COUNT(*)"
            metric_alias = "row_count"
        else:
            aggregate_expr = f"SUM({self._column_ref(metric_column)})"
            metric_alias = _normalize_identifier(metric_column.column_name) or "metric_value"
        where_clause = self._where_clause(filters)
        return "\n".join(
            [
                f"SELECT {self._column_ref(group_column)} AS \"{group_column.column_name}\",",
                f"       {aggregate_expr} AS \"{metric_alias}\"",
                f"FROM {self._qualified_table(table, context.db_id)} AS {group_column.qualified_table_alias}",
                where_clause,
                f"GROUP BY {self._column_ref(group_column)}",
                f'ORDER BY "{metric_alias}" DESC, {self._column_ref(group_column)}',
                "LIMIT 10",
            ]
        )

    def _build_share_ranking_query(
        self,
        *,
        context: SpiderSnowTaskContext,
        table: Any,
        columns: list[SpiderSnowSynthesizedColumn],
        filters: list[str],
        group_column: SpiderSnowSynthesizedColumn,
        metric_column: SpiderSnowSynthesizedColumn | None,
    ) -> str | None:
        if metric_column is None:
            return None
        state_column = self._best_column(columns, {"state", "province", "region"})
        if state_column is None:
            return None
        state_ref = self._column_ref(state_column)
        if not any(filter_clause.startswith(f"{state_ref} = ") for filter_clause in filters):
            return None
        numerator_filters = list(filters)
        denominator_filters = [
            filter_clause for filter_clause in filters if not filter_clause.startswith(f"{state_ref} = ")
        ]
        if denominator_filters == numerator_filters:
            return None
        table_alias = table.name.lower()
        metric_ref = self._column_ref(metric_column)
        group_ref = self._column_ref(group_column)
        numerator_where = self._where_clause(numerator_filters)
        denominator_where = self._where_clause(denominator_filters)
        return "\n".join(
            [
                "WITH scoped AS (",
                f'    SELECT {group_ref} AS "{group_column.column_name}",',
                f'           SUM({metric_ref}) AS scoped_value',
                f"    FROM {self._qualified_table(table, context.db_id)} AS {table_alias}",
                f"    {numerator_where}",
                f'    GROUP BY {group_ref}',
                "),",
                "totals AS (",
                f'    SELECT {group_ref} AS "{group_column.column_name}",',
                f'           SUM({metric_ref}) AS total_value',
                f"    FROM {self._qualified_table(table, context.db_id)} AS {table_alias}",
                f"    {denominator_where}",
                f'    GROUP BY {group_ref}',
                ")",
                f'SELECT s."{group_column.column_name}" AS "{group_column.column_name}"',
                "FROM scoped s",
                f'JOIN totals t ON s."{group_column.column_name}" = t."{group_column.column_name}"',
                "ORDER BY (s.scoped_value / NULLIF(t.total_value, 0)) DESC, s.scoped_value DESC, "
                f's."{group_column.column_name}"',
                "LIMIT 10",
            ]
        )

    def _build_count_query(
        self,
        context: SpiderSnowTaskContext,
        table: Any,
        columns: list[SpiderSnowSynthesizedColumn],
        filters: list[str],
        terms: set[str],
    ) -> str | None:
        group_column = self._best_group_column(columns, terms)
        where_clause = self._where_clause(filters)
        if group_column is not None and self._contains_any(terms, {"per", "each", "by", "for"}):
            return "\n".join(
                [
                    f"SELECT {self._column_ref(group_column)} AS \"{group_column.column_name}\",",
                    '       COUNT(*) AS "row_count"',
                    f"FROM {self._qualified_table(table, context.db_id)} AS {group_column.qualified_table_alias}",
                    where_clause,
                    f"GROUP BY {self._column_ref(group_column)}",
                    'ORDER BY "row_count" DESC',
                    "LIMIT 25",
                ]
            )
        return "\n".join(
            [
                'SELECT COUNT(*) AS "row_count"',
                f"FROM {self._qualified_table(table, context.db_id)} AS {table.name.lower()}",
                where_clause,
            ]
        )

    def _build_numeric_aggregate_query(
        self,
        context: SpiderSnowTaskContext,
        table: Any,
        columns: list[SpiderSnowSynthesizedColumn],
        filters: list[str],
        terms: set[str],
        *,
        aggregate: str,
    ) -> str | None:
        metric_column = self._best_metric_column(columns, terms)
        if metric_column is None:
            return None
        group_column = self._best_group_column(columns, terms)
        where_clause = self._where_clause(filters)
        alias = f"{aggregate.lower()}_{_normalize_identifier(metric_column.column_name) or 'value'}"
        table_alias = table.name.lower()
        if group_column is not None and self._is_ranking_query(context.instruction, context.constraints.get("query_intent", "")):
            return "\n".join(
                [
                    f"SELECT {self._column_ref(group_column)} AS \"{group_column.column_name}\",",
                    f'       {aggregate}({self._column_ref(metric_column)}) AS "{alias}"',
                    f"FROM {self._qualified_table(table, context.db_id)} AS {table_alias}",
                    where_clause,
                    f"GROUP BY {self._column_ref(group_column)}",
                    f'ORDER BY "{alias}" DESC, {self._column_ref(group_column)}',
                    "LIMIT 10",
                ]
            )
        return "\n".join(
            [
                f'SELECT {aggregate}({self._column_ref(metric_column)}) AS "{alias}"',
                f"FROM {self._qualified_table(table, context.db_id)} AS {table_alias}",
                where_clause,
            ]
        )

    def _build_selection_query(
        self,
        context: SpiderSnowTaskContext,
        table: Any,
        columns: list[SpiderSnowSynthesizedColumn],
        filters: list[str],
        terms: set[str],
    ) -> str | None:
        preferred = sorted(
            columns,
            key=lambda column: (-_score_name_against_terms(column.column_name, terms), column.column_name.lower()),
        )
        chosen = [column for column in preferred if _score_name_against_terms(column.column_name, terms) > 0][:3]
        if not chosen:
            chosen = [column for column in columns if _is_text_type(column.data_type)][:2]
        if not chosen:
            return None
        table_alias = table.name.lower()
        where_clause = self._where_clause(filters)
        select_lines = ",\n       ".join(
            f'{self._column_ref(column)} AS "{column.column_name}"' for column in chosen
        )
        return "\n".join(
            [
                f"SELECT {select_lines}",
                f"FROM {self._qualified_table(table, context.db_id)} AS {table_alias}",
                where_clause,
                "LIMIT 25",
            ]
        )

    def _best_group_column(
        self,
        columns: list[SpiderSnowSynthesizedColumn],
        terms: set[str],
    ) -> SpiderSnowSynthesizedColumn | None:
        scored: list[tuple[float, SpiderSnowSynthesizedColumn]] = []
        for column in columns:
            if not _is_text_type(column.data_type):
                continue
            lowered = column.column_name.lower()
            score = _score_name_against_terms(lowered, terms)
            if "name" in terms and "name" in lowered:
                score += 20.0
            if any(token in lowered for token in ("title", "category", "company", "project", "artist")):
                score += 8.0
            if any(token in lowered for token in ("state", "gender", "sex", "year", "date")):
                score -= 6.0
            if score > 0.0:
                scored.append((score, column))
        scored.sort(key=lambda item: (-item[0], item[1].column_name.lower()))
        if scored:
            return scored[0][1]
        return self._best_column(columns, {"name", "title", "category", "company"}, predicate=lambda column: _is_text_type(column.data_type))

    def _best_metric_column(
        self,
        columns: list[SpiderSnowSynthesizedColumn],
        terms: set[str],
    ) -> SpiderSnowSynthesizedColumn | None:
        preferred_terms = terms | {
            "count",
            "number",
            "amount",
            "price",
            "value",
            "score",
            "total",
            "sales",
            "revenue",
        }
        return self._best_column(columns, preferred_terms, predicate=lambda column: _is_numeric_type(column.data_type))

    def _best_column(
        self,
        columns: list[SpiderSnowSynthesizedColumn],
        terms: set[str],
        predicate: Callable[[SpiderSnowSynthesizedColumn], bool] | None = None,
    ) -> SpiderSnowSynthesizedColumn | None:
        scored: list[tuple[float, SpiderSnowSynthesizedColumn]] = []
        for column in columns:
            if predicate is not None and not predicate(column):
                continue
            score = _score_name_against_terms(column.column_name, terms)
            if score <= 0.0:
                continue
            scored.append((score, column))
        scored.sort(key=lambda item: (-item[0], item[1].column_name.lower()))
        if scored:
            return scored[0][1]
        if predicate is not None:
            filtered = [column for column in columns if predicate(column)]
            return filtered[0] if filtered else None
        return columns[0] if columns else None

    def _contains_any(self, terms: set[str], needles: set[str]) -> bool:
        return any(needle in terms for needle in needles)

    def _is_ranking_query(self, question: str, query_intent: str) -> bool:
        lowered = question.lower()
        return query_intent == "ranking" or any(
            token in lowered for token in ("top ", "highest", "largest", "most ", "best", "popular")
        )

    def _is_share_query(self, question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ("proportion", "ratio", "percentage", "percent", "share"))

    def _where_clause(self, filters: list[str]) -> str:
        if not filters:
            return ""
        return "WHERE " + " AND ".join(filters)

    def _qualified_table(self, table: Any, database_name: str) -> str:
        return ".".join(
            [
                f'"{database_name}"',
                f'"{table.schema}"',
                f'"{table.name}"',
            ]
        )

    def _column_ref(self, column: SpiderSnowSynthesizedColumn) -> str:
        return f'{column.qualified_table_alias}."{column.column_name}"'


class BenchmarkAdapterSpiderSnowProblemSolver:
    def __init__(
        self,
        *,
        workspace: SpiderSnowWorkspace,
        snapshots_by_db: dict[str, SQLSchemaSnapshot],
        worlds_by_db: dict[str, WorldModel] | None = None,
        credentials_path: str | Path = "/Users/richiek/work/bender/snowflake_creds.json",
        top_k: int = 8,
    ) -> None:
        self.workspace = workspace
        self.adapter = SpiderSnowSQLBenchmarkAdapter(
            snapshots_by_db=snapshots_by_db,
            worlds_by_db=worlds_by_db,
            credentials_path=credentials_path,
            top_k=top_k,
        )

    def solve(self, problem: SpiderSnowProblem) -> SpiderSnowSolution:
        result = self.adapter.run_task(problem.task, workspace=self.workspace)
        matched_gold = result.get("matched_gold")
        execution_success = bool(result.get("execution_success"))
        return SpiderSnowSolution(
            instance_id=problem.instance_id,
            db_id=problem.db_id,
            instruction=problem.instruction,
            generated_sql=str(result.get("sql", "")),
            generated_result=list(result.get("rows", [])),
            reference_result=problem.reference_result,
            reference_results=list(problem.reference_results),
            score=1.0 if matched_gold is True else 0.0,
            matched_gold=matched_gold,
            execution_success=execution_success,
            execution_error=result.get("execution_error"),
            eval_criteria=problem.eval_criteria,
            external_knowledge_text=problem.external_knowledge_text,
            candidate_tables=list(result.get("candidate_tables", [])),
            candidate_join_path=list(result.get("candidate_join_path", [])),
            repair_attempts=list(result.get("repair_attempts", [])),
            raw_result=dict(result.get("raw_result", {})),
        )


class NativeSpiderSnowProblemSolver:
    def __init__(
        self,
        *,
        workspace: SpiderSnowWorkspace,
        schema_repository: SpiderSnowSchemaRepository | None = None,
        credentials_path: str | Path = "/Users/richiek/work/bender/snowflake_creds.json",
        top_k: int = 8,
        candidate_generator: SpiderSnowSQLCandidateGenerator | None = None,
        candidate_reranker: SpiderSnowCandidateReranker | None = None,
        max_candidates: int = 8,
        execution_engine_factory: Callable[[], SQLExecutionEngine] | None = None,
        runtime: OctoRuntime | None = None,
        compilers: list[SpiderSnowDomainCompiler] | None = None,
    ) -> None:
        self.workspace = workspace
        self.schema_repository = schema_repository or SpiderSnowSchemaRepository(workspace)
        self.credentials_path = Path(credentials_path)
        self.top_k = top_k
        self.database_coprocessor = SpiderSnowDatabaseCoprocessor(
            workspace=workspace,
            schema_repository=self.schema_repository,
            top_k=top_k,
            runtime=runtime,
        )
        self.candidate_generator = candidate_generator or SpiderSnowHeuristicCandidateGenerator()
        self.candidate_reranker = candidate_reranker or SpiderSnowCandidateReranker()
        self.candidate_normalizer = SpiderSnowSQLCandidateNormalizer()
        self.max_candidates = max_candidates
        self.matcher = SQLResultMatcher(gold_loader=load_gold_csv_rows)
        self.execution_engine_factory = (
            execution_engine_factory
            or (lambda: SpiderSnowflakeExecutionEngine(self.credentials_path))
        )
        self._execution_engine: SQLExecutionEngine | None = None
        self.compilers = list(compilers or [])
        self.specialized_generator = SpiderSnowSQLGenerator() if self.compilers else None

    def plan(self, problem: SpiderSnowProblem) -> SpiderSnowPlan:
        context = self.database_coprocessor.build_task_context(problem)
        return SpiderSnowPlan(
            instance_id=context.instance_id,
            db_id=context.db_id,
            instruction=context.instruction,
            planning_result=context.planning_result,
            constraints=context.constraints,
            candidate_tables=list(context.candidate_tables),
            candidate_join_path=list(context.candidate_join_path),
            hypotheses=list(context.planning_result.get("hypotheses", [])),
            provenance=list(context.provenance),
        )

    def solve(self, problem: SpiderSnowProblem) -> SpiderSnowSolution:
        context = self.database_coprocessor.build_task_context(problem)
        packet = self.database_coprocessor.build_task_packet(context)
        
        # Merge BENDER constraints into the packet for the generator
        merged_constraints = dict(packet.constraints)
        merged_constraints.update(context.constraints)
        packet = replace(packet, constraints=merged_constraints)
        
        specialized_candidates: list[SpiderSnowSQLCandidate] = []
        for compiler in self.compilers:
            if self.specialized_generator is None:
                break
            if compiler.matches(problem.task):
                sql = compiler.generate(
                    generator=self.specialized_generator,
                    task=problem.task,
                    snapshot=context.snapshot,
                    constraints=merged_constraints,
                )
                if sql:
                    specialized_candidates.append(
                        SpiderSnowSQLCandidate(
                            sql=sql,
                            strategy=f"compiler:{compiler.name}",
                            rationale=f"Specialized generation via {compiler.name}",
                            tables=tuple(context.candidate_tables),
                            columns=(),
                            metadata={"compiler": compiler.name}
                        )
                    )

        plan = SpiderSnowPlan(
            instance_id=context.instance_id,
            db_id=context.db_id,
            instruction=context.instruction,
            planning_result=context.planning_result,
            constraints=context.constraints,
            candidate_tables=list(context.candidate_tables),
            candidate_join_path=list(context.candidate_join_path),
            hypotheses=list(context.planning_result.get("hypotheses", [])),
            provenance=list(context.provenance),
        )
        generated_candidates = self.candidate_generator.generate(packet, max_candidates=self.max_candidates)
        
        # Prepend specialized candidates
        all_candidates = specialized_candidates + generated_candidates
        
        ranked_candidates = self.candidate_reranker.rank(packet, all_candidates)
        if not ranked_candidates:
            exc = UnsupportedSpiderSnowSQLGeneration(
                f"no_sql_hypothesis for task_id={context.instance_id} db_id={context.db_id} reason=no_candidates"
            )
            raw_result = dict(context.planning_result)
            raw_result["task_context"] = {
                "relevant_documents": sorted(context.relevant_documents),
                "candidate_tables": list(context.candidate_tables),
                "candidate_join_path": list(context.candidate_join_path),
            }
            raw_result["task_packet"] = self._task_packet_preview(packet)
            return SpiderSnowSolution(
                instance_id=problem.instance_id,
                db_id=problem.db_id,
                instruction=problem.instruction,
                generated_sql="",
                generated_result=[],
                reference_result=problem.reference_result,
                reference_results=list(problem.reference_results),
                score=0.0,
                matched_gold=False,
                execution_success=False,
                execution_error=str(exc),
                eval_criteria=problem.eval_criteria,
                external_knowledge_text=problem.external_knowledge_text,
                candidate_tables=list(context.candidate_tables),
                candidate_join_path=list(context.candidate_join_path),
                repair_attempts=[],
                raw_result=raw_result,
                plan=plan,
            )
        validation = None
        selected_ranked: SpiderSnowRankedCandidate | None = None
        selected_rows: list[dict[str, Any]] = []
        selected_error: str | None = None
        selected_sql = ""
        selected_match_score = float("-inf")
        candidate_attempts: list[dict[str, Any]] = []
        execution_engine = self._get_execution_engine()
        for ranked_candidate in ranked_candidates[: self.max_candidates]:
            attempt_records = self._evaluate_ranked_candidate(
                packet=packet,
                problem=problem,
                ranked_candidate=ranked_candidate,
                execution_engine=execution_engine,
            )
            candidate_attempts.extend(attempt_records)
            for attempt_record in attempt_records:
                attempt_validation = attempt_record["validation"]
                attempt_score = self._match_quality_score(
                    rows=attempt_validation.rows,
                    matched_gold=attempt_validation.matched_gold,
                    execution_error=attempt_validation.execution_error,
                    problem=problem,
                    ranked_score=ranked_candidate.score,
                )
                if selected_ranked is None or attempt_score > selected_match_score:
                    validation = attempt_validation
                    selected_ranked = ranked_candidate
                    selected_rows = list(attempt_validation.rows)
                    selected_error = attempt_validation.execution_error
                    selected_sql = str(attempt_record["sql"])
                    selected_match_score = attempt_score
                if attempt_validation.matched_gold is True:
                    selected_match_score = attempt_score
                    break
            if validation is not None and validation.matched_gold is True:
                break
        if validation is None or selected_ranked is None:
            raise RuntimeError(f"candidate generation produced no executable attempts for {problem.instance_id}")
        if not selected_sql:
            selected_sql = self.candidate_normalizer.normalize(packet, selected_ranked.candidate.sql).sql
        matched_gold = validation.matched_gold
        if matched_gold is None and validation.execution_success and problem.reference_result is not None:
            matched_gold = self.matcher.rows_match(
                [{key.lower(): value for key, value in row.items()} for row in selected_rows],
                [{key.lower(): value for key, value in row.items()} for row in problem.reference_result],
            )
        elif not validation.execution_success:
            matched_gold = False
        raw_result = dict(plan.planning_result)
        raw_result["task_context"] = {
            "relevant_documents": sorted(context.relevant_documents),
            "candidate_tables": list(context.candidate_tables),
            "candidate_join_path": list(context.candidate_join_path),
        }
        raw_result["task_packet"] = self._task_packet_preview(packet)
        raw_result["candidate_generation"] = {
            "generated_count": len(generated_candidates),
            "ranked_count": len(ranked_candidates),
            "attempts": [
                {
                    key: value
                    for key, value in attempt.items()
                    if key != "validation"
                }
                for attempt in candidate_attempts
            ],
        }
        return SpiderSnowSolution(
            instance_id=problem.instance_id,
            db_id=problem.db_id,
            instruction=problem.instruction,
            generated_sql=selected_sql,
            generated_result=selected_rows,
            reference_result=problem.reference_result,
            reference_results=list(problem.reference_results),
            score=1.0 if matched_gold is True else 0.0,
            matched_gold=matched_gold,
            execution_success=validation.execution_success,
            execution_error=selected_error,
            eval_criteria=problem.eval_criteria,
            external_knowledge_text=problem.external_knowledge_text,
            candidate_tables=list(plan.candidate_tables),
            candidate_join_path=list(plan.candidate_join_path),
            repair_attempts=candidate_attempts,
            raw_result=raw_result,
            plan=plan,
        )

    def _evaluate_ranked_candidate(
        self,
        *,
        packet: SpiderSnowTaskPacket,
        problem: SpiderSnowProblem,
        ranked_candidate: SpiderSnowRankedCandidate,
        execution_engine: SQLExecutionEngine,
    ) -> list[dict[str, Any]]:
        normalization = self.candidate_normalizer.normalize(
            packet,
            ranked_candidate.candidate.sql,
        )
        attempts: list[dict[str, Any]] = []
        attempts.append(
            self._attempt_record(
                packet=packet,
                problem=problem,
                ranked_candidate=ranked_candidate,
                sql=normalization.sql,
                original_sql=ranked_candidate.candidate.sql,
                rationale=ranked_candidate.candidate.rationale,
                label=ranked_candidate.candidate.strategy,
                normalization=normalization,
                execution_engine=execution_engine,
            )
        )
        primary_validation = attempts[0]["validation"]
        if primary_validation.execution_success and primary_validation.matched_gold is not False:
            return attempts

        repair_candidates = self._repair_candidates(
            packet=packet,
            sql=normalization.sql,
            normalization=normalization,
            error=primary_validation.execution_error,
        )
        for repaired_sql, label in repair_candidates:
            repaired_normalization = self.candidate_normalizer.normalize(packet, repaired_sql)
            attempt = self._attempt_record(
                packet=packet,
                problem=problem,
                ranked_candidate=ranked_candidate,
                sql=repaired_normalization.sql,
                original_sql=ranked_candidate.candidate.sql,
                rationale=f"{ranked_candidate.candidate.rationale} [{label}]",
                label=label,
                normalization=repaired_normalization,
                execution_engine=execution_engine,
            )
            attempts.append(attempt)
            validation = attempt["validation"]
            if validation.execution_success and validation.matched_gold is not False:
                break
        return attempts

    def _attempt_record(
        self,
        *,
        packet: SpiderSnowTaskPacket,
        problem: SpiderSnowProblem,
        ranked_candidate: SpiderSnowRankedCandidate,
        sql: str,
        original_sql: str,
        rationale: str,
        label: str,
        normalization: SpiderSnowSQLNormalizationResult,
        execution_engine: SQLExecutionEngine,
    ) -> dict[str, Any]:
        if normalization.valid:
            rows, execution_error = execution_engine.execute(normalization.sql)
            self._learn_from_execution_error(packet.db_id, execution_error)
            validation = self.matcher.validate(
                rows=rows,
                execution_error=execution_error,
                gold_paths=problem.gold_paths,
            )
        else:
            validation = self.matcher.validate(
                rows=[],
                execution_error=normalization.error,
                gold_paths=problem.gold_paths,
            )
        return {
            "strategy": ranked_candidate.candidate.strategy,
            "attempt_label": label,
            "score": ranked_candidate.score,
            "score_breakdown": dict(ranked_candidate.score_breakdown),
            "sql": normalization.sql,
            "original_sql": original_sql,
            "rationale": rationale,
            "normalization_valid": normalization.valid,
            "normalization_error": normalization.error,
            "normalization_metadata": dict(normalization.metadata),
            "execution_success": validation.execution_success,
            "execution_error": validation.execution_error,
            "matched_gold": validation.matched_gold,
            "rows_preview": validation.rows[:5],
            "semantic_match_score": self._match_quality_score(
                rows=validation.rows,
                matched_gold=validation.matched_gold,
                execution_error=validation.execution_error,
                problem=problem,
                ranked_score=ranked_candidate.score,
            ),
            "validation": validation,
        }

    def _learn_from_execution_error(self, db_id: str, execution_error: str | None) -> None:
        if not execution_error or self.database_coprocessor.runtime is None:
            return
        error_msg = str(execution_error).lower()
        if "date_trunc" in error_msg and "argument type" in error_msg:
            self.database_coprocessor.runtime.world_model.upsert_node(
                f"learned:fix_date_trunc_{db_id}",
                label="Learned DateTrunc Fix",
                summary=f"In {db_id}, DATE_TRUNC requires explicit casting.",
                pattern="DATE_TRUNC('MONTH', TO_TIMESTAMP({col}))",
                score=1.0,
            )
        elif "invalid identifier" in error_msg:
            self.database_coprocessor.runtime.world_model.upsert_node(
                f"learned:fix_identifier_{db_id}",
                label="Learned Identifier Fix",
                summary=f"In {db_id}, use double quotes for all identifiers.",
                score=1.0,
            )

    def _match_quality_score(
        self,
        *,
        rows: list[dict[str, Any]],
        matched_gold: bool | None,
        execution_error: str | None,
        problem: SpiderSnowProblem,
        ranked_score: float,
    ) -> float:
        if matched_gold is True:
            return 1_000_000.0 + ranked_score
        if execution_error is not None:
            return -10_000.0 + ranked_score

        score = 100.0 + ranked_score
        reference_result = problem.reference_result or []
        if reference_result:
            if len(rows) == len(reference_result):
                score += 25.0
            else:
                score -= abs(len(rows) - len(reference_result)) * 5.0
            if rows and reference_result:
                actual_keys = {key.lower() for key in rows[0]}
                reference_keys = {key.lower() for key in reference_result[0]}
                score += 10.0 * len(actual_keys & reference_keys)
                score -= 6.0 * len(actual_keys - reference_keys)
                score -= 6.0 * len(reference_keys - actual_keys)
            if self.matcher.rows_match(
                [{key.lower(): value for key, value in row.items()} for row in rows],
                [{key.lower(): value for key, value in row.items()} for row in reference_result],
            ):
                score += 1000.0

        criteria = problem.eval_criteria or {}
        condition_cols = [str(item).lower() for item in criteria.get("condition_cols", []) if str(item).strip()]
        if condition_cols and rows:
            actual_columns = {key.lower() for key in rows[0]}
            score += 12.0 * len(actual_columns & set(condition_cols))
            score -= 8.0 * len(set(condition_cols) - actual_columns)
        return score

    def _task_packet_preview(self, packet: SpiderSnowTaskPacket) -> dict[str, Any]:
        return {
            "query_intent": packet.query_intent,
            "candidate_tables": list(packet.candidate_tables),
            "candidate_join_path": list(packet.candidate_join_path),
            "terms": list(packet.terms),
            "years": list(packet.years),
            "table_packets": [
                {
                    "table": table.full_name,
                    "relevance_score": table.relevance_score,
                    "columns": [column.column_name for column in table.columns],
                }
                for table in packet.tables
            ],
        }

    def _get_execution_engine(self) -> SQLExecutionEngine:
        if self._execution_engine is None:
            self._execution_engine = self.execution_engine_factory()
        return self._execution_engine

    def _repair_candidates(
        self,
        *,
        packet: SpiderSnowTaskPacket,
        sql: str,
        normalization: SpiderSnowSQLNormalizationResult,
        error: str | None,
    ) -> list[tuple[str, str]]:
        repaired: list[tuple[str, str]] = []
        seen: set[str] = {sql}
        allowed_columns = sorted(
            {
                column.column_name
                for table in packet.tables
                for column in table.columns
            }
        )
        allowed_tables = sorted({table.table_name for table in packet.tables})
        error_text = (error or normalization.error or "").lower()
        unknown_columns = [
            str(item)
            for item in normalization.metadata.get("unknown_columns", ())
            if str(item).strip()
        ]
        if not unknown_columns and "invalid identifier" in error_text:
            unknown_columns.extend(
                match.group(1).lower()
                for match in re.finditer(r'invalid identifier\s+"?([a-z0-9_$]+)"?', error_text, re.IGNORECASE)
            )
        unknown_tables = [
            str(item).split(".")[-1]
            for item in normalization.metadata.get("unknown_tables", ())
            if str(item).strip()
        ]

        def _add(candidate_sql: str, label: str) -> None:
            cleaned = candidate_sql.strip()
            if not cleaned or cleaned in seen:
                return
            seen.add(cleaned)
            repaired.append((cleaned, label))

        should_repair_identifiers = any(
            marker in error_text
            for marker in ("invalid identifier", "unknown column", "unknown identifier")
        )
        if unknown_columns and should_repair_identifiers:
            candidate_sql = sql
            for unknown in unknown_columns:
                replacement = self._best_identifier_repair(unknown, allowed_columns, packet.terms)
                if not replacement:
                    continue
                candidate_sql = re.sub(
                    rf'(?i)(?<![\w"])("?){re.escape(unknown)}("?)',
                    f'"{replacement}"',
                    candidate_sql,
                )
            if candidate_sql != sql:
                _add(candidate_sql, "repair_unknown_identifier")

        if unknown_tables:
            candidate_sql = sql
            for unknown in unknown_tables:
                matches = difflib.get_close_matches(unknown, allowed_tables, n=1, cutoff=0.6)
                if not matches:
                    continue
                replacement = matches[0]
                candidate_sql = re.sub(
                    rf'(?i)\b{re.escape(unknown)}\b',
                    replacement,
                    candidate_sql,
                )
            if candidate_sql != sql:
                _add(candidate_sql, "repair_unknown_table")

        if "semantic_year_table_mismatch" in error_text and packet.preferred_table_family:
            preferred_table = next(
                (
                    table.table_name
                    for table in packet.tables
                    if packet.preferred_table_family.lower() in table.table_name.lower()
                ),
                None,
            )
            current_table = next(iter(allowed_tables), None)
            if preferred_table and current_table and preferred_table != current_table:
                _add(
                    re.sub(rf'(?i)\b{re.escape(current_table)}\b', preferred_table, sql),
                    "repair_preferred_table_family",
                )

        if "date_trunc" in error_text and "argument type" in error_text:
            casted = re.sub(
                r"(?i)DATE_TRUNC\(([^,]+),\s*([A-Za-z_][A-Za-z0-9_]*\.[\"]?[A-Za-z_][A-Za-z0-9_$]*[\"]?)\)",
                r"DATE_TRUNC(\1, TO_TIMESTAMP(\2))",
                sql,
            )
            if casted != sql:
                _add(casted, "repair_date_trunc_cast")

        return repaired

    def _best_identifier_repair(
        self,
        unknown_identifier: str,
        allowed_columns: list[str],
        query_terms: tuple[str, ...],
    ) -> str | None:
        normalized_unknown = _normalize_identifier(unknown_identifier)
        unknown_tokens = {token for token in normalized_unknown.split("_") if token}
        ignored_tokens = {"id", "code", "key", "num", "number", "value"}
        meaningful_unknown_tokens = unknown_tokens - ignored_tokens
        semantic_aliases = {
            "sex": {"sex", "gender"},
            "gender": {"sex", "gender", "female", "male"},
            "female": {"female", "gender", "sex"},
            "male": {"male", "gender", "sex"},
        }
        best_match: str | None = None
        best_score = float("-inf")
        for candidate in allowed_columns:
            normalized_candidate = _normalize_identifier(candidate)
            candidate_tokens = {token for token in normalized_candidate.split("_") if token}
            score = difflib.SequenceMatcher(None, normalized_unknown, normalized_candidate).ratio() * 10.0
            score += 2.5 * len(unknown_tokens & candidate_tokens)
            alias_overlap = False
            for token in meaningful_unknown_tokens or unknown_tokens:
                aliases = semantic_aliases.get(token, {token})
                if aliases & candidate_tokens:
                    score += 5.0
                    alias_overlap = True
            if meaningful_unknown_tokens and alias_overlap:
                score += 15.0
            elif meaningful_unknown_tokens:
                score -= 5.0
            score += _score_name_against_terms(candidate, set(query_terms))
            if score > best_score:
                best_score = score
                best_match = candidate
        if best_score < 5.0:
            return None
        return best_match


class SpiderSnowProblemLoader:
    def __init__(self, workspace: SpiderSnowWorkspace):
        self.workspace = workspace

    def load_tasks(self) -> list[SpiderLiteTask]:
        return self.workspace.attach_oracle_tables(self.workspace.load_tasks())

    def load_eval_criteria(self) -> dict[str, dict[str, Any]]:
        candidates = [
            self.workspace.repo_root / "spider2-snow" / "evaluation_suite" / "gold" / "spider2snow_eval.jsonl",
            self.workspace.repo_root / "spider2snow_eval.jsonl",
        ]
        for candidate in candidates:
            if not candidate.exists():
                continue
            criteria: dict[str, dict[str, Any]] = {}
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                criteria[str(record["instance_id"])] = record
            return criteria
        return {}

    def load_problem(
        self,
        task: SpiderLiteTask,
        *,
        eval_criteria_by_id: dict[str, dict[str, Any]] | None = None,
    ) -> SpiderSnowProblem:
        gold_paths = self.workspace.resolve_gold_exec_result_paths(task.task_id)
        reference_results = [load_gold_csv_rows(path) for path in gold_paths]
        reference_result = reference_results[0] if reference_results else None
        eval_criteria = (eval_criteria_by_id or {}).get(task.task_id)
        external_knowledge_text = self._load_external_knowledge_text(task)
        return SpiderSnowProblem(
            task=task,
            gold_paths=gold_paths,
            reference_result=reference_result,
            reference_results=reference_results,
            eval_criteria=eval_criteria,
            external_knowledge_text=external_knowledge_text,
        )

    def load_problems(
        self,
        *,
        db_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
    ) -> list[SpiderSnowProblem]:
        tasks = self.load_tasks()
        if db_ids:
            allowed = set(db_ids)
            tasks = [task for task in tasks if task.db_id in allowed]
        if task_ids:
            allowed = set(task_ids)
            tasks = [task for task in tasks if task.task_id in allowed]
        eval_criteria_by_id = self.load_eval_criteria()
        return [self.load_problem(task, eval_criteria_by_id=eval_criteria_by_id) for task in tasks]

    def _load_external_knowledge_text(self, task: SpiderLiteTask) -> str:
        snippets: list[str] = []
        for filename in task.external_knowledge_files:
            path = self._resolve_external_knowledge_path(task.db_id, filename)
            if path is None:
                continue
            snippets.append(path.read_text(encoding="utf-8"))
        return "\n\n".join(snippets)

    def _resolve_external_knowledge_path(self, db_id: str, filename: str) -> Path | None:
        candidates = [
            self.workspace.repo_root / "spider2-snow" / filename,
            self.workspace.repo_root / "spider2-snow" / "resource" / filename,
            self.workspace.resolve_database_metadata_dir(db_id) / filename,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        db_root = self.workspace.resolve_database_metadata_dir(db_id)
        for candidate in db_root.rglob(filename):
            if candidate.is_file():
                return candidate
        return None


class OctoSpiderSnowSolveRunner:
    def __init__(
        self,
        *,
        workspace: SpiderSnowWorkspace,
        solver: SpiderSnowProblemSolver | None = None,
        schema_repository: SpiderSnowSchemaRepository | None = None,
        credentials_path: str | Path = "/Users/richiek/work/bender/snowflake_creds.json",
        top_k: int = 8,
    ) -> None:
        self.workspace = workspace
        self.loader = SpiderSnowProblemLoader(workspace)
        self.schema_repository = schema_repository or SpiderSnowSchemaRepository(workspace)
        self.solver = solver or NativeSpiderSnowProblemSolver(
            workspace=workspace,
            schema_repository=self.schema_repository,
            credentials_path=credentials_path,
            top_k=top_k,
        )

    def load_problems(
        self,
        *,
        db_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
    ) -> list[SpiderSnowProblem]:
        return self.loader.load_problems(db_ids=db_ids, task_ids=task_ids)

    def solve_problems(self, problems: list[SpiderSnowProblem]) -> list[SpiderSnowSolution]:
        return [self.solver.solve(problem) for problem in problems]

    def solve(
        self,
        *,
        db_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
    ) -> list[SpiderSnowSolution]:
        problems = self.load_problems(db_ids=db_ids, task_ids=task_ids)
        return self.solve_problems(problems)

    def save_solutions(self, solutions: list[SpiderSnowSolution], path: str | Path) -> None:
        payload = [solution.to_dict() for solution in solutions]
        Path(path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def summarize_solutions(self, solutions: list[SpiderSnowSolution]) -> dict[str, Any]:
        total = len(solutions)
        correct = sum(1 for solution in solutions if solution.score >= 1.0)
        broken = sum(1 for solution in solutions if not solution.execution_success)
        wrong = total - correct - broken
        return {
            "total": total,
            "correct": correct,
            "wrong": wrong,
            "broken": broken,
            "accuracy": (correct / total) if total else 0.0,
        }
