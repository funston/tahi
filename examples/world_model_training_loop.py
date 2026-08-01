"""Prototype of an LLM-driven world-model training loop.

The loop:
 1. Build a baseline world model from a BIRD SQLite database.
 2. Evaluate table recall on the dev questions.
 3. Feed the failures to an LLM (GPT-4o-mini) and ask for ontology fixes
    (aliases, semantic types) that would have retrieved the missing tables.
 4. Apply the LLM's suggestions to the world model.
 5. Re-evaluate and report the delta.

No GPUs are needed. The only external cost is a small number of LLM calls for
suggestions.

Run:
    python examples/world_model_training_loop.py --db-id superhero
    python examples/world_model_training_loop.py --db-id financial

Requires OPENAI_API_KEY in the environment.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import pyarrow.ipc as ipc
import sqlglot

from implementations.spider.spider import SpiderSchemaCoprocessor
from implementations.spider.spider_lite import SpiderLiteTask, SpiderLiteSQLiteDatabaseLoader
from octo.database import SQLSchemaSnapshot, snapshot_to_world_model
from octo.world_state import WorldModel


BIRD_ARROW = (
    ROOT
    / ".local"
    / "bird_hf"
    / "hf_datasets"
    / "Sudnya___bird-sql"
    / "default"
    / "0.0.0"
    / "7877a1bfee6b3794f5026b1f00fcc4dd43e529be"
    / "bird-sql-validation.arrow"
)
BIRD_DB_ROOT = ROOT / ".local" / "bird_hf" / "dev" / "dev_databases"


def load_bird_tasks(db_id: str) -> list[SpiderLiteTask]:
    with open(BIRD_ARROW, "rb") as handle:
        table = ipc.open_stream(handle).read_all()

    tasks: list[SpiderLiteTask] = []
    for row in table.to_pylist():
        if str(row["db_id"]) != db_id:
            continue
        record = {
            "instance_id": str(row["question_id"]),
            "db_id": db_id,
            "db": db_id,
            "question": str(row["question"]),
            "evidence": str(row["evidence"] or ""),
            "gold_sql": str(row["SQL"] or ""),
        }
        task = SpiderLiteTask.from_record(record)
        task.gold_tables = _gold_tables_from_sql(task.gold_sql)
        tasks.append(task)
    return tasks


def _gold_tables_from_sql(sql: str) -> list[str]:
    for dialect in ("mysql", "sqlite"):
        try:
            parsed = sqlglot.parse_one(sql, dialect=dialect)
            return sorted({table.name for table in parsed.find_all(sqlglot.exp.Table)})
        except Exception:
            continue
    return []


def build_db_snapshot(db_id: str) -> SQLSchemaSnapshot:
    db_path = BIRD_DB_ROOT / db_id / f"{db_id}.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    return SpiderLiteSQLiteDatabaseLoader().load(db_path, db_id=db_id, sample_limit=5)


def evaluate(
    tasks: list[SpiderLiteTask],
    snapshot: SQLSchemaSnapshot,
    world_model: WorldModel,
    top_k: int = 8,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    total_recall = 0.0
    total_with_gold = 0

    for task in tasks:
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"bird:{task.db_id}",
            top_k=top_k,
            world_model=world_model,
        )
        result = coprocessor.ask(task.question, trace=False)
        candidate_tables = result.get("constraints", {}).get("candidate_tables", [])

        normalized_gold = {t.lower() for t in task.gold_tables}
        normalized_predicted = {t.lower().split(".")[-1] for t in candidate_tables}
        matched = normalized_gold & normalized_predicted
        recall = len(matched) / max(1, len(normalized_gold))

        total_with_gold += 1
        total_recall += recall

        if recall < 1.0:
            failures.append(
                {
                    "task_id": task.task_id,
                    "question": task.question,
                    "gold_tables": task.gold_tables,
                    "predicted_tables": candidate_tables,
                    "missing": sorted(normalized_gold - normalized_predicted),
                }
            )

    return {
        "tasks": len(tasks),
        "average_recall": total_recall / total_with_gold if total_with_gold else 0.0,
        "failures": failures,
    }


def schema_summary(world_model: WorldModel) -> str:
    lines: list[str] = []
    for node_id, attrs in sorted(world_model.nodes.items()):
        node_type = attrs.get("type")
        if node_type == "table":
            label = attrs.get("label", node_id)
            aliases = attrs.get("aliases", [])
            lines.append(f"TABLE {label}" + (f" aliases={aliases}" if aliases else ""))
        elif node_type == "column":
            label = attrs.get("label", node_id)
            summary = attrs.get("summary", "")
            aliases = attrs.get("aliases", [])
            stype = attrs.get("semantic_type", "")
            parts = [f"  COLUMN {label}"]
            if aliases:
                parts.append(f"aliases={aliases}")
            if stype:
                parts.append(f"type={stype}")
            if summary:
                parts.append(f"summary={summary[:120]}")
            lines.append(" ".join(parts))
    return "\n".join(lines)


def build_prompt(
    db_id: str,
    world_model: WorldModel,
    failures: list[dict[str, Any]],
    max_failures: int = 25,
) -> str:
    failure_text = ""
    for idx, failure in enumerate(failures[:max_failures], 1):
        failure_text += (
            f"\n{idx}. Question: {failure['question']}\n"
            f"   Gold tables: {failure['gold_tables']}\n"
            f"   Predicted tables: {failure['predicted_tables']}\n"
            f"   Missing tables: {failure['missing']}\n"
        )

    return f"""You are a schema-ontology engineer. Your job is to improve a structured world model so that a keyword/graph retriever surfaces the right database tables for natural-language questions.

DATABASE: {db_id}

CURRENT SCHEMA (tables, columns, existing aliases, semantic types):
{schema_summary(world_model)}

RECENT FAILURES (the retriever did not return the missing tables):
{failure_text}

TASK:
Suggest concise additions to the world model that would fix these failures. Prefer generic domain terms over question-specific phrasing. Return a JSON object with exactly this shape:

{{
  "add_aliases": {{
    "table_name": ["alias1", "alias2"],
    "table_name.column_name": ["alias1", "alias2"]
  }},
  "add_semantic_types": {{
    "table_name.column_name": "semantic_type"
  }},
  "rationale": "short explanation"
}}

Only include entries that are missing or genuinely useful. Do not duplicate existing aliases.
"""


def llm_suggest(
    db_id: str, world_model: WorldModel, failures: list[dict[str, Any]]
) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed") from exc

    client = OpenAI(api_key=api_key)
    prompt = build_prompt(db_id, world_model, failures)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Empty LLM response")
    return json.loads(content)


def apply_suggestions(world_model: WorldModel, suggestions: dict[str, Any]) -> None:
    add_aliases = suggestions.get("add_aliases", {})
    add_types = suggestions.get("add_semantic_types", {})

    # Build lookup from node id -> attrs for tables and columns.
    table_nodes: dict[str, dict[str, Any]] = {}
    column_nodes: dict[str, dict[str, Any]] = {}
    for node_id, attrs in world_model.nodes.items():
        if attrs.get("type") == "table":
            table_nodes[attrs.get("table_name", "").lower()] = attrs
        elif attrs.get("type") == "column":
            key = (
                f"{attrs.get('table_name', '').lower()}."
                f"{attrs.get('column_name', '').lower()}"
            )
            column_nodes[key] = attrs

    for key, aliases in add_aliases.items():
        if "." in key:
            target = column_nodes.get(key.lower())
        else:
            target = table_nodes.get(key.lower())
        if target is None:
            continue
        existing = set(target.get("aliases", []))
        new = [a for a in aliases if isinstance(a, str)]
        target["aliases"] = sorted(existing | set(new))

    for key, stype in add_types.items():
        if "." not in key:
            continue
        target = column_nodes.get(key.lower())
        if target is None:
            continue
        target["semantic_type"] = str(stype)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-driven world-model training loop prototype"
    )
    parser.add_argument(
        "--db-id", type=str, required=True, choices=["superhero", "financial"]
    )
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument(
        "--max-failures", type=int, default=25, help="Failures to show the LLM"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompt and suggestions but do not call LLM",
    )
    args = parser.parse_args()

    print(f"Loading tasks and snapshot for {args.db_id}...")
    tasks = load_bird_tasks(args.db_id)
    snapshot = build_db_snapshot(args.db_id)

    print("Running baseline evaluation...")
    baseline_world = snapshot_to_world_model(snapshot)
    baseline = evaluate(tasks, snapshot, baseline_world, args.top_k)
    print(
        f"  Baseline recall: {baseline['average_recall']:.3f}"
        f" ({len(baseline['failures'])} failures)\n"
    )

    if not baseline["failures"]:
        print("No failures to improve.")
        return

    print("Building LLM prompt from failures...")
    prompt = build_prompt(
        args.db_id, baseline_world, baseline["failures"], args.max_failures
    )

    if args.dry_run:
        print(prompt)
        return

    print("Calling LLM for ontology suggestions...")
    suggestions = llm_suggest(args.db_id, baseline_world, baseline["failures"])
    print(json.dumps(suggestions, indent=2))
    print()

    print("Applying suggestions to world model...")
    enriched_world = snapshot_to_world_model(snapshot)
    apply_suggestions(enriched_world, suggestions)

    print("Re-running evaluation...")
    enriched = evaluate(tasks, snapshot, enriched_world, args.top_k)
    print(
        f"  Enriched recall: {enriched['average_recall']:.3f}"
        f" ({len(enriched['failures'])} failures)"
    )

    delta = enriched["average_recall"] - baseline["average_recall"]
    fixed = len(baseline["failures"]) - len(enriched["failures"])
    print(f"  Delta: +{delta:.3f} ({fixed} failures fixed)")


if __name__ == "__main__":
    main()
