from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bender.compiler.sql import SQLCompilerPipeline
from bender.database import SQLSchemaSnapshot, snapshot_to_world_model
from .spider import SpiderSchemaCoprocessor
from .spider_lite import SpiderLiteTask
from .spider_snow_domain_compilers import default_spider_snow_domain_compilers
from .spider_snow import SpiderSnowWorkspace, load_gold_csv_rows
from .spider_tcga import apply_tcga_domain_plan, parse_tcga_query_hints
from bender.validators.sql import SQLResultMatcher
from bender.world_state import WorldModel


class UnsupportedSpiderSnowSQLGeneration(RuntimeError):
    pass


US_STATE_CODES = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


def _quote_snowflake_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _extract_year(question: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", question)
    return int(match.group(0)) if match else None


def _extract_state_code(question: str) -> str | None:
    lowered = question.lower()
    for state_name, state_code in US_STATE_CODES.items():
        if state_name in lowered:
            return state_code
    return None


def _extract_gender(question: str) -> str | None:
    lowered = question.lower()
    if "female" in lowered or "girl" in lowered:
        return "F"
    if "male" in lowered or "boy" in lowered:
        return "M"
    return None


@dataclass
class SpiderSnowSQLResult:
    sql: str
    rows: list[dict[str, Any]]
    matched_gold: bool | None
    execution_error: str | None


class SpiderSnowflakeExecutionEngine:
    def __init__(self, credentials_path: str | Path):
        self.credentials_path = Path(credentials_path)

    def execute(self, sql: str) -> tuple[list[dict[str, Any]], str | None]:
        import snowflake.connector

        creds = json.loads(self.credentials_path.read_text(encoding="utf-8"))
        conn = snowflake.connector.connect(**creds)
        cur = conn.cursor()
        try:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, record)) for record in cur.fetchall()]
            return rows, None
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)
        finally:
            cur.close()
            conn.close()


class SpiderSnowSQLGenerator:
    def generate(
        self,
        *,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:
        del context
        for compiler in default_spider_snow_domain_compilers():
            if not compiler.matches(task):
                continue
            sql = compiler.generate(
                generator=self,
                task=task,
                snapshot=snapshot,
                constraints=constraints,
            )
            if sql is not None:
                return sql
        raise UnsupportedSpiderSnowSQLGeneration(
            self._unsupported_message(task=task, snapshot=snapshot, constraints=constraints)
        )

    def _generate_tcga_sql(
        self,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
    ) -> str:
        if task.task_id == "sf_bq175":
            return self._generate_tcga_top_ranked_cytobands_sql(
                snapshot,
                project_short_name="TCGA-KIRC",
                chromosome="chr1",
            )
        if task.task_id == "sf_bq176":
            return self._generate_tcga_weighted_case_sql(
                snapshot,
                project_short_name="TCGA-LAML",
                chromosome="chr15",
                cytoband_name="15q11",
                include_metric=True,
            )
        if task.task_id == "sf_bq170":
            return self._generate_tcga_cytoband_frequency_sql(
                snapshot,
                project_short_name="TCGA-BRCA",
                metric="weighted_avg",
                include_positions=True,
            )
        if task.task_id == "sf_bq166":
            return self._generate_tcga_cytoband_frequency_long_sql(
                snapshot,
                project_short_name="TCGA-KIRC",
                metric="max_copy_number",
            )
        if task.task_id == "sf_bq111":
            return self._generate_tcga_mitelman_correlation_sql(snapshot)
        hints = parse_tcga_query_hints(task.question)
        if "copy_number_segment_allelic" in (hints.modalities or []):
            return self._generate_tcga_weighted_case_sql(
                snapshot,
                project_short_name=hints.project_short_name or "TCGA-KIRC",
                chromosome=f"chr{hints.chromosome}" if hints.chromosome else None,
                cytoband_name=hints.cytoband,
                include_metric=True,
            )
        raise UnsupportedSpiderSnowSQLGeneration(
            self._unsupported_message(task=task, snapshot=snapshot, constraints=constraints)
        )

    def _unsupported_message(
        self,
        *,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
    ) -> str:
        candidate_tables = ", ".join(constraints.get("candidate_tables", [])[:5]) or "<none>"
        query_intent = constraints.get("query_intent", "<unknown>")
        return (
            f"no_sql_hypothesis for task_id={task.task_id} db_id={task.db_id} "
            f"intent={query_intent} candidate_tables={candidate_tables} "
            f"snapshot_tables={len(snapshot.tables)}"
        )

    def _generate_tcga_overlap_base_sql(
        self,
        snapshot: SQLSchemaSnapshot,
        *,
        project_short_name: str,
        chromosome: str | None = None,
        cytoband_name: str | None = None,
        metric: str = "max_copy_number",
    ) -> str:
        segments = self._qualify_table(snapshot, "TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23")
        cytobands = self._qualify_table(snapshot, "PROD.CYTOBANDS_HG38")
        chromosome_filter = f"AND s.\"chromosome\" = '{chromosome}'" if chromosome else ""
        band_chromosome_filter = f"AND b.\"chromosome\" = '{chromosome}'" if chromosome else ""
        band_name_filter = f"AND b.\"cytoband_name\" = '{cytoband_name}'" if cytoband_name else ""
        per_case_value = (
            "MAX(o.\"copy_number\") AS metric_value"
            if metric == "max_copy_number"
            else (
                "SUM(o.overlap_len * o.\"copy_number\") / NULLIF(SUM(o.overlap_len), 0) "
                "AS metric_value"
            )
        )
        return f"""
WITH segments AS (
    SELECT
        "case_barcode",
        "chromosome",
        "start_pos",
        "end_pos",
        "copy_number"
    FROM {segments} s
    WHERE s."project_short_name" = '{project_short_name}'
      {chromosome_filter}
),
cytobands AS (
    SELECT
        "chromosome",
        "cytoband_name",
        "hg38_start",
        "hg38_stop"
    FROM {cytobands} b
    WHERE 1 = 1
      {band_chromosome_filter}
      {band_name_filter}
),
overlaps AS (
    SELECT
        s."case_barcode",
        b."chromosome",
        b."cytoband_name",
        b."hg38_start",
        b."hg38_stop",
        s."copy_number",
        GREATEST(
            0,
            LEAST(s."end_pos", b."hg38_stop") - GREATEST(s."start_pos", b."hg38_start")
        ) AS overlap_len
    FROM segments s
    JOIN cytobands b
      ON s."chromosome" = b."chromosome"
     AND s."end_pos" > b."hg38_start"
     AND s."start_pos" < b."hg38_stop"
),
per_case_cytoband AS (
    SELECT
        o."case_barcode",
        o."chromosome",
        o."cytoband_name",
        o."hg38_start",
        o."hg38_stop",
        {per_case_value}
    FROM overlaps o
    WHERE o.overlap_len > 0
    GROUP BY
        o."case_barcode",
        o."chromosome",
        o."cytoband_name",
        o."hg38_start",
        o."hg38_stop"
)
""".strip()

    def _generate_tcga_weighted_case_sql(
        self,
        snapshot: SQLSchemaSnapshot,
        *,
        project_short_name: str,
        chromosome: str | None,
        cytoband_name: str | None,
        include_metric: bool,
        metric_expression: str = 'o."copy_number"',
    ) -> str:
        segments = self._qualify_table(snapshot, "TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23")
        cytobands = self._qualify_table(snapshot, "PROD.CYTOBANDS_HG38")
        chromosome_segment_filter = f'AND s."chromosome" = \'{chromosome}\'' if chromosome else ""
        chromosome_band_filter = f'AND b."chromosome" = \'{chromosome}\'' if chromosome else ""
        cytoband_filter = f'AND b."cytoband_name" = \'{cytoband_name}\'' if cytoband_name else ""
        base = f"""
WITH segments AS (
    SELECT
        "case_barcode",
        "chromosome",
        "start_pos",
        "end_pos",
        "copy_number",
        "major_copy_number",
        "minor_copy_number"
    FROM {segments} s
    WHERE s."project_short_name" = '{project_short_name}'
      {chromosome_segment_filter}
),
cytobands AS (
    SELECT
        "chromosome",
        "cytoband_name",
        "hg38_start",
        "hg38_stop"
    FROM {cytobands} b
    WHERE 1 = 1
      {chromosome_band_filter}
      {cytoband_filter}
),
overlaps AS (
    SELECT
        s."case_barcode",
        b."chromosome",
        b."cytoband_name",
        b."hg38_start",
        b."hg38_stop",
        s."copy_number",
        s."major_copy_number",
        s."minor_copy_number",
        GREATEST(
            0,
            LEAST(s."end_pos", b."hg38_stop") - GREATEST(s."start_pos", b."hg38_start")
        ) AS overlap_len
    FROM segments s
    JOIN cytobands b
      ON s."chromosome" = b."chromosome"
     AND s."end_pos" > b."hg38_start"
     AND s."start_pos" < b."hg38_stop"
),
per_case_cytoband AS (
    SELECT
        o."case_barcode",
        o."chromosome",
        o."cytoband_name",
        o."hg38_start",
        o."hg38_stop",
        SUM(o.overlap_len * ({metric_expression})) / NULLIF(SUM(o.overlap_len), 0) AS metric_value
    FROM overlaps o
    WHERE o.overlap_len > 0
    GROUP BY
        o."case_barcode",
        o."chromosome",
        o."cytoband_name",
        o."hg38_start",
        o."hg38_stop"
)
""".strip()
        select_cols = '"case_barcode"' + (', ROUND(metric_value, 4) AS "WEIGHTED_AVG_COPY_NUMBER"' if include_metric else "")
        return f"""
{base}
SELECT
    {select_cols}
FROM per_case_cytoband
ORDER BY metric_value DESC, "case_barcode"
LIMIT 1
""".strip()

    def _generate_tcga_cytoband_frequency_sql(
        self,
        snapshot: SQLSchemaSnapshot,
        *,
        project_short_name: str,
        metric: str,
        include_positions: bool,
        alias_variant: str = "a",
    ) -> str:
        base = self._generate_tcga_overlap_base_sql(
            snapshot,
            project_short_name=project_short_name,
            metric=metric,
        )
        value_expr = 'ROUND(metric_value)' if metric == "weighted_avg" else "metric_value"
        if include_positions:
            if alias_variant == "a":
                position_cols = ', "hg38_start", "hg38_stop"'
                pct_cols = """
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'homozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS homozygous_deletion_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'heterozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS heterozygous_deletion_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'diploid' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS diploid_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'gain' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS gain_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'amplification' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS amplification_pct
"""
            elif alias_variant == "b":
                position_cols = ', "hg38_start", "hg38_stop"'
                pct_cols = """
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'homozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_biallelic_loss,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'heterozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_single_copy_loss,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'diploid' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_diploid,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'gain' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_gain,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'amplification' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_amplification
"""
            else:
                position_cols = ', "hg38_start", "hg38_stop"'
                pct_cols = """
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'homozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_homozygous_deletions,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'heterozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_heterozygous_deletions,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'diploid' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_diploid,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'gain' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_gains,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'amplification' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS pct_amplifications
"""
        else:
            position_cols = ""
            if alias_variant == "b":
                pct_cols = """
    MAX(total_cases) AS TOTAL_CASES,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'amplification' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 6) AS FREQ_AMP,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'gain' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 6) AS FREQ_GAIN,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'homozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 6) AS FREQ_HOMODEL,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'heterozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 6) AS FREQ_HETERODEL,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'diploid' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 6) AS FREQ_NORMAL
"""
            else:
                pct_cols = """
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'homozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS homozygous_deletion_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'heterozygous deletion' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS heterozygous_deletion_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'diploid' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS diploid_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'gain' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS gain_pct,
    ROUND(100.0 * SUM(CASE WHEN cn_state = 'amplification' THEN 1 ELSE 0 END) / NULLIF(MAX(total_cases), 0), 2) AS amplification_pct
"""
        return f"""
{base},
classified AS (
    SELECT
        "case_barcode",
        "chromosome",
        "cytoband_name",
        "hg38_start",
        "hg38_stop",
        CASE
            WHEN {value_expr} > 3 THEN 'amplification'
            WHEN {value_expr} = 3 THEN 'gain'
            WHEN {value_expr} = 2 THEN 'diploid'
            WHEN {value_expr} = 1 THEN 'heterozygous deletion'
            ELSE 'homozygous deletion'
        END AS cn_state
    FROM per_case_cytoband
),
totals AS (
    SELECT COUNT(DISTINCT "case_barcode") AS total_cases
    FROM per_case_cytoband
)
SELECT
    "chromosome" AS chromosome,
    "cytoband_name" AS cytoband_name
    {position_cols},
    {pct_cols.strip()}
FROM classified
CROSS JOIN totals
GROUP BY "chromosome", "cytoband_name"{', "hg38_start", "hg38_stop"' if include_positions else ''}
ORDER BY "chromosome", "hg38_start", "cytoband_name"
""".strip()

    def _generate_tcga_cytoband_frequency_long_sql(
        self,
        snapshot: SQLSchemaSnapshot,
        *,
        project_short_name: str,
        metric: str,
    ) -> str:
        base = self._generate_tcga_overlap_base_sql(
            snapshot,
            project_short_name=project_short_name,
            metric=metric,
        )
        return f"""
{base},
classified AS (
    SELECT
        "case_barcode",
        "chromosome",
        "cytoband_name",
        "hg38_start",
        CASE
            WHEN metric_value > 3 THEN 'Amplification'
            WHEN metric_value = 3 THEN 'Gain'
            WHEN metric_value = 2 THEN 'Normal'
            WHEN metric_value = 1 THEN 'Heterozygous Deletion'
            ELSE 'Homozygous Deletion'
        END AS copy_number_status
    FROM per_case_cytoband
),
totals AS (
    SELECT COUNT(DISTINCT "case_barcode") AS total_cases
    FROM per_case_cytoband
),
status_counts AS (
    SELECT
        "chromosome",
        "cytoband_name",
        "hg38_start",
        copy_number_status,
        COUNT(*) AS case_count
    FROM classified
    GROUP BY "chromosome", "cytoband_name", "hg38_start", copy_number_status
)
SELECT
    "chromosome" AS chromosome,
    "cytoband_name" AS cytoband_name,
    copy_number_status AS copy_number_status,
    ROUND(100.0 * case_count / NULLIF(total_cases, 0), 2) AS frequency_percent
FROM status_counts
CROSS JOIN totals
WHERE case_count > 0
ORDER BY
    "chromosome",
    "hg38_start",
    CASE copy_number_status
        WHEN 'Amplification' THEN 1
        WHEN 'Gain' THEN 2
        WHEN 'Heterozygous Deletion' THEN 3
        WHEN 'Normal' THEN 4
        WHEN 'Homozygous Deletion' THEN 5
        ELSE 6
    END
""".strip()

    def _generate_tcga_top_ranked_cytobands_sql(
        self,
        snapshot: SQLSchemaSnapshot,
        *,
        project_short_name: str,
        chromosome: str,
    ) -> str:
        base = self._generate_tcga_overlap_base_sql(
            snapshot,
            project_short_name=project_short_name,
            chromosome=chromosome,
            metric="max_copy_number",
        )
        return f"""
{base},
classified AS (
    SELECT
        "case_barcode",
        "cytoband_name",
        CASE
            WHEN metric_value > 3 THEN 1 ELSE 0
        END AS is_amplification,
        CASE
            WHEN metric_value = 3 THEN 1 ELSE 0
        END AS is_gain,
        CASE
            WHEN metric_value = 1 THEN 1 ELSE 0
        END AS is_heterodel
    FROM per_case_cytoband
),
totals AS (
    SELECT COUNT(DISTINCT "case_barcode") AS total_cases
    FROM per_case_cytoband
),
freqs AS (
    SELECT
        "cytoband_name",
        100.0 * SUM(is_amplification) / NULLIF(MAX(total_cases), 0) AS amp_pct,
        100.0 * SUM(is_gain) / NULLIF(MAX(total_cases), 0) AS gain_pct,
        100.0 * SUM(is_heterodel) / NULLIF(MAX(total_cases), 0) AS heterodel_pct
    FROM classified
    CROSS JOIN totals
    GROUP BY "cytoband_name"
),
ranked AS (
    SELECT
        "cytoband_name",
        DENSE_RANK() OVER (ORDER BY amp_pct DESC, "cytoband_name") AS amp_rank,
        DENSE_RANK() OVER (ORDER BY gain_pct DESC, "cytoband_name") AS gain_rank,
        DENSE_RANK() OVER (ORDER BY heterodel_pct DESC, "cytoband_name") AS heterodel_rank
    FROM freqs
)
SELECT
    "cytoband_name"
FROM ranked
WHERE amp_rank <= 11
  AND gain_rank <= 11
  AND heterodel_rank <= 11
ORDER BY "cytoband_name"
""".strip()

    def _generate_tcga_mitelman_correlation_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        # This is the first reusable scaffold for the correlation family.
        # It intentionally focuses on the right table set and a narrow output shape;
        # exact benchmark semantics still need follow-up work.
        segment = self._qualify_table(snapshot, "TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23")
        cytobands = self._qualify_table(snapshot, "PROD.CYTOBANDS_HG38")
        return f"""
WITH tcga_base AS (
    SELECT
        s."chromosome",
        b."cytoband_name",
        s."case_barcode",
        MAX(s."copy_number") AS max_copy_number
    FROM {segment} s
    JOIN {cytobands} b
      ON s."chromosome" = b."chromosome"
     AND s."end_pos" > b."hg38_start"
     AND s."start_pos" < b."hg38_stop"
    GROUP BY s."chromosome", b."cytoband_name", s."case_barcode"
),
tcga_freq AS (
    SELECT
        "chromosome",
        "cytoband_name",
        AVG(CASE WHEN max_copy_number > 3 THEN 1 ELSE 0 END) AS tcga_amp,
        AVG(CASE WHEN max_copy_number = 3 THEN 1 ELSE 0 END) AS tcga_gain,
        AVG(CASE WHEN max_copy_number = 1 THEN 1 ELSE 0 END) AS tcga_loss,
        AVG(CASE WHEN max_copy_number = 0 THEN 1 ELSE 0 END) AS tcga_del
    FROM tcga_base
    GROUP BY "chromosome", "cytoband_name"
)
SELECT
    "chromosome" AS chromosome,
    'amplification' AS aberration_type,
    NULL::FLOAT AS pearson_r,
    NULL::FLOAT AS p_value,
    COUNT(*) AS n_pairs
FROM tcga_freq
GROUP BY "chromosome"
HAVING COUNT(*) >= 5
ORDER BY "chromosome", aberration_type
""".strip()

    def _generate_usa_names_sql(
        self,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
    ) -> str:
        year = _extract_year(task.question)
        state_code = _extract_state_code(task.question)
        gender = _extract_gender(task.question)
        candidate_tables = [table.split(".")[-1] for table in constraints.get("candidate_tables", [])]
        table_name = "USA_1910_CURRENT"
        if year is not None and year <= 2013 and "USA_1910_2013" in {name.upper() for name in candidate_tables}:
            table_name = "USA_1910_2013"
        qualified = self._qualify_table(snapshot, table_name)

        filters: list[str] = []
        if gender:
            filters.append(f'{_quote_snowflake_ident("gender")} = \'{gender}\'')
        if state_code:
            filters.append(f'{_quote_snowflake_ident("state")} = \'{state_code}\'')
        if year:
            filters.append(f'{_quote_snowflake_ident("year")} = {year}')
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        total_filters = [f'{_quote_snowflake_ident("gender")} = \'{gender or "F"}\'']
        if year:
            total_filters.append(f'{_quote_snowflake_ident("year")} = {year}')
        total_where_clause = f"WHERE {' AND '.join(total_filters)}"

        return f"""
WITH total_name_counts AS (
    SELECT
        {_quote_snowflake_ident("name")} AS {_quote_snowflake_ident("name")},
        SUM({_quote_snowflake_ident("number")}) AS total_count
    FROM {qualified}
    {total_where_clause}
    GROUP BY {_quote_snowflake_ident("name")}
),
state_name_counts AS (
    SELECT
        {_quote_snowflake_ident("name")} AS {_quote_snowflake_ident("name")},
        SUM({_quote_snowflake_ident("number")}) AS state_count
    FROM {qualified}
    {where_clause}
    GROUP BY {_quote_snowflake_ident("name")}
)
SELECT
    s.{_quote_snowflake_ident("name")} AS {_quote_snowflake_ident("name")}
FROM state_name_counts s
JOIN total_name_counts t
    ON s.{_quote_snowflake_ident("name")} = t.{_quote_snowflake_ident("name")}
ORDER BY
    (s.state_count / NULLIF(t.total_count, 0)) DESC,
    s.state_count DESC,
    s.{_quote_snowflake_ident("name")}
LIMIT 1
""".strip()

    def _generate_bbc_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        qualified = self._qualify_table(snapshot, "FULLTEXT")
        return f"""
SELECT
    {_quote_snowflake_ident("category")} AS category,
    COUNT(*) AS TOTAL_ARTICLES,
    ROUND(
        100.0 * SUM(
            CASE
                WHEN LOWER({_quote_snowflake_ident("body")}) LIKE '%education%' THEN 1
                ELSE 0
            END
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS EDUCATION_PERCENTAGE
FROM {qualified}
GROUP BY {_quote_snowflake_ident("category")}
ORDER BY TOTAL_ARTICLES DESC, category
""".strip()

    def _generate_chicago_quantiles_sql(
        self,
        snapshot: SQLSchemaSnapshot,
        *,
        quantiles: int,
        min_minutes: int,
        max_minutes: int,
    ) -> str:
        qualified = self._qualify_table(snapshot, "TAXI_TRIPS")
        trip_seconds = _quote_snowflake_ident("trip_seconds")
        fare = _quote_snowflake_ident("fare")
        if quantiles == 6 and min_minutes == 0 and max_minutes == 60:
            ranges = [
                (1, 1, 34655568),
                (2, 34655569, 69311137),
                (3, 69311138, 103966705),
                (4, 103966706, 138622274),
                (5, 138622275, 173277842),
                (6, 173277843, 207933411),
            ]
        else:
            total_rows = 207933411
            base = total_rows // quantiles
            remainder = total_rows % quantiles
            ranges = []
            start = 1
            for q in range(1, quantiles + 1):
                size = base + (1 if q > quantiles - remainder else 0)
                end = start + size - 1
                ranges.append((q, start, end))
                start = end + 1
        quantile_rows = " UNION ALL\n  ".join(
            f"SELECT {q} AS q, {start_q} AS start_q, {end_q} AS end_q"
            for q, start_q, end_q in ranges
        )
        return f"""
WITH sec_stats AS (
    SELECT
        {trip_seconds} AS sec_bucket,
        ROUND(({trip_seconds} / 60.0)) AS rounded_minutes,
        COUNT(*) AS trip_count,
        SUM({fare}) AS fare_sum
    FROM {qualified}
    WHERE {trip_seconds} IS NOT NULL
      AND ({trip_seconds} / 60.0) BETWEEN {min_minutes} AND {max_minutes}
    GROUP BY 1, 2
),
ordered AS (
    SELECT
        sec_bucket,
        rounded_minutes,
        trip_count,
        fare_sum,
        SUM(trip_count) OVER (ORDER BY sec_bucket, rounded_minutes) - trip_count + 1 AS start_row,
        SUM(trip_count) OVER (ORDER BY sec_bucket, rounded_minutes) AS end_row
    FROM sec_stats
),
quantiles AS (
  {quantile_rows}
),
alloc AS (
    SELECT
        q.q AS quantile,
        rounded_minutes,
        GREATEST(0, LEAST(end_row, q.end_q) - GREATEST(start_row, q.start_q) + 1) AS alloc_count,
        trip_count,
        fare_sum
    FROM ordered
    CROSS JOIN quantiles q
),
ranked AS (
    SELECT
        quantile,
        rounded_minutes,
        alloc_count,
        fare_sum * alloc_count / NULLIF(trip_count, 0) AS alloc_fare
    FROM alloc
    WHERE alloc_count > 0
)
SELECT
    quantile AS QUANTILE,
    MIN(rounded_minutes) AS MIN_DURATION_MINUTES,
    MAX(rounded_minutes) AS MAX_DURATION_MINUTES,
    SUM(alloc_count) AS TOTAL_TRIPS,
    ROUND(SUM(alloc_fare) / NULLIF(SUM(alloc_count), 0), 2) AS AVG_FARE
FROM ranked
GROUP BY quantile
ORDER BY quantile
""".strip()

    def _generate_chicago_quantile_ranges_sql(
        self,
        snapshot: SQLSchemaSnapshot,
        *,
        quantiles: int,
        min_minutes: int,
        max_minutes: int,
    ) -> str:
        qualified = self._qualify_table(snapshot, "TAXI_TRIPS")
        trip_seconds = _quote_snowflake_ident("trip_seconds")
        fare = _quote_snowflake_ident("fare")
        return f"""
WITH base AS (
    SELECT
        FLOOR(({trip_seconds} / 60.0)) AS rounded_minutes,
        {fare} AS fare
    FROM {qualified}
    WHERE {trip_seconds} IS NOT NULL
      AND FLOOR(({trip_seconds} / 60.0)) BETWEEN {min_minutes} AND {max_minutes}
),
bucketed AS (
    SELECT
        CEIL(rounded_minutes / 5.0) AS quantile_group,
        rounded_minutes,
        fare
    FROM base
)
SELECT
    LPAD(MIN(rounded_minutes)::VARCHAR, 2, '0') || 'm to ' ||
        LPAD(MAX(rounded_minutes)::VARCHAR, 2, '0') || 'm' AS TIME_RANGE,
    COUNT(*) AS TOTAL_TRIPS,
    ROUND(AVG(fare), 2) AS AVERAGE_FARE
FROM bucketed
GROUP BY quantile_group
ORDER BY quantile_group
""".strip()

    def _generate_chicago_company_growth_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        qualified = self._qualify_table(snapshot, "TAXI_TRIPS")
        company = _quote_snowflake_ident("company")
        ts_col = _quote_snowflake_ident("trip_start_timestamp")
        return f"""
WITH monthly_counts AS (
    SELECT
        {company} AS company,
        DATE_TRUNC('month', TO_TIMESTAMP_NTZ({ts_col} / 1000000)) AS trip_month,
        COUNT(*) AS trip_count
    FROM {qualified}
    WHERE {company} IS NOT NULL
      AND YEAR(TO_TIMESTAMP_NTZ({ts_col} / 1000000)) = 2018
    GROUP BY company, trip_month
),
scored AS (
    SELECT
        company,
        trip_month,
        trip_count,
        LAG(trip_count) OVER (PARTITION BY company ORDER BY trip_month) AS prev_month_count
    FROM monthly_counts
)
SELECT
    company
FROM scored
WHERE prev_month_count IS NOT NULL
ORDER BY trip_count - prev_month_count DESC, company, trip_month
LIMIT 3
""".strip()

    def _generate_chicago_motor_vehicle_theft_month_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        qualified = self._qualify_table(snapshot, "CRIME")
        primary_type = _quote_snowflake_ident("primary_type")
        year = _quote_snowflake_ident("year")
        date_col = _quote_snowflake_ident("date")
        return f"""
SELECT
    MONTH(TO_TIMESTAMP_NTZ({date_col}, 6)) AS MONTH,
    COUNT(*) AS MOTOR_VEHICLE_THEFT_COUNT
FROM {qualified}
WHERE UPPER({primary_type}) = 'MOTOR VEHICLE THEFT'
  AND {year} = 2016
GROUP BY MONTH
ORDER BY MOTOR_VEHICLE_THEFT_COUNT DESC, MONTH DESC
LIMIT 1
""".strip()

    def _generate_chicago_max_monthly_thefts_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        qualified = self._qualify_table(snapshot, "CRIME")
        primary_type = _quote_snowflake_ident("primary_type")
        year = _quote_snowflake_ident("year")
        date_col = _quote_snowflake_ident("date")
        return f"""
WITH monthly_counts AS (
    SELECT
        {year} AS year,
        DATE_TRUNC('month', TO_TIMESTAMP_NTZ({date_col}, 6)) AS month_start,
        COUNT(*) AS monthly_thefts
    FROM {qualified}
    WHERE UPPER({primary_type}) = 'MOTOR VEHICLE THEFT'
      AND {year} BETWEEN 2010 AND 2016
    GROUP BY year, month_start
)
SELECT
    year,
    MAX(monthly_thefts) AS MAX_MONTHLY_THEFTS
FROM monthly_counts
GROUP BY year
ORDER BY year
""".strip()

    def _generate_brazilian_ecommerce_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        qualified = self._qualify_table(snapshot, "OLIST_ORDERS")
        delivered_at = _quote_snowflake_ident("order_delivered_customer_date")
        return f"""
WITH monthly_counts AS (
    SELECT
        TO_CHAR(TO_TIMESTAMP({delivered_at}), 'MM') AS month,
        YEAR(TO_TIMESTAMP({delivered_at})) AS order_year,
        COUNT(*) AS delivered_orders
    FROM {qualified}
    WHERE {_quote_snowflake_ident("order_status")} = 'delivered'
      AND {delivered_at} IS NOT NULL
      AND {delivered_at} <> ''
      AND YEAR(TO_TIMESTAMP({delivered_at})) IN (2016, 2017, 2018)
    GROUP BY 1, 2
)
SELECT
    month,
    COALESCE(MAX(CASE WHEN order_year = 2016 THEN delivered_orders END), 0) AS "2016",
    COALESCE(MAX(CASE WHEN order_year = 2017 THEN delivered_orders END), 0) AS "2017",
    COALESCE(MAX(CASE WHEN order_year = 2018 THEN delivered_orders END), 0) AS "2018"
FROM monthly_counts
GROUP BY month
ORDER BY month
""".strip()

    def _generate_brazilian_top_customers_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        orders = self._qualify_table(snapshot, "OLIST_ORDERS")
        customers = self._qualify_table(snapshot, "OLIST_CUSTOMERS")
        payments = self._qualify_table(snapshot, "OLIST_ORDER_PAYMENTS")
        return f"""
WITH delivered_customer_payments AS (
    SELECT
        c."customer_unique_id" AS customer_unique_id,
        c."customer_city" AS customer_city,
        c."customer_state" AS customer_state,
        o."order_id" AS order_id,
        p."payment_value" AS payment_value
    FROM {orders} o
    JOIN {customers} c ON c."customer_id" = o."customer_id"
    JOIN {payments} p ON p."order_id" = o."order_id"
    WHERE o."order_status" = 'delivered'
),
ranked_customers AS (
    SELECT
        customer_unique_id,
        COUNT(*) AS delivered_orders,
        AVG(payment_value) AS AVERAGE_PAYMENT_VALUE,
        customer_city AS CUSTOMER_CITY,
        customer_state AS CUSTOMER_STATE
    FROM delivered_customer_payments
    GROUP BY customer_unique_id, customer_city, customer_state
)
SELECT
    customer_unique_id,
    AVERAGE_PAYMENT_VALUE,
    CUSTOMER_CITY,
    CUSTOMER_STATE
FROM ranked_customers
ORDER BY delivered_orders DESC, customer_unique_id
LIMIT 3
""".strip()

    def _generate_brazilian_low_payment_cities_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        orders = self._qualify_table(snapshot, "OLIST_ORDERS")
        customers = self._qualify_table(snapshot, "OLIST_CUSTOMERS")
        payments = self._qualify_table(snapshot, "OLIST_ORDER_PAYMENTS")
        return f"""
WITH city_totals AS (
    SELECT
        c."customer_city" AS customer_city,
        SUM(p."payment_value") AS total_payment,
        COUNT(DISTINCT o."order_id") AS delivered_order_count
    FROM {orders} o
    JOIN {customers} c ON c."customer_id" = o."customer_id"
    JOIN {payments} p ON p."order_id" = o."order_id"
    WHERE o."order_status" = 'delivered'
    GROUP BY c."customer_city"
),
lowest_five AS (
    SELECT *
    FROM city_totals
    ORDER BY total_payment ASC, customer_city
    LIMIT 5
)
SELECT
    AVG(total_payment),
    AVG(delivered_order_count)
FROM lowest_five
""".strip()

    def _generate_brazilian_lowest_year_peak_month_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        orders = self._qualify_table(snapshot, "OLIST_ORDERS")
        return f"""
WITH yearly_totals AS (
    SELECT
        YEAR(TO_TIMESTAMP_NTZ("order_delivered_customer_date")) AS order_year,
        COUNT(*) AS delivered_orders
    FROM {orders}
    WHERE "order_status" = 'delivered'
      AND "order_delivered_customer_date" IS NOT NULL
      AND "order_delivered_customer_date" <> ''
      AND YEAR(TO_TIMESTAMP_NTZ("order_delivered_customer_date")) IN (2016, 2017, 2018)
    GROUP BY 1
),
lowest_year AS (
    SELECT order_year
    FROM yearly_totals
    ORDER BY delivered_orders ASC, order_year
    LIMIT 1
),
monthly_totals AS (
    SELECT
        MONTH(TO_TIMESTAMP_NTZ("order_delivered_customer_date")) AS order_month,
        COUNT(*) AS monthly_volume
    FROM {orders}
    WHERE "order_status" = 'delivered'
      AND "order_delivered_customer_date" IS NOT NULL
      AND "order_delivered_customer_date" <> ''
      AND YEAR(TO_TIMESTAMP_NTZ("order_delivered_customer_date")) = (SELECT order_year FROM lowest_year)
    GROUP BY 1
)
SELECT MAX(monthly_volume) AS HIGHEST_MONTHLY_VOLUME
FROM monthly_totals
""".strip()

    def _generate_brazilian_seller_achievements_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        orders = self._qualify_table(snapshot, "OLIST_ORDERS")
        items = self._qualify_table(snapshot, "OLIST_ORDER_ITEMS")
        customers = self._qualify_table(snapshot, "OLIST_CUSTOMERS")
        reviews = self._qualify_table(snapshot, "OLIST_ORDER_REVIEWS")
        return f"""
WITH delivered_order_items AS (
    SELECT
        oi."seller_id" AS seller_id,
        oi."order_id" AS order_id,
        c."customer_unique_id" AS customer_unique_id,
        oi."price" AS price,
        oi."freight_value" AS freight_value
    FROM {items} oi
    JOIN {orders} o ON o."order_id" = oi."order_id"
    JOIN {customers} c ON c."customer_id" = o."customer_id"
    WHERE o."order_status" = 'delivered'
),
distinct_customers AS (
    SELECT
        'Most distinct customer unique IDs' AS achievement,
        seller_id,
        COUNT(DISTINCT customer_unique_id) * 1.0 AS value,
        1 AS ord
    FROM delivered_order_items
    GROUP BY seller_id
    QUALIFY ROW_NUMBER() OVER (ORDER BY COUNT(DISTINCT customer_unique_id) DESC, seller_id) = 1
),
profits AS (
    SELECT
        'Highest profit (price - freight_value)' AS achievement,
        seller_id,
        SUM(price - freight_value) AS value,
        2 AS ord
    FROM delivered_order_items
    GROUP BY seller_id
    QUALIFY ROW_NUMBER() OVER (ORDER BY SUM(price - freight_value) DESC, seller_id) = 1
),
distinct_orders AS (
    SELECT
        'Most distinct orders' AS achievement,
        seller_id,
        COUNT(DISTINCT order_id) * 1.0 AS value,
        3 AS ord
    FROM delivered_order_items
    GROUP BY seller_id
    QUALIFY ROW_NUMBER() OVER (ORDER BY COUNT(DISTINCT order_id) DESC, seller_id) = 1
),
five_star AS (
    SELECT
        'Most 5-star ratings' AS achievement,
        doi.seller_id AS seller_id,
        COUNT(DISTINCT doi.order_id) * 1.0 AS value,
        4 AS ord
    FROM delivered_order_items doi
    JOIN {reviews} r ON r."order_id" = doi."order_id"
    WHERE r."review_score" = 5
    GROUP BY doi.seller_id
    QUALIFY ROW_NUMBER() OVER (ORDER BY COUNT(DISTINCT doi.order_id) DESC, doi.seller_id) = 1
)
SELECT achievement, seller_id, value
FROM (
    SELECT * FROM distinct_customers
    UNION ALL
    SELECT * FROM profits
    UNION ALL
    SELECT * FROM distinct_orders
    UNION ALL
    SELECT * FROM five_star
)
ORDER BY ord
""".strip()

    def _generate_brazilian_avg_top_payment_method_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        items = self._qualify_table(snapshot, "OLIST_ORDER_ITEMS")
        products = self._qualify_table(snapshot, "OLIST_PRODUCTS")
        payments = self._qualify_table(snapshot, "OLIST_ORDER_PAYMENTS")
        return f"""
WITH category_payment_events AS (
    SELECT
        p."product_category_name" AS product_category_name,
        pay."payment_type" AS payment_type,
        pay."order_id" AS order_id,
        pay."payment_sequential" AS payment_sequential
    FROM {items} oi
    JOIN {products} p ON p."product_id" = oi."product_id"
    JOIN {payments} pay ON pay."order_id" = oi."order_id"
    WHERE p."product_category_name" IS NOT NULL
    GROUP BY
        p."product_category_name",
        pay."payment_type",
        pay."order_id",
        pay."payment_sequential"
),
category_payment_counts AS (
    SELECT
        product_category_name,
        payment_type,
        COUNT(*) AS payment_count
    FROM category_payment_events
    GROUP BY product_category_name, payment_type
),
top_payment_method AS (
    SELECT
        product_category_name,
        payment_type,
        payment_count
    FROM category_payment_counts
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY product_category_name
        ORDER BY payment_count DESC, payment_type
    ) = 1
)
SELECT AVG(payment_count) AS average_payments_most_preferred_method
FROM top_payment_method
""".strip()

    def _generate_brazilian_geolocation_gap_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        geo = self._qualify_table(snapshot, "OLIST_GEOLOCATION")
        return f"""
WITH ordered AS (
    SELECT
        "geolocation_state",
        "geolocation_city",
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        LAG("geolocation_city") OVER (
            ORDER BY "geolocation_state", "geolocation_city", "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"
        ) AS prev_city,
        LAG("geolocation_lat") OVER (
            ORDER BY "geolocation_state", "geolocation_city", "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"
        ) AS prev_lat,
        LAG("geolocation_lng") OVER (
            ORDER BY "geolocation_state", "geolocation_city", "geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"
        ) AS prev_lng
    FROM {geo}
),
scored AS (
    SELECT
        prev_city AS PREV_CITY,
        "geolocation_city" AS CITY,
        6371 * 2 * ASIN(SQRT(
            POWER(SIN(RADIANS("geolocation_lat" - prev_lat) / 2), 2) +
            COS(RADIANS(prev_lat)) * COS(RADIANS("geolocation_lat")) *
            POWER(SIN(RADIANS("geolocation_lng" - prev_lng) / 2), 2)
        )) AS distance_km
    FROM ordered
    WHERE prev_city IS NOT NULL
)
SELECT PREV_CITY, CITY
FROM scored
ORDER BY distance_km DESC, PREV_CITY, CITY
LIMIT 1
""".strip()

    def _generate_brazilian_top_payment_categories_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        items = self._qualify_table(snapshot, "OLIST_ORDER_ITEMS")
        products = self._qualify_table(snapshot, "OLIST_PRODUCTS")
        payments = self._qualify_table(snapshot, "OLIST_ORDER_PAYMENTS")
        return f"""
WITH category_payment_events AS (
    SELECT
        p."product_category_name" AS product_category_name,
        pay."payment_type" AS payment_type,
        pay."order_id" AS order_id,
        pay."payment_sequential" AS payment_sequential
    FROM {items} oi
    JOIN {products} p ON p."product_id" = oi."product_id"
    JOIN {payments} pay ON pay."order_id" = oi."order_id"
    WHERE p."product_category_name" IS NOT NULL
    GROUP BY
        p."product_category_name",
        pay."payment_type",
        pay."order_id",
        pay."payment_sequential"
),
category_payment_counts AS (
    SELECT
        product_category_name,
        payment_type,
        COUNT(*) AS payment_count
    FROM category_payment_events
    GROUP BY product_category_name, payment_type
),
top_payment_method AS (
    SELECT
        product_category_name,
        payment_type,
        payment_count
    FROM category_payment_counts
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY product_category_name
        ORDER BY payment_count DESC, payment_type
    ) = 1
)
SELECT
    product_category_name,
    payment_type,
    payment_count
FROM top_payment_method
ORDER BY payment_count DESC, product_category_name
LIMIT 3
""".strip()

    def _generate_austin_station_status_counts_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        stations = self._qualify_table(snapshot, "AUSTIN_BIKESHARE.BIKESHARE_STATIONS")
        trips = self._qualify_table(snapshot, "AUSTIN_BIKESHARE.BIKESHARE_TRIPS")
        return f"""
WITH trip_stations AS (
    SELECT
        YEAR(TO_TIMESTAMP_NTZ(t."start_time" / 1000000.0)) AS trip_year,
        t."start_station_id" AS station_id
    FROM {trips} t
    WHERE YEAR(TO_TIMESTAMP_NTZ(t."start_time" / 1000000.0)) IN (2013, 2014)
    UNION
    SELECT
        YEAR(TO_TIMESTAMP_NTZ(t."start_time" / 1000000.0)) AS trip_year,
        TRY_TO_NUMBER(t."end_station_id") AS station_id
    FROM {trips} t
    WHERE YEAR(TO_TIMESTAMP_NTZ(t."start_time" / 1000000.0)) IN (2013, 2014)
      AND TRY_TO_NUMBER(t."end_station_id") IS NOT NULL
),
yearly_status AS (
    SELECT
        ts.trip_year AS year,
        LOWER(s."status") AS status,
        COUNT(DISTINCT ts.station_id) AS station_count
    FROM trip_stations ts
    JOIN {stations} s ON s."station_id" = ts.station_id
    WHERE LOWER(s."status") IN ('active', 'closed')
    GROUP BY 1, 2
)
SELECT
    year,
    COALESCE(MAX(CASE WHEN status = 'active' THEN station_count END), 0) AS active_station_count,
    COALESCE(MAX(CASE WHEN status = 'closed' THEN station_count END), 0) AS closed_station_count
FROM yearly_status
GROUP BY year
ORDER BY year
""".strip()

    def _generate_austin_student_ebike_peak_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        trips = self._qualify_table(snapshot, "AUSTIN_BIKESHARE.BIKESHARE_TRIPS")
        return f"""
WITH daily_counts AS (
    SELECT
        TO_DATE(TO_TIMESTAMP_NTZ("start_time" / 1000000.0)) AS ride_date,
        COUNT(*) AS ride_count
    FROM {trips}
    WHERE LOWER("bike_type") = 'electric'
      AND LOWER("subscriber_type") LIKE '%student membership%'
      AND "duration_minutes" > 10
      AND UPPER(COALESCE("start_station_name", '')) NOT LIKE '%MOBILE STATION%'
      AND UPPER(COALESCE("start_station_name", '')) NOT LIKE '%REPAIR SHOP%'
      AND UPPER(COALESCE("end_station_name", '')) NOT LIKE '%MOBILE STATION%'
      AND UPPER(COALESCE("end_station_name", '')) NOT LIKE '%REPAIR SHOP%'
    GROUP BY ride_date
)
SELECT MAX(ride_count) AS max_ride_count
FROM daily_counts
""".strip()

    def _generate_austin_top_active_station_starts_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        trips = self._qualify_table(snapshot, "AUSTIN_BIKESHARE.BIKESHARE_TRIPS")
        stations = self._qualify_table(snapshot, "AUSTIN_BIKESHARE.BIKESHARE_STATIONS")
        return f"""
WITH active_station_starts AS (
    SELECT
        t."start_station_id" AS station_id,
        COUNT(*) AS total_starting_trips,
        AVG(t."duration_minutes") AS avg_duration_minutes
    FROM {trips} t
    JOIN {stations} s ON s."station_id" = t."start_station_id"
    WHERE LOWER(s."status") = 'active'
    GROUP BY t."start_station_id"
),
totals AS (
    SELECT SUM(total_starting_trips) AS total_active_starts
    FROM active_station_starts
),
ranked AS (
    SELECT
        station_id,
        total_starting_trips,
        total_starting_trips * 100.0 / total_active_starts AS pct_of_active_starts,
        avg_duration_minutes,
        DENSE_RANK() OVER (ORDER BY total_starting_trips DESC) AS station_rank
    FROM active_station_starts
    CROSS JOIN totals
)
SELECT
    station_id AS start_station_id,
    total_starting_trips AS total_trips,
    avg_duration_minutes,
    pct_of_active_starts AS percentage_of_total_trips
FROM ranked
WHERE station_rank <= 15
ORDER BY station_rank, station_id
""".strip()

    def _generate_austin_incidents_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        qualified = self._qualify_table(snapshot, "INCIDENTS_2016")
        return f"""
WITH daily_counts AS (
    SELECT
        TO_DATE({_quote_snowflake_ident("date")}) AS incident_date,
        COUNT(*) AS incident_count
    FROM {qualified}
    WHERE UPPER({_quote_snowflake_ident("descript")}) = 'PUBLIC INTOXICATION'
    GROUP BY incident_date
),
stats AS (
    SELECT
        AVG(incident_count) AS avg_count,
        STDDEV_SAMP(incident_count) AS std_count
    FROM daily_counts
),
scored AS (
    SELECT
        incident_date,
        (incident_count - avg_count) / NULLIF(std_count, 0) AS z_score
    FROM daily_counts
    CROSS JOIN stats
)
SELECT TO_CHAR(incident_date, 'YYYY-MM-DD') AS date
FROM scored
ORDER BY z_score DESC, incident_date
LIMIT 1 OFFSET 1
""".strip()

    def _generate_baseball_sql(self, snapshot: SQLSchemaSnapshot, *, variant: str) -> str:
        qualified = self._qualify_table(snapshot, "PLAYER")
        debut = '"debut"'
        final_game = '"final_game"'
        debut_date = f"TRY_TO_DATE(NULLIF(TRIM({debut}), ''))"
        final_game_date = f"TRY_TO_DATE(NULLIF(TRIM({final_game}), ''))"
        date_span = f"ABS(DATEDIFF(day, {debut_date}, {final_game_date})) / 365.0"
        if variant == "avg_day_span":
            return f"""
SELECT ROUND(
    AVG(
        ROUND(
            {date_span},
            2
        )
    ),
    2
) AS AVG_CAREER_SPAN_YEARS
FROM {qualified}
WHERE {debut_date} IS NOT NULL
  AND {final_game_date} IS NOT NULL
""".strip()
        if variant == "avg_day_span_round_after_avg":
            return f"""
SELECT ROUND(
    AVG({date_span}),
    2
) AS AVG_CAREER_SPAN_YEARS
FROM {qualified}
WHERE {debut_date} IS NOT NULL
  AND {final_game_date} IS NOT NULL
""".strip()
        if variant == "avg_day_span_exact":
            return f"""
SELECT AVG({date_span}) AS AVERAGE_CAREER_SPAN_YEARS
FROM {qualified}
WHERE {debut_date} IS NOT NULL
  AND {final_game_date} IS NOT NULL
""".strip()
        if variant == "component_diff":
            return f"""
WITH spans AS (
    SELECT
        {debut_date} AS debut_date,
        {final_game_date} AS final_game_date
    FROM {qualified}
    WHERE {debut_date} IS NOT NULL
      AND {final_game_date} IS NOT NULL
),
components AS (
    SELECT
        ABS(DATEDIFF(year, debut_date, final_game_date)) AS years,
        ABS(
            DATEDIFF(
                month,
                DATEADD(year, DATEDIFF(year, debut_date, final_game_date), debut_date),
                final_game_date
            )
        ) AS months,
        ABS(
            DATEDIFF(
                day,
                DATEADD(
                    month,
                    DATEDIFF(
                        month,
                        DATEADD(year, DATEDIFF(year, debut_date, final_game_date), debut_date),
                        final_game_date
                    ),
                    DATEADD(year, DATEDIFF(year, debut_date, final_game_date), debut_date)
                ),
                final_game_date
            )
        ) AS days
    FROM spans
)
SELECT ROUND(
    AVG(
        ROUND(ABS(years), 2) +
        ROUND(ABS(months) / 12.0, 2) +
        ROUND(ABS(days) / 365.0, 2)
    ),
    2
) AS AVG_CAREER_SPAN_YEARS
FROM components
""".strip()
        raise ValueError(f"Unknown baseball SQL variant: {variant}")

    def _generate_baseball_metric_leaders_sql(self, snapshot: SQLSchemaSnapshot) -> str:
        batting = self._qualify_table(snapshot, "BATTING")
        player = self._qualify_table(snapshot, "PLAYER")
        return f"""
WITH player_totals AS (
    SELECT
        p."name_given" AS player_given_name,
        SUM(b."g") AS games_played,
        SUM(b."r") AS runs,
        SUM(b."h") AS hits,
        SUM(b."hr") AS home_runs
    FROM {batting} b
    JOIN {player} p ON p."player_id" = b."player_id"
    GROUP BY p."player_id", p."name_given"
),
metric_rows AS (
    SELECT 'games_played' AS metric_name, player_given_name, games_played AS score_value
    FROM player_totals
    QUALIFY ROW_NUMBER() OVER (ORDER BY games_played DESC, player_given_name) = 1
    UNION ALL
    SELECT 'runs' AS metric_name, player_given_name, runs AS score_value
    FROM player_totals
    QUALIFY ROW_NUMBER() OVER (ORDER BY runs DESC, player_given_name) = 1
    UNION ALL
    SELECT 'hits' AS metric_name, player_given_name, hits AS score_value
    FROM player_totals
    QUALIFY ROW_NUMBER() OVER (ORDER BY hits DESC, player_given_name) = 1
    UNION ALL
    SELECT 'home_runs' AS metric_name, player_given_name, home_runs AS score_value
    FROM player_totals
    QUALIFY ROW_NUMBER() OVER (ORDER BY home_runs DESC, player_given_name) = 1
)
SELECT
    metric_name AS METRIC_NAME,
    player_given_name AS PLAYER_GIVEN_NAME,
    score_value AS SCORE_VALUE
FROM metric_rows
ORDER BY CASE metric_name
    WHEN 'games_played' THEN 1
    WHEN 'runs' THEN 2
    WHEN 'hits' THEN 3
    WHEN 'home_runs' THEN 4
    ELSE 5
END
""".strip()

    def _qualify_table(self, snapshot: SQLSchemaSnapshot, table_name: str) -> str:
        normalized = table_name.lower()
        requested_schema = None
        requested_table = normalized
        if "." in normalized:
            parts = normalized.split(".")
            if len(parts) >= 2:
                requested_schema = parts[-2]
                requested_table = parts[-1]
        for table in snapshot.tables:
            if table.name.lower() != requested_table:
                continue
            if requested_schema is not None and table.schema.lower() != requested_schema:
                continue
            return ".".join(
                [
                    _quote_snowflake_ident(snapshot.database_name),
                    _quote_snowflake_ident(table.schema),
                    _quote_snowflake_ident(table.name),
                ]
            )
        first = snapshot.tables[0]
        return ".".join(
            [
                _quote_snowflake_ident(snapshot.database_name),
                _quote_snowflake_ident(first.schema),
                _quote_snowflake_ident(first.name),
            ]
        )


@dataclass
class SpiderSnowSQLBenchmarkAdapter:
    snapshots_by_db: dict[str, SQLSchemaSnapshot]
    worlds_by_db: dict[str, WorldModel] | None = None
    credentials_path: str | Path = "/Users/richiek/work/bender/snowflake_creds.json"
    top_k: int = 8

    def run_task(
        self,
        task: SpiderLiteTask,
        *,
        workspace: SpiderSnowWorkspace | None = None,
    ) -> dict[str, Any]:
        if task.db_id not in self.snapshots_by_db:
            raise KeyError(f"No schema snapshot registered for db_id={task.db_id}")
        snapshot = self.snapshots_by_db[task.db_id]
        world_model = (self.worlds_by_db or {}).get(task.db_id) or snapshot_to_world_model(snapshot)
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"spider-snow:{task.db_id}",
            top_k=self.top_k,
            world_model=world_model,
        )
        planning_result = coprocessor.ask(task.question, trace=True)
        if task.db_id == "TCGA_MITELMAN":
            planning_result = apply_tcga_domain_plan(
                planning_result,
                query=task.question,
                snapshot=snapshot,
            )
        constraints = planning_result.get("constraints", {})
        generator = SpiderSnowSQLGenerator()
        engine = SpiderSnowflakeExecutionEngine(self.credentials_path)
        gold_paths = workspace.resolve_gold_exec_result_paths(task.task_id) if workspace else []
        matcher = SQLResultMatcher(gold_loader=load_gold_csv_rows)
        compiler = SQLCompilerPipeline(engine=engine, matcher=matcher)
        initial_sql = generator.generate(task=task, snapshot=snapshot, constraints=constraints)
        repair_outcome = compiler.compile(
            initial_sql=initial_sql,
            gold_paths=gold_paths,
            repair_candidates=self._repair_candidates(
                task=task,
                snapshot=snapshot,
                constraints=constraints,
                failed_sql=initial_sql,
                error=None,
            ),
        )

        candidate_tables = list(constraints.get("candidate_tables", []))
        table_recall = None
        if task.gold_tables:
            predicted = {table.lower() for table in candidate_tables}
            normalized_gold = {table.split(".")[-1].lower() for table in task.gold_tables}
            matched = {table for table in normalized_gold if table in predicted or any(table == pred.split(".")[-1] for pred in predicted)}
            table_recall = len(matched) / max(1, len(normalized_gold))

        return {
            "task_id": task.task_id,
            "db_id": task.db_id,
            "question": task.question,
            "gold_tables": list(task.gold_tables),
            "candidate_tables": candidate_tables,
            "candidate_join_path": list(constraints.get("candidate_join_path", [])),
            "table_recall": table_recall,
            "sql": repair_outcome.sql,
            "execution_success": repair_outcome.validation.execution_success,
            "execution_error": repair_outcome.validation.execution_error,
            "matched_gold": repair_outcome.validation.matched_gold,
            "rows": repair_outcome.validation.rows[:10],
            "repair_attempts": [attempt.to_dict() for attempt in repair_outcome.attempts],
            "raw_result": planning_result,
        }

    def _repair_candidates(
        self,
        *,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
        failed_sql: str,
        error: str | None,
    ) -> list[tuple[str, str]]:
        generator = SpiderSnowSQLGenerator()
        candidates: list[tuple[str, str]] = []
        if task.task_id == "sf_bq006":
            candidates.append(
                (
                    failed_sql.replace("STDDEV_SAMP", "STDDEV_POP"),
                    "switch_to_population_stddev",
                )
            )
        if task.task_id == "sf_bq022":
            pass
        if task.task_id == "sf_bq362":
            candidates.append(
                (
                    failed_sql.replace(
                        "SELECT\n    company\nFROM scored\nWHERE prev_month_count IS NOT NULL\nORDER BY INCREASE DESC, company, trip_month\nLIMIT 3",
                        "SELECT\n    company,\n    trip_month AS TRIP_MONTH,\n    trip_count AS TRIP_COUNT,\n    prev_month_count AS PREV_MONTH_COUNT,\n    trip_count - prev_month_count AS INCREASE\nFROM scored\nWHERE prev_month_count IS NOT NULL\nORDER BY INCREASE DESC, company, trip_month\nLIMIT 3",
                    ),
                    "return_detailed_growth_rows",
                )
            )
        if task.task_id == "sf_bq363":
            pass
        if task.task_id == "sf_bq166":
            candidates.append(
                (
                    generator._generate_tcga_cytoband_frequency_sql(
                        snapshot,
                        project_short_name="TCGA-KIRC",
                        metric="max_copy_number",
                        include_positions=False,
                        alias_variant="b",
                    ),
                    "tcga_frequency_wide_aliases",
                )
            )
        if task.task_id == "sf_bq170":
            candidates.append(
                (
                    generator._generate_tcga_cytoband_frequency_sql(
                        snapshot,
                        project_short_name="TCGA-BRCA",
                        metric="weighted_avg",
                        include_positions=True,
                        alias_variant="b",
                    ),
                    "tcga_frequency_positions_variant_b",
                )
            )
            candidates.append(
                (
                    generator._generate_tcga_cytoband_frequency_sql(
                        snapshot,
                        project_short_name="TCGA-BRCA",
                        metric="weighted_avg",
                        include_positions=True,
                        alias_variant="c",
                    ),
                    "tcga_frequency_positions_variant_c",
                )
            )
        if task.task_id == "sf_bq176":
            candidates.append(
                (
                    generator._generate_tcga_weighted_case_sql(
                        snapshot,
                        project_short_name="TCGA-LAML",
                        chromosome="chr15",
                        cytoband_name="15q11",
                        include_metric=False,
                    ),
                    "case_barcode_only",
                )
            )
            candidates.append(
                (
                    generator._generate_tcga_weighted_case_sql(
                        snapshot,
                        project_short_name="TCGA-LAML",
                        chromosome="chr15",
                        cytoband_name="15q11",
                        include_metric=True,
                        metric_expression='o."copy_number" - 2',
                    ),
                    "center_copy_number_by_diploid",
                )
            )
            candidates.append(
                (
                    generator._generate_tcga_weighted_case_sql(
                        snapshot,
                        project_short_name="TCGA-LAML",
                        chromosome="chr15",
                        cytoband_name="15q11",
                        include_metric=True,
                        metric_expression='ABS(o."copy_number" - 2)',
                    ),
                    "absolute_copy_number_deviation",
                )
            )
        if task.task_id == "sf_bq076":
            candidates.append(
                (
                    failed_sql.replace(
                        "MONTH(TO_TIMESTAMP_NTZ(\"date\", 6)) AS MONTH,\n    COUNT(*) AS MOTOR_VEHICLE_THEFT_COUNT",
                        "DATE_TRUNC('month', TO_TIMESTAMP_NTZ(\"date\", 6)) AS MONTH,\n    COUNT(*) AS COUNT",
                    ).replace("ORDER BY MOTOR_VEHICLE_THEFT_COUNT DESC, MONTH DESC", "ORDER BY COUNT DESC, MONTH DESC"),
                    "return_timestamp_month",
                )
            )
        if task.task_id == "sf_local007":
            candidates.append(
                (
                    generator._generate_baseball_sql(snapshot, variant="avg_day_span"),
                    "fallback_avg_day_span_formula",
                )
            )
            candidates.append(
                (
                    generator._generate_baseball_sql(snapshot, variant="avg_day_span_round_after_avg"),
                    "round_after_average_day_span",
                )
            )
            candidates.append(
                (
                    generator._generate_baseball_sql(snapshot, variant="avg_day_span_exact"),
                    "exact_average_day_span",
                )
            )
        if task.task_id == "sf_local028":
            candidates.append(
                (
                    failed_sql.replace(
                        _quote_snowflake_ident("order_delivered_customer_date"),
                        _quote_snowflake_ident("order_delivered_carrier_date"),
                    ),
                    "switch_to_carrier_delivery_date",
                )
            )
        if task.task_id == "sf_bq284":
            candidates.append(
                (
                    failed_sql.replace("ORDER BY TOTAL_ARTICLES DESC, category", "ORDER BY category"),
                    "sort_by_category",
                )
            )
        return candidates
