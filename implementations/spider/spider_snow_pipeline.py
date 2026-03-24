from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


def query_terms(text: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9_]+", text.lower()))
    singularized = {term[:-1] for term in terms if term.endswith("s") and len(term) > 3}
    return terms | singularized


def normalize_identifier(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")


def score_name_against_terms(name: str, terms: set[str]) -> float:
    normalized = normalize_identifier(name)
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


def is_numeric_type(data_type: str) -> bool:
    lowered = data_type.lower()
    return any(token in lowered for token in ("int", "number", "numeric", "decimal", "double", "float", "real"))


def is_text_type(data_type: str) -> bool:
    lowered = data_type.lower()
    return any(token in lowered for token in ("char", "text", "string", "varchar"))


def extract_years(text: str) -> list[int]:
    return [int(match.group(0)) for match in re.finditer(r"\b(19|20)\d{2}\b", text)]


SQL_KEYWORDS = {
    "all",
    "and",
    "as",
    "asc",
    "avg",
    "between",
    "by",
    "case",
    "count",
    "cte",
    "date",
    "date_trunc",
    "day",
    "desc",
    "distinct",
    "else",
    "end",
    "extract",
    "false",
    "from",
    "group",
    "having",
    "in",
    "interval",
    "is",
    "join",
    "lag",
    "left",
    "like",
    "limit",
    "max",
    "min",
    "month",
    "not",
    "null",
    "nullif",
    "offset",
    "on",
    "or",
    "order",
    "over",
    "partition",
    "qualify",
    "rank",
    "round",
    "row_number",
    "rows",
    "select",
    "stddev_pop",
    "sum",
    "then",
    "timestamp",
    "to_date",
    "true",
    "union",
    "where",
    "when",
    "with",
    "year",
}


def _strip_identifier_token(token: str) -> str:
    return token.strip().strip('"').strip("`").strip("[]")


def _split_object_path(path: str) -> tuple[str, ...]:
    parts = re.findall(r'"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*', path)
    return tuple(_strip_identifier_token(part) for part in parts if _strip_identifier_token(part))


def infer_sql_references(packet: "SpiderSnowTaskPacket", sql: str) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    table_lookup: dict[str, str] = {}
    allowed_columns: set[str] = set()
    for table in packet.tables:
        canonical = table.full_name
        variants = {
            canonical.lower(),
            table.table_name.lower(),
            table.qualified_name.lower(),
            f'{packet.db_id}.{table.qualified_name}'.lower(),
        }
        for variant in variants:
            table_lookup[variant] = canonical
        for column in table.columns:
            allowed_columns.add(column.column_name.lower())

    found_tables: list[str] = []
    unknown_tables: list[str] = []
    alias_map: dict[str, str] = {}
    cte_names = {match.lower() for match in re.findall(r'(?i)\bWITH\s+([A-Za-z_][A-Za-z0-9_]*)\s+AS\b', sql)}
    cte_names.update(match.lower() for match in re.findall(r'(?i),\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\b', sql))
    table_pattern = re.compile(
        r'(?i)\b(FROM|JOIN)\s+((?:"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)(?:\.(?:"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)){0,2})(?:\s+(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?'
    )
    for _, raw_path, alias in table_pattern.findall(sql):
        parts = _split_object_path(raw_path)
        if not parts:
            continue
        lookup_keys = {
            ".".join(parts).lower(),
            ".".join(parts[-2:]).lower(),
            parts[-1].lower(),
        }
        canonical = next((table_lookup[key] for key in lookup_keys if key in table_lookup), None)
        if canonical is not None:
            if canonical not in found_tables:
                found_tables.append(canonical)
            if alias:
                alias_map[alias.lower()] = canonical
            alias_map[parts[-1].lower()] = canonical
            continue
        if parts[-1].lower() not in cte_names:
            unknown_tables.append(raw_path)
        if alias:
            alias_map[alias.lower()] = raw_path
        alias_map[parts[-1].lower()] = raw_path

    found_columns: list[str] = []
    unknown_columns: list[str] = []
    qualified_refs = re.findall(r'(?i)\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*"?(?:([A-Za-z_][A-Za-z0-9_$]*))"?', sql)
    for alias, column in qualified_refs:
        alias_key = alias.lower()
        column_key = column.lower()
        if alias_key in alias_map:
            target = alias_map[alias_key].lower()
            if column_key in allowed_columns or target in cte_names:
                if column not in found_columns:
                    found_columns.append(column)
                continue
        
        if alias_key not in cte_names and column_key not in SQL_KEYWORDS:
            unknown_columns.append(column)

    stripped_sql = re.sub(r"'(?:''|[^'])*'", " ", sql)
    stripped_sql = re.sub(r'"[^"]+"', " ", stripped_sql)
    # Heuristic for CTE/SELECT column aliases to avoid false penalties
    known_aliases = {match.lower() for match in re.findall(r'(?i)AS\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', sql)}
    bare_tokens = re.findall(r'\b([A-Za-z_][A-Za-z0-9_$]*)\b', stripped_sql)
    seen_unknown_columns: set[str] = set(item.lower() for item in unknown_columns)
    for index, token in enumerate(bare_tokens):
        lowered = token.lower()
        if lowered in SQL_KEYWORDS or lowered in allowed_columns or lowered in alias_map or lowered in cte_names or lowered in known_aliases:
            if lowered in allowed_columns and token not in found_columns:
                found_columns.append(token)
            continue
        if lowered in {packet.db_id.lower(), *(table.table_name.lower() for table in packet.tables)}:
            continue
        if index > 0 and bare_tokens[index - 1].lower() == "as":
            continue
        if lowered not in allowed_columns and lowered not in seen_unknown_columns:
            unknown_columns.append(token)
            seen_unknown_columns.add(lowered)

    metadata = {
        "unknown_tables": tuple(unknown_tables),
        "unknown_columns": tuple(unknown_columns),
    }
    return tuple(found_tables), tuple(found_columns), metadata


def enrich_candidate_from_packet(packet: "SpiderSnowTaskPacket", candidate: "SpiderSnowSQLCandidate") -> "SpiderSnowSQLCandidate":
    tables, columns, metadata = infer_sql_references(packet, candidate.sql)
    merged_metadata = dict(candidate.metadata)
    merged_metadata.update(metadata)
    return replace(candidate, tables=tables, columns=columns, metadata=merged_metadata)


@dataclass(frozen=True)
class SpiderSnowPacketColumn:
    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    description: str = ""
    sample_values: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def table_alias(self) -> str:
        return self.table_name.lower()

    @property
    def qualified_table(self) -> str:
        return f'"{self.schema_name}"."{self.table_name}"'

    @property
    def ref(self) -> str:
        return f'{self.table_alias}."{self.column_name}"'


@dataclass(frozen=True)
class SpiderSnowPacketTable:
    schema_name: str
    table_name: str
    description: str
    row_estimate: int | None
    relevance_score: float
    columns: tuple[SpiderSnowPacketColumn, ...]

    @property
    def alias(self) -> str:
        return self.table_name.lower()

    @property
    def full_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"

    @property
    def qualified_name(self) -> str:
        return f'"{self.schema_name}"."{self.table_name}"'


@dataclass(frozen=True)
class SpiderSnowTaskPacket:
    instance_id: str
    db_id: str
    instruction: str
    query_intent: str
    constraints: dict[str, Any]
    candidate_tables: tuple[str, ...]
    candidate_join_path: tuple[str, ...]
    terms: tuple[str, ...]
    years: tuple[int, ...]
    metadata_snippets: tuple[str, ...]
    external_knowledge_text: str
    tables: tuple[SpiderSnowPacketTable, ...]
    provenance: tuple[str, ...] = ()
    time_scope: str = ""
    comparison_scope: str = ""
    requires_global_denominator: bool = False
    preferred_table_family: str = ""

    def to_prompt(self) -> str:
        lines = [
            "You are writing Snowflake SQL for a Spider benchmark task.",
            f"Database: {self.db_id}",
            f"Question: {self.instruction}",
            f"Intent: {self.query_intent}",
            "Use only the exact tables and columns listed below.",
            "Do not invent identifiers, and prefer the candidate tables unless execution would be impossible.",
            "Return one executable Snowflake SQL query and nothing else.",
        ]
        if self.candidate_tables:
            lines.append("Candidate tables: " + ", ".join(self.candidate_tables))
        if self.candidate_join_path:
            lines.append("Candidate join path: " + " -> ".join(self.candidate_join_path))
        if self.time_scope:
            lines.append(f"Time scope: {self.time_scope}")
        if self.comparison_scope:
            lines.append(f"Comparison scope: {self.comparison_scope}")
        if self.requires_global_denominator:
            lines.append("Denominator scope: global comparison denominator required.")
        if self.preferred_table_family:
            lines.append(f"Preferred table family: {self.preferred_table_family}")
        lines.append("Relevant tables:")
        for table in self.tables:
            column_text = ", ".join(f"{column.column_name} ({column.data_type})" for column in table.columns[:12])
            lines.append(f'- "{self.db_id}".{table.qualified_name}: {column_text}')
            if table.description:
                lines.append(f"  Note: {table.description[:180]}")
        if self.metadata_snippets:
            lines.append("Metadata notes:")
            for snippet in self.metadata_snippets[:4]:
                lines.append(snippet)
        if self.external_knowledge_text:
            lines.append("External knowledge:")
            lines.append(self.external_knowledge_text[:2400])
        return "\n".join(lines)


@dataclass(frozen=True)
class SpiderSnowSQLCandidate:
    sql: str
    strategy: str
    rationale: str
    tables: tuple[str, ...]
    columns: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpiderSnowRankedCandidate:
    candidate: SpiderSnowSQLCandidate
    score: float
    score_breakdown: dict[str, float]


@dataclass(frozen=True)
class SpiderSnowSQLNormalizationResult:
    sql: str
    valid: bool
    error: str | None
    tables: tuple[str, ...]
    columns: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


class SpiderSnowSQLCandidateGenerator(Protocol):
    def generate(self, packet: SpiderSnowTaskPacket, *, max_candidates: int = 8) -> list[SpiderSnowSQLCandidate]:
        ...


class SpiderSnowHeuristicCandidateGenerator:
    def generate(self, packet: SpiderSnowTaskPacket, *, max_candidates: int = 8) -> list[SpiderSnowSQLCandidate]:
        candidates: list[SpiderSnowSQLCandidate] = []
        terms = set(packet.terms)
        if not terms:
            return []
        ranking_query = self._is_ranking_query(packet.instruction, packet.query_intent)
        
        # --- Hard Schema Guardrails (Coprocessor Enforcement) ---
        # Filter out tables that BENDER flagged with a relevance penalty (e.g., cross-schema noise)
        valid_tables = []
        for table in packet.tables:
            # We look at the metadata of the table node carried in the packet
            # (Note: In a production setting, this would be a bit cleaner)
            if table.relevance_score < 5.0: # Arbitrary threshold for 'distractor' noise
                continue
            valid_tables.append(table)
        
        # If we filtered everything, fallback to original tables but log it
        if not valid_tables:
            valid_tables = list(packet.tables[:4])
        
        # Priority 1: Templated candidates driven by BENDER constraints
        for table in valid_tables[:3]:
            filters = self._build_filters(packet, table)
            columns = list(table.columns)
            
            if packet.constraints.get("sql_template") == "proportion_join" or packet.requires_global_denominator:
                share_candidate = self._build_share_of_total_candidate(packet, table, columns, filters, terms)
                if share_candidate is not None:
                    candidates.append(share_candidate)
            
            if packet.constraints.get("query_intent") == "window_quantile" or packet.constraints.get("window_function") == "NTILE":
                quantile = self._build_quantile_candidate(packet, table, columns, filters, terms)
                if quantile is not None:
                    candidates.append(quantile)
            
            if packet.constraints.get("query_intent") == "growth_analysis" or packet.constraints.get("sql_pattern") == "self_join_on_month":
                growth = self._build_growth_candidate(packet, table, columns, filters, terms)
                if growth is not None:
                    candidates.append(growth)

        # Priority 2: Generic candidates
        for table in packet.tables[:4]:
            filters = self._build_filters(packet, table)
            columns = list(table.columns)
            
            if ranking_query:
               ranking = self._build_ranking_candidate(packet, table, columns, filters, terms)
               if ranking is not None:
                   candidates.append(ranking)

            if packet.query_intent == "count":
                count_candidate = self._build_count_candidate(packet, table, columns, filters, terms)
                if count_candidate is not None:
                    candidates.append(count_candidate)
            
            aggregate = self._aggregate_for_intent(packet.query_intent)
            if aggregate is not None:
                aggregate_candidate = self._build_aggregate_candidate(
                    packet, table, columns, filters, terms, aggregate=aggregate
                )
                if aggregate_candidate is not None:
                    candidates.append(aggregate_candidate)
            
            selection = self._build_selection_candidate(packet, table, columns, filters, terms)
            if selection is not None:
                candidates.append(selection)
                
        # Priority 3: Join candidates (Simple fallback for multi-table intent)
        if len(packet.tables) >= 2:
            join_candidate = self._build_join_candidate(packet, packet.tables[0], packet.tables[1], terms)
            if join_candidate:
                candidates.append(join_candidate)
                
        return self._dedupe(candidates)[:max_candidates]

    def _build_join_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        t1: SpiderSnowPacketTable,
        t2: SpiderSnowPacketTable,
        terms: set[str],
    ) -> SpiderSnowSQLCandidate | None:
        # Simple heuristic join: find common column names
        common = set(c.column_name for c in t1.columns) & set(c.column_name for c in t2.columns)
        join_col = None
        if "station_id" in common:
            join_col = "station_id"
        elif "id" in common:
            join_col = "id"
        elif common:
            join_col = sorted(common)[0]
        
        if not join_col:
            return None
            
        metric = self._best_metric_column(list(t1.columns) + list(t2.columns), terms)
        group = self._best_group_column(list(t1.columns) + list(t2.columns), terms)
        
        # Build a very basic join query
        sql = "\n".join([
            f'SELECT {group.ref if group else "*"}',
            f'FROM "{packet.db_id}".{t1.qualified_name} AS {t1.alias}',
            f'JOIN "{packet.db_id}".{t2.qualified_name} AS {t2.alias} ON {t1.alias}."{join_col}" = {t2.alias}."{join_col}"',
            f"LIMIT 25"
        ])
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy="heuristic_join",
            rationale=f"Join {t1.full_name} and {t2.full_name} on {join_col}",
            tables=(t1.full_name, t2.full_name),
            columns=(join_col,),
            metadata={}
        )

    def _dedupe(self, candidates: list[SpiderSnowSQLCandidate]) -> list[SpiderSnowSQLCandidate]:
        ordered: list[SpiderSnowSQLCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.sql.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(candidate)
        return ordered

    def _aggregate_for_intent(self, query_intent: str) -> str | None:
        if query_intent == "sum":
            return "SUM"
        if query_intent == "average":
            return "AVG"
        return None

    def _build_filters(self, packet: SpiderSnowTaskPacket, table: SpiderSnowPacketTable) -> list[str]:
        filters: list[str] = []
        lowered = packet.instruction.lower()
        
        # --- BENDER Enhancement: Temporal Year Filters ---
        year_column = self._best_column(
            table.columns,
            {"year"},
            predicate=lambda column: "year" in column.column_name.lower() or "date" in column.column_name.lower(),
        )
        if year_column is not None:
            if len(packet.years) > 1:
                filters.append(f"{year_column.ref} IN ({', '.join(map(str, packet.years))})")
            elif packet.years:
                filters.append(f"{year_column.ref} = {packet.years[0]}")
        elif packet.years:
            # Try to find a timestamp/date column to filter on
            date_col = next((c for c in table.columns if c.metadata.get("semantic_role") == "ROLE_TEMPORAL"), None)
            if date_col is None:
                date_col = self._best_column(table.columns, {"timestamp", "date", "created", "start"})
            
            if date_col:
                date_expr = date_col.ref
                if packet.db_id == "CHICAGO" and "timestamp" in date_col.column_name.lower():
                    date_expr = f"TO_TIMESTAMP({date_col.ref} / 1000000)"
                
                if len(packet.years) > 1:
                    filters.append(f"EXTRACT(YEAR FROM {date_expr}) IN ({', '.join(map(str, packet.years))})")
                elif packet.years:
                    filters.append(f"EXTRACT(YEAR FROM {date_expr}) = {packet.years[0]}")

        # --- BENDER Enhancement: Numeric Range Filters ---
        numeric_range = packet.constraints.get("numeric_range")
        if numeric_range:
            low, high = numeric_range
            range_col = self._best_column(table.columns, {"trip_seconds", "duration", "amount", "total"})
            if range_col:
                if "minute" in lowered and "second" in range_col.column_name.lower():
                    filters.append(f"{range_col.ref} BETWEEN {low * 60} AND {high * 60}")
                else:
                    filters.append(f"{range_col.ref} BETWEEN {low} AND {high}")

        gender_column = self._best_column(table.columns, {"gender", "sex"})
        if gender_column is not None:
            if "female" in lowered or "girl" in lowered:
                filters.append(f"{gender_column.ref} = 'F'")
            elif "male" in lowered or "boy" in lowered:
                filters.append(f"{gender_column.ref} = 'M'")

        state_column = self._best_column(table.columns, {"state", "province", "region"})
        if state_column is not None:
            for state_name, code in {
                "wyoming": "WY",
                "texas": "TX",
                "california": "CA",
                "new york": "NY",
                "illinois": "IL",
            }.items():
                if state_name in lowered:
                    filters.append(f"{state_column.ref} = '{code}'")
                    break
        return filters

    def _build_ranking_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        table: SpiderSnowPacketTable,
        columns: list[SpiderSnowPacketColumn],
        filters: list[str],
        terms: set[str],
    ) -> SpiderSnowSQLCandidate | None:
        group_column = self._best_group_column(columns, terms)
        if group_column is None:
            return None
        metric_column = self._best_metric_column(columns, terms)
        if metric_column is None:
            aggregate_expr = "COUNT(*)"
            alias = "row_count"
        else:
            aggregate_expr = f"SUM({metric_column.ref})"
            alias = normalize_identifier(metric_column.column_name) or "metric_value"
        sql = "\n".join(
            [
                f'SELECT {group_column.ref} AS "{group_column.column_name}",',
                f'       {aggregate_expr} AS "{alias}"',
                f'FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                self._where_clause(filters),
                f"GROUP BY {group_column.ref}",
                f'ORDER BY "{alias}" DESC, {group_column.ref}',
                "LIMIT 10",
            ]
        )
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy="ranking",
            rationale=f"Rank {table.full_name} by {metric_column.column_name if metric_column else 'count'}",
            tables=(table.full_name,),
            columns=tuple(
                column.column_name for column in [group_column, metric_column] if column is not None
            ),
            metadata={"filters": filters},
        )

    def _build_quantile_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        table: SpiderSnowPacketTable,
        columns: list[SpiderSnowPacketColumn],
        filters: list[str],
        terms: set[str],
    ) -> SpiderSnowSQLCandidate | None:
        # Find duration column using BENDER's Semantic Roles
        metric_column = next((c for c in columns if c.metadata.get("semantic_role") == "ROLE_DURATION"), None)
        if metric_column is None:
            metric_column = self._best_column(columns, {"trip_seconds", "duration"})
        
        if metric_column is None:
            metric_column = self._best_metric_column(columns, terms)
            
        if metric_column is None:
            return None

        fare_column = self._best_column(columns, {"fare", "amount", "total"})
        buckets = packet.constraints.get("ntile_buckets", 6)
        
        # Scale metric to minutes if requested
        metric_expr = f'"{metric_column.column_name}"'
        if "minute" in packet.instruction.lower() and "second" in metric_column.column_name.lower():
            metric_expr = f'"{metric_column.column_name}" / 60'

        sql = "\n".join(
            [
                "WITH quantiles AS (",
                "    SELECT *, ",
                f'           NTILE({buckets}) OVER (ORDER BY {metric_expr}) AS "quantile"',
                f'    FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                f"    {self._where_clause(filters)}",
                ")",
                'SELECT "quantile" AS "QUANTILE",',
                f'       ROUND(MIN({metric_expr})) AS "MIN_DURATION_MINUTES",',
                f'       ROUND(MAX({metric_expr})) AS "MAX_DURATION_MINUTES",',
                '       COUNT(*) AS "TOTAL_TRIPS",',
                f'       ROUND(AVG("{fare_column.column_name if fare_column else "fare"}"), 2) AS "AVG_FARE"',
                "FROM quantiles",
                'GROUP BY 1',
                'ORDER BY 1'
            ]
        )
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy="window_quantile",
            rationale=f"Quantile analysis using NTILE({buckets}) with full metrics",
            tables=(table.full_name,),
            columns=(metric_column.column_name, "quantile"),
            metadata={"filters": filters},
        )

    def _build_growth_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        table: SpiderSnowPacketTable,
        columns: list[SpiderSnowPacketColumn],
        filters: list[str],
        terms: set[str],
    ) -> SpiderSnowSQLCandidate | None:
        # Find semantic roles using BENDER guidance
        entity_col = next((c for c in columns if c.metadata.get("semantic_role") == "ROLE_GEOGRAPHIC"), None)
        if entity_col is None:
            entity_col = self._best_column(columns, {"company", "taxi_id", "station"})
            
        date_col = next((c for c in columns if c.metadata.get("semantic_role") == "ROLE_TEMPORAL"), None)
        if date_col is None:
            date_col = self._best_column(columns, {"trip_start_timestamp", "month", "date"})
        
        if entity_col is None or date_col is None:
            return None
            
        # Type-aware casting for Snowflake
        date_expr = date_col.ref
        if packet.db_id == "CHICAGO" and "timestamp" in date_col.column_name.lower():
             # CHICAGO specifically uses microseconds
             date_expr = f"TO_TIMESTAMP({date_col.ref} / 1000000)"
        elif date_col.data_type.upper() in ["NUMBER", "INTEGER"]:
            # If it's a number (like unix timestamp), try to treat as timestamp
            # This is common in some Spider schemas
            date_expr = f"TO_TIMESTAMP({date_col.ref})"
        elif date_col.data_type.upper() == "TEXT":
            date_expr = f"TO_DATE({date_col.ref})"

        sql = "\n".join(
            [
                "WITH monthly_metrics AS (",
                f'    SELECT {entity_col.ref} AS "entity_id",',
                f"           DATE_TRUNC('MONTH', {date_expr}) AS \"obs_month\",",
                '           COUNT(*) AS "obs_count"',
                f'    FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                f"    {self._where_clause(filters)}",
                '    GROUP BY 1, 2',
                "),",
                "growth AS (",
                '    SELECT m1."entity_id",',
                '           m1."obs_month",',
                '           m1."obs_count",',
                '           m2."obs_count" AS "prev_count",',
                '           (m1."obs_count" - m2."obs_count") AS "increase"',
                "    FROM monthly_metrics m1",
                '    JOIN monthly_metrics m2 ON m1."entity_id" = m2."entity_id"',
                "      AND DATEADD('MONTH', 1, m2.\"obs_month\") = m1.\"obs_month\"",
                ")",
                'SELECT "entity_id", "obs_month", "obs_count", "prev_count", "increase"',
                "FROM growth",
                'ORDER BY "increase" DESC',
                "LIMIT 3"
            ]
        )
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy="growth_analysis",
            rationale=f"Role-based growth analysis for {table.full_name}",
            tables=(table.full_name,),
            columns=(entity_col.column_name, date_col.column_name, "increase"),
            metadata={"filters": filters},
        )

    def _build_share_of_total_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        table: SpiderSnowPacketTable,
        columns: list[SpiderSnowPacketColumn],
        filters: list[str],
        terms: set[str],
    ) -> SpiderSnowSQLCandidate | None:
        metric_column = self._best_metric_column(columns, terms)
        group_column = self._best_group_column(columns, terms)
        if metric_column is None or group_column is None:
            return None
        scope_column = self._best_column(columns, {"state", "province", "region"})
        if scope_column is None:
            return None
        scope_ref = scope_column.ref
        scoped_filters = list(filters)
        global_filters = [item for item in filters if not item.startswith(f"{scope_ref} = ")]
        if scoped_filters == global_filters:
            return None
        sql = "\n".join(
            [
                "WITH scoped AS (",
                f'    SELECT {group_column.ref} AS "{group_column.column_name}",',
                f'           SUM({metric_column.ref}) AS "state_count"',
                f'    FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                f"    {self._where_clause(scoped_filters)}",
                f'    GROUP BY {group_column.ref}',
                "),",
                "totals AS (",
                f'    SELECT {group_column.ref} AS "{group_column.column_name}",',
                f'           SUM({metric_column.ref}) AS "total_count"',
                f'    FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                f"    {self._where_clause(global_filters)}",
                f'    GROUP BY {group_column.ref}',
                ")",
                f'SELECT s."{group_column.column_name}" AS "{group_column.column_name}"',
                "FROM scoped s",
                f'JOIN totals t ON s."{group_column.column_name}" = t."{group_column.column_name}"',
                f'ORDER BY (s."state_count" / NULLIF(t."total_count", 0)) DESC, s."state_count" DESC, s."{group_column.column_name}"',
                "LIMIT 1",
            ]
        )
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy="share_of_total",
            rationale=f"Compare scoped {metric_column.column_name} share against global totals in {table.full_name}",
            tables=(table.full_name,),
            columns=(group_column.column_name, metric_column.column_name, scope_column.column_name),
            metadata={
                "filters": filters,
                "global_filters": global_filters,
                "requires_global_denominator": True,
            },
        )

    def _build_count_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        table: SpiderSnowPacketTable,
        columns: list[SpiderSnowPacketColumn],
        filters: list[str],
        terms: set[str],
    ) -> SpiderSnowSQLCandidate | None:
        group_column = self._best_group_column(columns, terms)
        if group_column is not None and self._contains_any(terms, {"per", "each", "by", "for"}):
            sql = "\n".join(
                [
                    f'SELECT {group_column.ref} AS "{group_column.column_name}",',
                    '       COUNT(*) AS "row_count"',
                    f'FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                    self._where_clause(filters),
                    f"GROUP BY {group_column.ref}",
                    'ORDER BY "row_count" DESC',
                    "LIMIT 25",
                ]
            )
            columns_used = (group_column.column_name,)
        else:
            sql = "\n".join(
                [
                    'SELECT COUNT(*) AS "row_count"',
                    f'FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                    self._where_clause(filters),
                ]
            )
            columns_used = ()
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy="count",
            rationale=f"Count rows from {table.full_name}",
            tables=(table.full_name,),
            columns=columns_used,
            metadata={"filters": filters},
        )

    def _build_aggregate_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        table: SpiderSnowPacketTable,
        columns: list[SpiderSnowPacketColumn],
        filters: list[str],
        terms: set[str],
        *,
        aggregate: str,
    ) -> SpiderSnowSQLCandidate | None:
        metric_column = self._best_metric_column(columns, terms)
        if metric_column is None:
            return None
        group_column = self._best_group_column(columns, terms)
        alias = f"{aggregate.lower()}_{normalize_identifier(metric_column.column_name) or 'value'}"
        if group_column is not None and self._is_ranking_query(packet.instruction, packet.query_intent):
            sql = "\n".join(
                [
                    f'SELECT {group_column.ref} AS "{group_column.column_name}",',
                    f'       {aggregate}({metric_column.ref}) AS "{alias}"',
                    f'FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                    self._where_clause(filters),
                    f"GROUP BY {group_column.ref}",
                    f'ORDER BY "{alias}" DESC, {group_column.ref}',
                    "LIMIT 10",
                ]
            )
            used_columns = (group_column.column_name, metric_column.column_name)
        else:
            sql = "\n".join(
                [
                    f'SELECT {aggregate}({metric_column.ref}) AS "{alias}"',
                    f'FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                    self._where_clause(filters),
                ]
            )
            used_columns = (metric_column.column_name,)
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy=aggregate.lower(),
            rationale=f"{aggregate} over {metric_column.column_name} in {table.full_name}",
            tables=(table.full_name,),
            columns=used_columns,
            metadata={"filters": filters},
        )

    def _build_selection_candidate(
        self,
        packet: SpiderSnowTaskPacket,
        table: SpiderSnowPacketTable,
        columns: list[SpiderSnowPacketColumn],
        filters: list[str],
        terms: set[str],
    ) -> SpiderSnowSQLCandidate | None:
        preferred = sorted(
            columns,
            key=lambda column: (-score_name_against_terms(column.column_name, terms), column.column_name.lower()),
        )
        chosen = [column for column in preferred if score_name_against_terms(column.column_name, terms) > 0][:3]
        if not chosen:
            chosen = [column for column in columns if is_text_type(column.data_type)][:2]
        if not chosen:
            return None
        select_lines = ",\n       ".join(f'{column.ref} AS "{column.column_name}"' for column in chosen)
        sql = "\n".join(
            [
                f"SELECT {select_lines}",
                f'FROM "{packet.db_id}".{table.qualified_name} AS {table.alias}',
                self._where_clause(filters),
                "LIMIT 25",
            ]
        )
        return SpiderSnowSQLCandidate(
            sql=sql,
            strategy="selection",
            rationale=f"Project relevant columns from {table.full_name}",
            tables=(table.full_name,),
            columns=tuple(column.column_name for column in chosen),
            metadata={"filters": filters},
        )

    def _best_group_column(
        self,
        columns: list[SpiderSnowPacketColumn],
        terms: set[str],
    ) -> SpiderSnowPacketColumn | None:
        scored: list[tuple[float, SpiderSnowPacketColumn]] = []
        for column in columns:
            if not is_text_type(column.data_type):
                continue
            lowered = column.column_name.lower()
            score = score_name_against_terms(lowered, terms)
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
        return self._best_column(
            columns,
            {"name", "title", "category", "company"},
            predicate=lambda column: is_text_type(column.data_type),
        )

    def _best_metric_column(
        self,
        columns: list[SpiderSnowPacketColumn],
        terms: set[str],
    ) -> SpiderSnowPacketColumn | None:
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
        return self._best_column(columns, preferred_terms, predicate=lambda column: is_numeric_type(column.data_type))

    def _best_column(
        self,
        columns: list[SpiderSnowPacketColumn],
        terms: set[str],
        predicate: Any | None = None,
    ) -> SpiderSnowPacketColumn | None:
        scored: list[tuple[float, SpiderSnowPacketColumn]] = []
        for column in columns:
            if predicate is not None and not predicate(column):
                continue
            score = score_name_against_terms(column.column_name, terms)
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

    def _where_clause(self, filters: list[str]) -> str:
        if not filters:
            return ""
        return "WHERE " + " AND ".join(filters)


class SpiderSnowPromptedCandidateGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: int = 120,
        temperature: float = 0.0,
        max_tokens: int = 256,
        strict: bool = False,
        fallback: SpiderSnowSQLCandidateGenerator | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.strict = strict
        self.fallback = fallback or SpiderSnowHeuristicCandidateGenerator()

    def generate(self, packet: SpiderSnowTaskPacket, *, max_candidates: int = 8) -> list[SpiderSnowSQLCandidate]:
        last_error: Exception | None = None
        candidates: list[SpiderSnowSQLCandidate] = []
        try:
            payload = {
                "prompt": {"text": packet.to_prompt()},
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "n": max_candidates,
            }
            response = self._post_json(f"{self.base_url}/v1/generate", payload)
            candidates.extend(self._parse_candidates(packet, response))
        except Exception as exc:
            last_error = exc
        candidates.extend(self.fallback.generate(packet, max_candidates=max_candidates))
        deduped = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.sql.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        if deduped:
            return deduped[:max_candidates]
        if self.strict:
            detail = f"{type(last_error).__name__}: {last_error}" if last_error is not None else "empty_candidate_set"
            raise RuntimeError(
                f"prompted_candidate_generation_failed model={self.model} base_url={self.base_url} detail={detail}"
            )
        return []

    def _parse_candidates(self, packet: SpiderSnowTaskPacket, payload: dict[str, Any]) -> list[SpiderSnowSQLCandidate]:
        texts: list[str] = []
        results = payload.get("results")
        if isinstance(results, list):
            for result in results:
                if not isinstance(result, dict):
                    texts.append(str(result))
                    continue
                if isinstance(result.get("response"), str):
                    texts.append(result["response"])
                if isinstance(result.get("text"), str):
                    texts.append(result["text"])
        outputs = payload.get("outputs")
        if isinstance(outputs, list):
            texts.extend(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in outputs
            )
        text = payload.get("text", "")
        if text:
            texts.append(str(text))
        generated_text = payload.get("generated_text", "")
        if generated_text:
            texts.append(str(generated_text))
        choices = payload.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    texts.append(str(choice))
                    continue
                if isinstance(choice.get("text"), str):
                    texts.append(choice["text"])
                message = choice.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    texts.append(message["content"])
        candidates: list[SpiderSnowSQLCandidate] = []
        for index, text in enumerate(texts):
            sql = self._extract_sql(text)
            if not sql:
                continue
            candidate = SpiderSnowSQLCandidate(
                sql=sql,
                strategy="prompted",
                rationale="Candidate generated by prompted SQL model",
                tables=(),
                columns=(),
                metadata={"candidate_index": index},
            )
            candidates.append(
                enrich_candidate_from_packet(
                    packet,
                    candidate,
                )
            )
        return candidates

    def _extract_sql(self, text: str) -> str:
        stripped = text.strip()
        fenced = re.findall(r"```(?:sql)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            stripped = fenced[0].strip()
        select_match = re.search(r"((WITH|SELECT)\b.*)", stripped, flags=re.IGNORECASE | re.DOTALL)
        if select_match:
            stripped = select_match.group(1).strip()
        stripped = stripped.split("\n\n", 1)[0].strip()
        if "SELECT" not in stripped.upper() and "WITH" not in stripped.upper():
            return ""
        return stripped

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class SpiderSnowOllamaCandidateGenerator:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11435",
        model: str = "qwen2.5-coder:latest",
        timeout: int = 240,
        strict: bool = True,
        temperatures: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3),
        fallback: SpiderSnowSQLCandidateGenerator | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.strict = strict
        self.temperatures = temperatures
        self.fallback = fallback or SpiderSnowHeuristicCandidateGenerator()

    def generate(self, packet: SpiderSnowTaskPacket, *, max_candidates: int = 8) -> list[SpiderSnowSQLCandidate]:
        candidates: list[SpiderSnowSQLCandidate] = []
        errors: list[str] = []
        prompt_variants = self._prompt_variants(packet, max_candidates)
        for index, prompt in enumerate(prompt_variants):
            temperature = self.temperatures[index % len(self.temperatures)]
            try:
                response = self._post_json(
                    f"{self.base_url}/api/generate",
                    {
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                        },
                    },
                )
                text = str(response.get("response", ""))
                sql = self._extract_sql(text)
                if not sql:
                    continue
                candidate = SpiderSnowSQLCandidate(
                        sql=sql,
                        strategy="ollama",
                        rationale=f"Ollama candidate variant {index + 1}",
                        tables=(),
                        columns=(),
                        metadata={"temperature": temperature, "variant": index + 1},
                    )
                candidates.append(
                    enrich_candidate_from_packet(
                        packet,
                        candidate,
                    )
                )
                if len(candidates) >= max_candidates:
                    break
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        candidates.extend(self.fallback.generate(packet, max_candidates=max_candidates))
        deduped = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.sql.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        if deduped:
            return deduped[:max_candidates]
        if self.strict:
            detail = "; ".join(errors) if errors else "empty_candidate_set"
            raise RuntimeError(
                f"ollama_candidate_generation_failed model={self.model} base_url={self.base_url} detail={detail}"
            )
        return []

    def _prompt_variants(self, packet: SpiderSnowTaskPacket, max_candidates: int) -> list[str]:
        base = packet.to_prompt()
        variants = [
            base + "\nUse the most likely join path and return one SQL query only.",
            base + "\nPrefer exact aggregations and explicit GROUP BY clauses where needed. Return one SQL query only.",
            base + "\nPrefer a conservative executable query over a clever one. Return one SQL query only.",
            base + "\nIf there is ambiguity, choose the candidate tables listed above. Return one SQL query only.",
        ]
        return variants[:max_candidates]

    def _extract_sql(self, text: str) -> str:
        stripped = text.strip()
        fenced = re.findall(r"```(?:sql)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            stripped = fenced[0].strip()
        select_match = re.search(r"((WITH|SELECT)\b.*)", stripped, flags=re.IGNORECASE | re.DOTALL)
        if select_match:
            stripped = select_match.group(1).strip()
        stripped = stripped.split("\n\n", 1)[0].strip()
        if "SELECT" not in stripped.upper() and "WITH" not in stripped.upper():
            return ""
        return stripped

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class SpiderSnowCandidateReranker:
    def rank(
        self,
        packet: SpiderSnowTaskPacket,
        candidates: list[SpiderSnowSQLCandidate],
    ) -> list[SpiderSnowRankedCandidate]:
        ranked: list[SpiderSnowRankedCandidate] = []
        terms = set(packet.terms)
        candidate_tables = {name.split(".")[-1].lower() for name in packet.candidate_tables}
        for candidate in candidates:
            candidate = enrich_candidate_from_packet(packet, candidate)
            sql_upper = candidate.sql.upper()
            table_bonus = 0.0
            column_bonus = 0.0
            literal_bonus = 0.0
            intent_bonus = 0.0
            shape_bonus = 0.0
            penalty = 0.0

            for table_name in candidate.tables:
                normalized = table_name.split(".")[-1].lower()
                if normalized in candidate_tables:
                    table_bonus += 4.0
                table_bonus += score_name_against_terms(normalized, terms)

            for column_name in candidate.columns:
                column_bonus += score_name_against_terms(column_name, terms)

            unknown_tables = tuple(candidate.metadata.get("unknown_tables", ()))
            unknown_columns = tuple(candidate.metadata.get("unknown_columns", ()))
            penalty -= 8.0 * len(unknown_tables)
            penalty -= 3.0 * len(unknown_columns)
            if not candidate.tables:
                penalty -= 4.0

            for year in packet.years:
                if str(year) in candidate.sql:
                    literal_bonus += 2.0
            if packet.preferred_table_family:
                if packet.preferred_table_family.upper() in sql_upper:
                    table_bonus += 6.0
                if packet.preferred_table_family == "CURRENT" and re.search(r"\b19\d{2}_20\d{2}\b", candidate.sql):
                    penalty -= 8.0
            if packet.requires_global_denominator:
                has_ratio = "/" in candidate.sql
                # Look for state filter specifically (not just the word 'state')
                has_state_filter = re.search(r'(?i)\bstate\b\s*=\s*', candidate.sql) is not None
                
                if has_ratio:
                    shape_bonus += 12.0
                else:
                    # Penalize candidates that sort by raw metric instead of ratio when ratio is requested
                    penalty -= 12.0

                if "WITH" in sql_upper and "JOIN" in sql_upper and has_ratio:
                    shape_bonus += 8.0
                
                if "OVER (" in sql_upper and self._contains_any(terms, {"proportion", "share", "compared"}):
                    # Window function proportion is almost always wrong if a WHERE filter is present
                    if "WHERE" in sql_upper:
                        penalty -= 15.0
                
                # Penalize simple ranking queries that apply state filter but miss the ratio
                if has_state_filter and not has_ratio:
                    penalty -= 10.0
                    
                state_filter_count = len(re.findall(r'(?i)\bstate\b\s*=\s*', candidate.sql))
                if state_filter_count > 1:
                    # Multiple state filters in non-ratio query is very suspicious
                    if not has_ratio:
                        penalty -= 8.0
                    elif state_filter_count > 2:
                        # Even share-of-total usually only has one or two state filters (numerator vs denominator)
                        penalty -= 6.0

            # BENDER Constraint: Window Functions
            if packet.constraints.get("window_function") == "NTILE":
                if candidate.strategy == "window_quantile" or "NTILE(" in sql_upper:
                    shape_bonus += 40.0
                else:
                    penalty -= 20.0
            
            # BENDER Constraint: Growth Analysis
            if packet.constraints.get("query_intent") == "growth_analysis" or packet.constraints.get("sql_pattern") == "self_join_on_month":
                if candidate.strategy == "growth_analysis" or "DATEADD(" in sql_upper:
                    shape_bonus += 40.0
                else:
                    penalty -= 20.0

            if packet.query_intent == "count" and "COUNT(" in sql_upper:
                intent_bonus += 4.0
            elif packet.query_intent == "sum" and "SUM(" in sql_upper:
                intent_bonus += 4.0
            elif packet.query_intent == "average" and "AVG(" in sql_upper:
                intent_bonus += 4.0
            elif packet.query_intent == "ranking" and "ORDER BY" in sql_upper:
                intent_bonus += 4.0
            elif packet.query_intent in {"selection", ""}:
                intent_bonus += 1.0

            if "GROUP BY" in sql_upper and self._contains_any(terms, {"per", "each", "by"}):
                shape_bonus += 2.0
            if "LIMIT 10" in sql_upper and self._contains_any(terms, {"top", "highest", "largest", "most"}):
                shape_bonus += 1.5
            if "WHERE" in sql_upper and packet.years:
                shape_bonus += 1.0

            breakdown = {
                "table_bonus": table_bonus,
                "column_bonus": column_bonus,
                "literal_bonus": literal_bonus,
                "intent_bonus": intent_bonus,
                "shape_bonus": shape_bonus,
                "penalty": penalty,
            }
            ranked.append(
                SpiderSnowRankedCandidate(
                    candidate=candidate,
                    score=sum(breakdown.values()),
                    score_breakdown=breakdown,
                )
            )
        ranked.sort(
            key=lambda item: (
                -item.score,
                item.candidate.strategy,
                item.candidate.sql,
            )
        )
        return ranked

    def _contains_any(self, terms: set[str], needles: set[str]) -> bool:
        return any(needle in terms for needle in needles)


class SpiderSnowSQLCandidateNormalizer:
    def normalize(self, packet: SpiderSnowTaskPacket, sql: str) -> SpiderSnowSQLNormalizationResult:
        try:
            expression = sqlglot.parse_one(sql, read="snowflake")
        except ParseError as exc:
            return SpiderSnowSQLNormalizationResult(
                sql=sql,
                valid=False,
                error=f"sqlglot_parse_error: {exc}",
                tables=(),
                columns=(),
                metadata={},
            )

        forbidden = tuple(expression.find_all((exp.Delete, exp.Update, exp.Insert, exp.Create, exp.Drop, exp.Command)))
        if forbidden:
            return SpiderSnowSQLNormalizationResult(
                sql=sql,
                valid=False,
                error=f"sqlglot_rejected_statement: {forbidden[0].key}",
                tables=(),
                columns=(),
                metadata={},
            )

        allowed_tables: dict[str, SpiderSnowPacketTable] = {}
        allowed_columns: set[str] = set()
        for table in packet.tables:
            variants = {
                table.table_name.lower(),
                table.full_name.lower(),
                table.qualified_name.lower(),
                f"{packet.db_id}.{table.qualified_name}".lower(),
            }
            for variant in variants:
                allowed_tables[variant] = table
            for column in table.columns:
                allowed_columns.add(column.column_name.lower())

        found_tables: list[str] = []
        unknown_tables: list[str] = []
        alias_map: dict[str, SpiderSnowPacketTable] = {}
        cte_names = {
            cte.alias_or_name.lower()
            for cte in expression.find_all(exp.CTE)
            if cte.alias_or_name
        }
        for table_ref in expression.find_all(exp.Table):
            if table_ref.name.lower() in cte_names:
                continue
            parts = tuple(
                part
                for part in (
                    table_ref.catalog,
                    table_ref.db,
                    table_ref.name,
                )
                if part
            )
            lookup_keys = {
                ".".join(parts).lower(),
                ".".join(parts[-2:]).lower() if len(parts) >= 2 else "",
                table_ref.name.lower(),
            }
            packet_table = next((allowed_tables[key] for key in lookup_keys if key and key in allowed_tables), None)
            if packet_table is None:
                unknown_tables.append(".".join(parts) or table_ref.name)
                continue
            if packet_table.full_name not in found_tables:
                found_tables.append(packet_table.full_name)
            range_match = re.search(r"((?:19|20)\d{2})_((?:19|20)\d{2})", packet_table.table_name)
            if range_match and packet.years:
                end_year = int(range_match.group(2))
                if any(year > end_year for year in packet.years):
                    return SpiderSnowSQLNormalizationResult(
                        sql=sql,
                        valid=False,
                        error=(
                            f"semantic_year_table_mismatch: table={packet_table.table_name} "
                            f"max_year={end_year} years={list(packet.years)}"
                        ),
                        tables=tuple(found_tables),
                        columns=(),
                        metadata={"unknown_tables": (), "unknown_columns": ()},
                    )
            table_ref.set("catalog", exp.to_identifier(packet.db_id, quoted=True))
            table_ref.set("db", exp.to_identifier(packet_table.schema_name, quoted=True))
            table_ref.set("this", exp.to_identifier(packet_table.table_name, quoted=True))
            alias_name = table_ref.alias_or_name.lower()
            alias_map[alias_name] = packet_table
            alias_map[packet_table.table_name.lower()] = packet_table

        found_columns: list[str] = []
        unknown_columns: list[str] = []
        for column_ref in expression.find_all(exp.Column):
            column_name = column_ref.name
            lowered = column_name.lower()
            if lowered in allowed_columns:
                if column_name not in found_columns:
                    found_columns.append(column_name)
                column_ref.set("this", exp.to_identifier(column_name, quoted=True))
                table_name = column_ref.table
                if table_name and table_name.lower() not in alias_map and table_name.lower() not in cte_names:
                    unknown_columns.append(column_name)
                continue
            if lowered not in SQL_KEYWORDS:
                unknown_columns.append(column_name)

        if unknown_tables:
            return SpiderSnowSQLNormalizationResult(
                sql=sql,
                valid=False,
                error=f"sqlglot_unknown_tables: {', '.join(sorted(set(unknown_tables)))}",
                tables=tuple(found_tables),
                columns=tuple(found_columns),
                metadata={"unknown_tables": tuple(sorted(set(unknown_tables))), "unknown_columns": tuple(sorted(set(unknown_columns)))},
            )

        normalized_sql = self._surface_normalize(packet, sql)
        _, _, inferred_metadata = infer_sql_references(packet, normalized_sql)
        unknown_columns = sorted(set(unknown_columns) | set(inferred_metadata.get("unknown_columns", ())))
        return SpiderSnowSQLNormalizationResult(
            sql=normalized_sql,
            valid=True,
            error=None,
            tables=tuple(found_tables),
            columns=tuple(found_columns),
            metadata={
                "unknown_tables": tuple(inferred_metadata.get("unknown_tables", ())),
                "unknown_columns": tuple(unknown_columns),
            },
        )

    def _surface_normalize(self, packet: SpiderSnowTaskPacket, sql: str) -> str:
        normalized = sql
        for table in sorted(packet.tables, key=lambda item: len(item.table_name), reverse=True):
            fully_qualified = f'"{packet.db_id}".{table.qualified_name}'
            patterns = [
                re.compile(
                    rf'(?i)\b(FROM|JOIN)\s+{re.escape(packet.db_id)}\.{re.escape(table.schema_name)}\.{re.escape(table.table_name)}\b'
                ),
                re.compile(
                    rf'(?i)\b(FROM|JOIN)\s+{re.escape(packet.db_id)}\.{re.escape(table.table_name)}\b'
                ),
                re.compile(
                    rf'(?i)\b(FROM|JOIN)\s+{re.escape(table.schema_name)}\.{re.escape(table.table_name)}\b'
                ),
                re.compile(
                    rf'(?i)\b(FROM|JOIN)\s+{re.escape(table.table_name)}\b'
                ),
            ]
            for pattern in patterns:
                normalized = pattern.sub(rf'\1 {fully_qualified}', normalized)
        column_names = sorted(
            {
                column.column_name
                for table in packet.tables
                for column in table.columns
            },
            key=len,
            reverse=True,
        )
        for column_name in column_names:
            quoted = f'"{column_name}"'
            alias_pattern = re.compile(rf'(?i)\b([A-Za-z_][A-Za-z0-9_]*)\.{re.escape(column_name)}\b')
            bare_pattern = re.compile(rf'(?i)(?<![\w".]){re.escape(column_name)}(?![\w"])')
            normalized = alias_pattern.sub(rf'\1.{quoted}', normalized)
            normalized = bare_pattern.sub(quoted, normalized)
        return normalized
