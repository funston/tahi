"""Enriched world-model recall experiment on BIRD superhero and financial.

This script shows that adding domain aliases and semantic types to the world
model improves table recall on the two hardest BIRD dev databases.

Run:
    python examples/bird_enriched_recall.py
    python examples/bird_enriched_recall.py --db-id financial
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import pyarrow.ipc as ipc
import sqlglot

from implementations.spider.spider import SpiderSchemaCoprocessor
from implementations.spider.spider_lite import SpiderLiteTask
from implementations.spider.spider_lite import SpiderLiteSQLiteDatabaseLoader
from octo.database import SQLSchemaSnapshot, snapshot_to_world_model
from octo.world_state import WorldModel


BIRD_ARROW = Path(
    "/Users/richiek/work/bender/.local/bird_hf/hf_datasets/"
    "Sudnya___bird-sql/default/0.0.0/7877a1bfee6b3794f5026b1f00fcc4dd43e529be/"
    "bird-sql-validation.arrow"
)
BIRD_DB_ROOT = Path("/Users/richiek/work/bender/.local/bird_hf/dev/dev_databases")


def load_bird_tasks(db_ids: set[str] | None = None) -> list[SpiderLiteTask]:
    with open(BIRD_ARROW, "rb") as handle:
        table = ipc.open_stream(handle).read_all()

    tasks: list[SpiderLiteTask] = []
    for row in table.to_pylist():
        db_id = str(row["db_id"])
        if db_ids is not None and db_id not in db_ids:
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


def _set_aliases(node: dict[str, Any], aliases: list[str]) -> None:
    existing = set(node.get("aliases", []))
    node["aliases"] = sorted(existing | set(aliases))


def _set_summary(node: dict[str, Any], suffix: str) -> None:
    summary = node.get("summary", "")
    if suffix.lower() not in summary.lower():
        node["summary"] = f"{summary} {suffix}".strip()


# ---------------------------------------------------------------------------
# Superhero enrichment
# ---------------------------------------------------------------------------


def enrich_superhero_world_model(world_model: WorldModel, snapshot: SQLSchemaSnapshot) -> None:
    """Add domain aliases for the BIRD superhero schema."""
    table_aliases = {
        "superhero": ["superhero", "hero", "character"],
        "colour": ["colour", "color", "eye colour", "hair colour", "skin colour", "appearance"],
        "gender": ["gender", "sex", "male", "female"],
        "publisher": ["publisher", "comics", "comic book publisher", "Marvel", "DC", "Dark Horse"],
        "race": ["race", "species", "vampire", "alien", "human", "demi-god", "demigod"],
        "alignment": ["alignment", "good", "bad", "neutral", "villain", "hero", "moral"],
        "superpower": ["superpower", "power", "ability", "super strength"],
        "hero_power": ["hero power", "superhero power", "powers", "abilities"],
        "attribute": ["attribute", "intelligence", "strength", "speed", "durability", "power", "combat"],
        "hero_attribute": [
            "hero attribute",
            "attribute value",
            "stats",
            "fastest",
            "strongest",
            "dumbest",
            "weakest",
            "slowest",
            "most durable",
        ],
    }

    column_aliases = {
        "eye_colour_id": ["eye colour", "eye color", "eyes"],
        "hair_colour_id": ["hair colour", "hair color", "hair"],
        "skin_colour_id": ["skin colour", "skin color", "skin"],
        "gender_id": ["gender", "sex"],
        "race_id": ["race", "species"],
        "publisher_id": ["publisher", "comics"],
        "alignment_id": ["alignment", "good", "bad", "neutral"],
        "height_cm": ["height", "tall"],
        "weight_kg": ["weight", "heavy"],
    }

    for node_id, attrs in world_model.nodes.items():
        node_type = attrs.get("type")
        if node_type == "table":
            table_name = attrs.get("table_name", "")
            aliases = table_aliases.get(table_name, [])
            if aliases:
                _set_aliases(attrs, aliases)
        elif node_type == "column":
            column_name = attrs.get("column_name", "")
            aliases = column_aliases.get(column_name, [])
            if aliases:
                _set_aliases(attrs, aliases)
            _set_summary(attrs, f"Related terms: {', '.join(aliases[:3])}.")


# ---------------------------------------------------------------------------
# Financial enrichment
# ---------------------------------------------------------------------------


def _financial_district_values(db_path: Path) -> tuple[list[str], list[str]]:
    """Read district names and regions from the financial database."""
    conn = sqlite3.connect(str(db_path))
    try:
        names = [row[0] for row in conn.execute("SELECT DISTINCT A2 FROM district WHERE A2 IS NOT NULL")]
        regions = [row[0] for row in conn.execute("SELECT DISTINCT A3 FROM district WHERE A3 IS NOT NULL")]
        return names, regions
    finally:
        conn.close()


def enrich_financial_world_model(world_model: WorldModel, snapshot: SQLSchemaSnapshot) -> None:
    """Add domain aliases for the BIRD financial schema."""
    db_path = BIRD_DB_ROOT / "financial" / "financial.sqlite"
    district_names, district_regions = _financial_district_values(db_path)

    table_aliases = {
        "district": ["district", "region", "branch", "location", "area", "city", "town"] + district_names + district_regions,
        "client": ["client", "customer", "person", "account holder"],
        "account": ["account", "bank account"],
        "disp": ["disposition", "disp", "owner", "account holder", "ownership"],
        "card": ["card", "credit card", "bank card"],
        "loan": ["loan", "credit"],
        "order": ["order", "payment order", "standing order", "bank order"],
        "trans": ["transaction", "trans", "withdrawal", "deposit", "bank transaction"],
    }

    column_aliases = {
        "A2": ["district name", "city", "branch", "town name"],
        "A3": ["region"],
        "A11": ["average salary", "salary", "income", "wage"],
        "A12": ["unemployment 1995", "unemployment rate 1995"],
        "A13": ["unemployment 1996", "unemployment rate 1996"],
        "A14": ["crimes 1995", "number of crimes 1995"],
        "A15": ["crimes 1996", "number of crimes 1996"],
        "gender": ["gender", "sex", "male", "female"],
        "birth_date": ["birth date", "date of birth", "born", "age"],
        "frequency": ["frequency", "statement issuance", "weekly", "monthly", "issuance"],
        "date": ["open date", "account opening date", "opened", "transaction date"],
        "type": ["type", "disposition type", "owner type", "ownership type", "card type", "transaction type", "withdrawal", "credit"],
        "issued": ["issued date", "card issued"],
        "amount": ["amount", "loan amount", "transaction amount"],
        "duration": ["loan duration"],
        "payments": ["monthly payments", "loan payments"],
        "status": ["loan status"],
        "k_symbol": ["payment symbol", "transaction symbol", "purpose", "household payment"],
        "balance": ["balance"],
        "bank": ["bank"],
        "operation": ["operation", "transaction operation"],
        "bank_to": ["destination bank"],
        "account_to": ["destination account"],
    }

    for node_id, attrs in world_model.nodes.items():
        node_type = attrs.get("type")
        if node_type == "table":
            table_name = attrs.get("table_name", "")
            aliases = table_aliases.get(table_name, [])
            if aliases:
                _set_aliases(attrs, aliases)
        elif node_type == "column":
            column_name = attrs.get("column_name", "")
            aliases = column_aliases.get(column_name, [])
            if aliases:
                _set_aliases(attrs, aliases)
            _set_summary(attrs, f"Related terms: {', '.join(aliases[:3])}.")


ENRICHMENTS: dict[str, Callable[[WorldModel, SQLSchemaSnapshot], None]] = {
    "superhero": enrich_superhero_world_model,
    "financial": enrich_financial_world_model,
}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    tasks: list[SpiderLiteTask],
    snapshot: SQLSchemaSnapshot,
    world_model: WorldModel,
    top_k: int,
) -> dict[str, Any]:
    per_task: list[dict[str, Any]] = []
    total_with_gold = 0
    total_recall = 0.0
    failures: list[dict[str, Any]] = []

    for task in tasks:
        if task.db_id != snapshot.database_name:
            continue
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"bird:{task.db_id}",
            top_k=top_k,
            world_model=world_model,
        )
        result = coprocessor.ask(task.question, trace=False)
        candidate_tables = result.get("constraints", {}).get("candidate_tables", [])

        recall = None
        if task.gold_tables:
            normalized_gold = {t.lower() for t in task.gold_tables}
            normalized_predicted = {t.lower().split(".")[-1] for t in candidate_tables}
            matched = normalized_gold & normalized_predicted
            recall = len(matched) / max(1, len(normalized_gold))

        record = {
            "task_id": task.task_id,
            "db_id": task.db_id,
            "question": task.question,
            "gold_tables": task.gold_tables,
            "candidate_tables": candidate_tables,
            "table_recall": recall,
        }
        per_task.append(record)

        if recall is not None:
            total_with_gold += 1
            total_recall += recall
            if recall < 1.0:
                failures.append(record)

    return {
        "tasks_evaluated": len(per_task),
        "tasks_with_gold_tables": total_with_gold,
        "average_table_recall": total_recall / total_with_gold if total_with_gold else None,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BIRD enriched world-model recall experiment")
    parser.add_argument("--db-id", type=str, default=None, help="Evaluate only this DB")
    parser.add_argument("--top-k", type=int, default=8, help="Candidate table limit")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output")
    args = parser.parse_args()

    db_ids = {args.db_id} if args.db_id else set(ENRICHMENTS)
    tasks = load_bird_tasks(db_ids)

    print(f"Evaluating {sorted(db_ids)} — {len(tasks)} tasks\n")

    summary_rows: list[dict[str, Any]] = []
    for db_id in sorted(db_ids):
        db_path = BIRD_DB_ROOT / db_id / f"{db_id}.sqlite"
        if not db_path.exists():
            print(f"Skipping {db_id}: database not found")
            continue

        db_tasks = [t for t in tasks if t.db_id == db_id]
        loader = SpiderLiteSQLiteDatabaseLoader()
        snapshot = loader.load(db_path, db_id=db_id, sample_limit=5)

        baseline_world = snapshot_to_world_model(snapshot)
        baseline_result = evaluate(db_tasks, snapshot, baseline_world, args.top_k)

        enriched_world = snapshot_to_world_model(snapshot)
        ENRICHMENTS[db_id](enriched_world, snapshot)
        enriched_result = evaluate(db_tasks, snapshot, enriched_world, args.top_k)

        baseline_recall = baseline_result["average_table_recall"] or 0.0
        enriched_recall = enriched_result["average_table_recall"] or 0.0
        delta = enriched_recall - baseline_recall
        fixed = len(baseline_result["failures"]) - len(enriched_result["failures"])

        print(f"{db_id}")
        print(f" Baseline recall: {baseline_recall:.3f} ({len(baseline_result['failures'])} failures)")
        print(f" Enriched recall: {enriched_recall:.3f} ({len(enriched_result['failures'])} failures)")
        print(f" Delta: +{delta:.3f} ({fixed} failures fixed)")
        print()

        summary_rows.append(
            {
                "db_id": db_id,
                "baseline_recall": baseline_recall,
                "enriched_recall": enriched_recall,
                "delta": delta,
                "baseline_failures": len(baseline_result["failures"]),
                "enriched_failures": len(enriched_result["failures"]),
                "failures_fixed": fixed,
            }
        )

    if args.output:
        args.output.write_text(json.dumps(summary_rows, indent=2, default=str), encoding="utf-8")
        print(f"Summary written to {args.output}")


if __name__ == "__main__":
    main()
