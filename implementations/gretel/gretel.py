from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from octo.benchmarking import (
    BenchmarkCaseResult,
    benchmark_report_to_dict,
    render_markdown_summary_table,
    summarize_system_results,
)
from octo.database import SQLColumnProfile, SQLSchemaSnapshot, SQLTableProfile
from implementations.sql import SQLSchemaCoprocessor
from octo.world_state import WorldModel


def _normalize_identifier(value: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "_", snake.lower()).strip("_")


def _truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def _infer_gold_tables_from_sql(sql: str) -> list[str]:
    if not sql.strip():
        return []
    try:
        expression = sqlglot.parse_one(sql, read="sqlite")
    except ParseError:
        return []
    tables: list[str] = []
    cte_names = {
        cte.alias_or_name.lower()
        for cte in expression.find_all(exp.CTE)
        if cte.alias_or_name
    }
    for table_ref in expression.find_all(exp.Table):
        table_name = table_ref.name
        if table_name.lower() in cte_names:
            continue
        if table_name not in tables:
            tables.append(table_name)
    return tables


@dataclass
class GretelTask:
    task_id: str
    domain: str
    domain_description: str
    sql_prompt: str
    sql_context: str
    gold_sql: str
    sql_explanation: str = ""
    sql_task_type: str = ""
    sql_task_type_description: str = ""
    sql_complexity: str = ""
    sql_complexity_description: str = ""
    gold_tables: list[str] = field(default_factory=list)
    raw_record: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "GretelTask":
        gold_sql = str(record.get("sql") or "")
        return cls(
            task_id=str(record.get("id") or record.get("task_id") or "gretel_task"),
            domain=str(record.get("domain") or "unknown_domain"),
            domain_description=str(record.get("domain_description") or ""),
            sql_prompt=str(record.get("sql_prompt") or record.get("question") or ""),
            sql_context=str(record.get("sql_context") or ""),
            gold_sql=gold_sql,
            sql_explanation=str(record.get("sql_explanation") or ""),
            sql_task_type=str(record.get("sql_task_type") or ""),
            sql_task_type_description=str(record.get("sql_task_type_description") or ""),
            sql_complexity=str(record.get("sql_complexity") or ""),
            sql_complexity_description=str(record.get("sql_complexity_description") or ""),
            gold_tables=_infer_gold_tables_from_sql(gold_sql),
            raw_record=dict(record),
        )


class GretelDatasetLoader:
    def load_json(self, path: str | Path) -> list[GretelTask]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        records = payload.get("records", []) if isinstance(payload, dict) else payload
        return [GretelTask.from_record(record) for record in records]

    def load_huggingface(self, *, split: str = "train[:100]") -> list[GretelTask]:
        from datasets import load_dataset

        dataset = load_dataset("gretelai/synthetic_text_to_sql", split=split)
        return [GretelTask.from_record(dict(record)) for record in dataset]

    def iter_huggingface(
        self,
        *,
        split: str = "train",
        cache_dir: str | None = None,
    ):
        from datasets import load_dataset

        dataset = load_dataset(
            "gretelai/synthetic_text_to_sql",
            split=split,
            cache_dir=cache_dir,
        )
        for record in dataset:
            yield GretelTask.from_record(dict(record))


def build_snapshot_from_sql_context(
    sql_context: str, *, database_name: str
) -> SQLSchemaSnapshot:
    statements = sqlglot.parse(sql_context, read="sqlite")
    tables: list[SQLTableProfile] = []
    for statement in statements:
        if not isinstance(statement, exp.Create):
            continue
        schema = statement.this
        if not isinstance(schema, exp.Schema):
            continue
        table_ref = schema.this
        if not isinstance(table_ref, exp.Table):
            continue
        columns: list[SQLColumnProfile] = []
        for ordinal_position, column_def in enumerate(schema.expressions, start=1):
            if not isinstance(column_def, exp.ColumnDef):
                continue
            columns.append(
                SQLColumnProfile(
                    schema="main",
                    table=table_ref.name,
                    name=str(column_def.this),
                    data_type=str(column_def.args.get("kind") or "TEXT"),
                    is_nullable=True,
                    ordinal_position=ordinal_position,
                    sample_values=[],
                )
            )
        tables.append(
            SQLTableProfile(
                schema="main",
                name=table_ref.name,
                description="gretel synthetic table",
                columns=columns,
            )
        )
    return SQLSchemaSnapshot(
        database_name=database_name, tables=tables, foreign_keys=[]
    )


def enrich_world_with_gretel_metadata(
    world_model: WorldModel, task: GretelTask
) -> WorldModel:
    database_node_id = f"database:{task.task_id}"
    if database_node_id not in world_model.nodes:
        return world_model

    docs = {
        f"{task.task_id}:domain": f"Domain: {task.domain}. {task.domain_description}",
        f"{task.task_id}:task_type": f"Task type: {task.sql_task_type}. {task.sql_task_type_description}",
        f"{task.task_id}:complexity": f"Complexity: {task.sql_complexity}. {task.sql_complexity_description}",
        f"{task.task_id}:explanation": task.sql_explanation,
    }
    for doc_key, text in docs.items():
        if not text.strip():
            continue
        node_id = f"document:{doc_key}"
        world_model.upsert_node(
            node_id,
            label=doc_key.split(":")[-1],
            type="document",
            summary=_truncate_text(text, 800),
            keywords=[task.domain, task.sql_task_type, task.sql_complexity],
            source_file=doc_key,
        )
        world_model.add_edge(database_node_id, "has_document", node_id, score=0.92)
    return world_model


@dataclass
class GretelBenchmarkAdapter:
    snapshots_by_task: dict[str, SQLSchemaSnapshot]
    worlds_by_task: dict[str, WorldModel] | None = None
    top_k: int = 8
    include_metadata_in_query: bool = False

    def run_task(self, task: GretelTask) -> dict[str, Any]:
        snapshot = self.snapshots_by_task[task.task_id]
        world_model = (self.worlds_by_task or {}).get(task.task_id)
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"gretel:{task.task_id}",
            top_k=self.top_k,
            world_model=world_model,
        )
        query = task.sql_prompt
        if self.include_metadata_in_query:
            metadata = " ".join(
                bit
                for bit in [
                    f"Domain: {task.domain}.",
                    task.domain_description.strip(),
                    f"Task type: {task.sql_task_type}.",
                    task.sql_task_type_description.strip(),
                ]
                if bit
            )
            if metadata:
                query = f"{task.sql_prompt}\nContext: {metadata}"
        result = coprocessor.ask(query, trace=True)
        candidate_tables = result.get("constraints", {}).get("candidate_tables", [])
        gold_table_names = task.gold_tables
        table_recall = None
        if gold_table_names:
            gold_tables = {_normalize_identifier(name) for name in gold_table_names}
            predicted_tables = {_normalize_identifier(name) for name in candidate_tables}
            if gold_tables:
                table_recall = len(gold_tables & predicted_tables) / len(gold_tables)
        return {
            "task_id": task.task_id,
            "domain": task.domain,
            "question": task.sql_prompt,
            "query": query,
            "candidate_tables": candidate_tables,
            "table_recall": table_recall,
            "gold_tables": gold_table_names,
            "trace": result.get("trace", []),
            "raw_result": result,
        }


@dataclass
class GretelABBenchmarkRunner:
    baseline_adapter: GretelBenchmarkAdapter
    octo_adapter: GretelBenchmarkAdapter

    def run(self, tasks: list[GretelTask]) -> dict[str, Any]:
        naive_results: list[BenchmarkCaseResult] = []
        baseline_results: list[BenchmarkCaseResult] = []
        octo_results: list[BenchmarkCaseResult] = []
        for task in tasks:
            naive = _run_gretel_naive_baseline(
                self.baseline_adapter.snapshots_by_task[task.task_id], task
            )
            baseline = self.baseline_adapter.run_task(task)
            octo = self.octo_adapter.run_task(task)
            naive_results.append(
                BenchmarkCaseResult(
                    case_id=task.task_id,
                    system="naive_lexical",
                    correct=bool((naive.get("table_recall") or 0.0) >= 1.0),
                    metrics={
                        "table_recall": naive.get("table_recall"),
                        "top1_hit": _top1_hit(naive),
                    },
                    detail=naive,
                )
            )
            baseline_results.append(
                BenchmarkCaseResult(
                    case_id=task.task_id,
                    system="schema_only",
                    correct=bool((baseline.get("table_recall") or 0.0) >= 1.0),
                    metrics={
                        "table_recall": baseline.get("table_recall"),
                        "top1_hit": _top1_hit(baseline),
                    },
                    detail=baseline,
                )
            )
            octo_results.append(
                BenchmarkCaseResult(
                    case_id=task.task_id,
                    system="octo",
                    correct=bool((octo.get("table_recall") or 0.0) >= 1.0),
                    metrics={
                        "table_recall": octo.get("table_recall"),
                        "top1_hit": _top1_hit(octo),
                    },
                    detail=octo,
                )
            )
        summaries = [
            summarize_system_results(
                "naive_lexical", naive_results, metric_names=["table_recall", "top1_hit"]
            ),
            summarize_system_results(
                "schema_only", baseline_results, metric_names=["table_recall", "top1_hit"]
            ),
            summarize_system_results(
                "octo", octo_results, metric_names=["table_recall", "top1_hit"]
            ),
        ]
        payload = benchmark_report_to_dict(
            benchmark_name="gretel_ab_grounding",
            summaries=summaries,
            results_by_system={
                "naive_lexical": naive_results,
                "schema_only": baseline_results,
                "octo": octo_results,
            },
        )
        payload["markdown_summary"] = render_markdown_summary_table(summaries)
        return payload


def _top1_hit(result: dict[str, Any]) -> float:
    candidate_tables = result.get("candidate_tables", [])
    gold_tables = result.get("gold_tables", [])
    if not candidate_tables or not gold_tables:
        return 0.0
    predicted = _normalize_identifier(candidate_tables[0])
    gold = {_normalize_identifier(name) for name in gold_tables}
    return 1.0 if predicted in gold else 0.0


def _run_gretel_naive_baseline(
    snapshot: SQLSchemaSnapshot, task: GretelTask
) -> dict[str, Any]:
    question_tokens = set(re.findall(r"[a-z0-9_]+", task.sql_prompt.lower()))
    scored: list[tuple[float, str]] = []
    for table in snapshot.tables:
        table_tokens = set(re.findall(r"[a-z0-9_]+", table.name.lower()))
        column_tokens = {
            token
            for column in table.columns
            for token in re.findall(r"[a-z0-9_]+", column.name.lower())
        }
        score = len(question_tokens & table_tokens) * 2.0 + len(
            question_tokens & column_tokens
        ) * 0.5
        scored.append((score, table.name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    candidate_tables = [name for score, name in scored if score > 0.0][:3]
    gold_table_names = task.gold_tables
    table_recall = None
    if gold_table_names:
        gold_tables = {_normalize_identifier(name) for name in gold_table_names}
        predicted_tables = {_normalize_identifier(name) for name in candidate_tables}
        table_recall = (
            len(gold_tables & predicted_tables) / len(gold_tables)
            if gold_tables
            else None
        )
    return {
        "task_id": task.task_id,
        "domain": task.domain,
        "question": task.sql_prompt,
        "candidate_tables": candidate_tables,
        "table_recall": table_recall,
        "gold_tables": gold_table_names,
    }
