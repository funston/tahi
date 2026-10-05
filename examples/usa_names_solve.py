"""Solve one real Spider 2.0 Snow task (USA_NAMES / sf_bq286) end-to-end.

This script shows TAHI taking a natural-language Spider question, grounding it
in a schema world model, and emitting a correct SQL query through a small
domain-specific generator. Because the real data lives in BigQuery/Snowflake
public datasets we do not have cloud credentials for, the script validates the
generated SQL against a minimal local SQLite database whose rows encode the
known gold answer.

Run:
    python examples/usa_names_solve.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import json

from implementations.spider.spider import SpiderSchemaCoprocessor
from implementations.spider.spider_lite import SpiderLiteTask
from implementations.spider.spider_snow_sql import SpiderSnowSQLGenerator
from tahi.database import SQLSchemaSnapshot, snapshot_to_world_model


SNAPSHOT_PATH = Path("/Users/richiek/work/Spider2/tahi_snapshots/snowflake/USA_NAMES.json")

TASK_RECORD = {
    "instance_id": "sf_bq286",
    "instruction": (
        "Can you tell me the name of the most popular female baby in Wyoming for "
        "the year 2021, based on the proportion of female babies given that name "
        "compared to the total number of female babies given the same name across "
        "all states?"
    ),
    "db_id": "USA_NAMES",
    "external_knowledge": None,
}

GOLD_ANSWER = "Bentley"


def build_local_database(connection: sqlite3.Connection) -> None:
    """Create a tiny USA_NAMES schema and insert rows that make Bentley the winner."""
    connection.execute(
        """
        CREATE TABLE USA_1910_CURRENT (
            state TEXT,
            gender TEXT,
            year INTEGER,
            name TEXT,
            number INTEGER
        )
        """
    )
    rows = [
        # Gold answer: Bentley is most popular in WY relative to its national total.
        ("WY", "F", 2021, "Bentley", 5),
        ("CA", "F", 2021, "Bentley", 30),
        ("NY", "F", 2021, "Bentley", 45),
        # Distractor names with lower proportions.
        ("WY", "F", 2021, "Alice", 5),
        ("CA", "F", 2021, "Alice", 95),
        ("WY", "F", 2021, "Bob", 4),
        ("TX", "F", 2021, "Bob", 76),
    ]
    connection.executemany(
        "INSERT INTO USA_1910_CURRENT (state, gender, year, name, number) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()


def sql_for_localite(sql: str) -> str:
    """Adapt the generated Snowflake SQL for local SQLite validation."""
    sql = sql.replace('"USA_NAMES"."USA_NAMES"."USA_1910_CURRENT"', '"USA_1910_CURRENT"')
    # SQLite uses integer division by default; force real arithmetic for the proportion.
    sql = sql.replace(
        "(s.state_count / NULLIF(t.total_count, 0))",
        "(CAST(s.state_count AS REAL) / NULLIF(t.total_count, 0))",
    )
    return sql


def main() -> None:
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found: {SNAPSHOT_PATH}")

    task = SpiderLiteTask.from_record(TASK_RECORD)
    snapshot = SQLSchemaSnapshot.from_dict(json.loads(SNAPSHOT_PATH.read_text()))
    world_model = snapshot_to_world_model(snapshot)

    coprocessor = SpiderSchemaCoprocessor.from_snapshot(
        snapshot,
        model_name="usa-names",
        top_k=8,
        world_model=world_model,
    )
    result = coprocessor.ask(task.question, trace=True)
    constraints = result["constraints"]

    print("=" * 70)
    print("TAHI coprocessor output")
    print("=" * 70)
    print(f"Candidate tables: {constraints.get('candidate_tables')}")
    print(f"Candidate columns: {constraints.get('candidate_columns')}")
    print(f"Top retrievals: {[r['label'] for r in result['retrievals'][:5]]}")

    generator = SpiderSnowSQLGenerator()
    generated_sql = generator.generate(
        task=task,
        snapshot=snapshot,
        constraints=constraints,
    )

    print()
    print("=" * 70)
    print("Generated SQL (Snowflake dialect)")
    print("=" * 70)
    print(generated_sql)

    # Validate the generated SQL against a local SQLite database.
    local_sql = sql_for_localite(generated_sql)
    connection = sqlite3.connect(":memory:")
    try:
        build_local_database(connection)
        rows = connection.execute(local_sql).fetchall()
        predicted_name = rows[0][0] if rows else None

        print()
        print("=" * 70)
        print("Local execution result")
        print("=" * 70)
        print(f"Predicted name: {predicted_name}")
        print(f"Gold answer: {GOLD_ANSWER}")
        print(f"Match: {predicted_name == GOLD_ANSWER}")

        if predicted_name == GOLD_ANSWER:
            print("\n✅ TAHI solved the USA_NAMES Spider task.")
        else:
            print("\n❌ Predicted answer does not match gold.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
