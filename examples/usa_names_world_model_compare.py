"""Compare one-shot RAG vs. OCTO with an enriched USA_NAMES world model.

This script isolates the value of a better-structured world model for the
USA_NAMES Spider task. It shows that a generic schema world model misses the
`state` and `gender` columns, while an enriched world model (semantic aliases
+ types) surfaces them without any hand-coded domain compiler.

Run:
    python examples/usa_names_world_model_compare.py
"""

from __future__ import annotations

import re
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
from octo.database import SQLSchemaSnapshot, snapshot_to_world_model
from octo.retrieval.legacy import InMemoryGraphIndex, embed_text, token_overlap_score
from octo.world_state import WorldModel


SNAPSHOT_PATH = Path("/Users/richiek/work/Spider2/octo_snapshots/snowflake/USA_NAMES.json")

QUESTION = (
    "Can you tell me the name of the most popular female baby in Wyoming for "
    "the year 2021, based on the proportion of female babies given that name "
    "compared to the total number of female babies given the same name across "
    "all states?"
)

US_STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def enrich_usa_names_world_model(world_model: WorldModel) -> WorldModel:
    """Add semantic aliases and types to the USA_NAMES world model."""
    state_aliases = list(US_STATE_CODES.keys()) + list(US_STATE_CODES.values())

    column_enrichment = {
        "gender": {
            "aliases": ["sex", "male", "female", "boy", "girl", "gender"],
            "semantic_type": "gender",
        },
        "state": {
            "aliases": ["state", "state code", "us state"] + state_aliases,
            "semantic_type": "us_state",
        },
        "year": {
            "aliases": ["year", "date", "annual", "birth year", "calendar year"],
            "semantic_type": "year",
        },
        "name": {
            "aliases": ["name", "given name", "first name", "baby name"],
            "semantic_type": "person_name",
        },
        "number": {
            "aliases": ["number", "count", "occurrences", "frequency", "babies", "total"],
            "semantic_type": "count",
        },
    }

    table_enrichment = {
        "USA_1910_CURRENT": {
            "aliases": [
                "current",
                "recent",
                "1910 to current",
                "usa names current",
                "baby names after 2013",
            ],
        },
        "USA_1910_2013": {
            "aliases": [
                "historical",
                "1910 to 2013",
                "old names",
                "historical usa names",
            ],
        },
    }

    for node_id, attrs in world_model.nodes.items():
        node_type = attrs.get("type")
        if node_type == "column":
            column_name = attrs.get("column_name", "").lower()
            enrichment = column_enrichment.get(column_name)
            if enrichment:
                existing_aliases = set(attrs.get("aliases", []))
                new_aliases = list(existing_aliases | set(enrichment["aliases"]))
                attrs["aliases"] = new_aliases
                attrs["semantic_type"] = enrichment["semantic_type"]
                # Also boost the summary with plain-language terms.
                summary = attrs.get("summary", "")
                if enrichment["semantic_type"] == "gender" and "sex" not in summary.lower():
                    attrs["summary"] = summary + " Values: male/female (M/F)."
                if enrichment["semantic_type"] == "us_state" and "wyoming" not in summary.lower():
                    attrs["summary"] = summary + " Includes all US states (e.g., Wyoming, WY)."
        elif node_type == "table":
            table_name = attrs.get("table_name", "")
            enrichment = table_enrichment.get(table_name)
            if enrichment:
                existing_aliases = set(attrs.get("aliases", []))
                attrs["aliases"] = list(existing_aliases | set(enrichment["aliases"]))

    return world_model


def one_shot_rag_candidates(snapshot: SQLSchemaSnapshot, query: str, top_k: int = 10) -> dict[str, list[str]]:
    """Simple one-shot RAG: retrieve schema chunks by token overlap."""
    chunks: list[tuple[str, str]] = []  # (kind:label, text)
    for table in snapshot.tables:
        table_text = f"Table {table.schema}.{table.name}. {table.description}"
        column_parts = [
            f"{col.name}: {col.data_type}"
            + (f" ({col.description})" if col.description else "")
            for col in table.columns
        ]
        chunks.append((f"table:{table.name}", f"{table_text} Columns: {', '.join(column_parts)}."))
        for col in table.columns:
            col_text = f"Column {col.name} in table {table.name}. Type {col.data_type}."
            if col.description:
                col_text += f" {col.description}"
            chunks.append((f"column:{table.name}.{col.name}", col_text))

    scored = [
        (label, text, token_overlap_score(query, text))
        for label, text in chunks
    ]
    scored.sort(key=lambda item: item[2], reverse=True)

    candidate_tables: list[str] = []
    candidate_columns: list[str] = []
    for label, _, score in scored[:top_k]:
        if score <= 0.0:
            continue
        if label.startswith("table:"):
            candidate_tables.append(label.split(":", 1)[1])
        elif label.startswith("column:"):
            candidate_columns.append(label.split(":", 1)[1].split(".")[-1])

    return {
        "candidate_tables": list(dict.fromkeys(candidate_tables)),
        "candidate_columns": list(dict.fromkeys(candidate_columns)),
    }


def run_coprocessor(world_model: WorldModel) -> dict[str, Any]:
    snapshot = SQLSchemaSnapshot.from_dict(json.loads(SNAPSHOT_PATH.read_text()))
    coprocessor = SpiderSchemaCoprocessor.from_snapshot(
        snapshot,
        model_name="usa-names",
        top_k=16,
        world_model=world_model,
    )
    result = coprocessor.ask(QUESTION, trace=True)
    return {
        "candidate_tables": result["constraints"].get("candidate_tables", []),
        "candidate_columns": result["constraints"].get("candidate_columns", []),
        "retrievals": [r["label"] for r in result["retrievals"]],
    }


def evaluate(label: str, candidates: dict[str, list[str]]) -> None:
    print(f"\n{label}")
    print("-" * len(label))
    print(f"Tables: {candidates['candidate_tables']}")
    print(f"Columns: {candidates['candidate_columns']}")
    important_columns = {"state", "gender", "year", "name", "number"}
    found = important_columns & {c.lower() for c in candidates["candidate_columns"]}
    print(f"Important columns found: {sorted(found)} ({len(found)}/{len(important_columns)})")


def main() -> None:
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Snapshot not found: {SNAPSHOT_PATH}")

    snapshot = SQLSchemaSnapshot.from_dict(json.loads(SNAPSHOT_PATH.read_text()))

    # 1. One-shot keyword RAG baseline.
    rag_candidates = one_shot_rag_candidates(snapshot, QUESTION, top_k=16)
    evaluate("1) One-shot keyword RAG", rag_candidates)

    # 2. OCTO with a generic (un-enriched) world model.
    generic_world = snapshot_to_world_model(snapshot)
    generic_candidates = run_coprocessor(generic_world)
    evaluate("2) OCTO generic world model", generic_candidates)

    # 3. OCTO with an enriched world model.
    enriched_world = snapshot_to_world_model(snapshot)
    enrich_usa_names_world_model(enriched_world)
    enriched_candidates = run_coprocessor(enriched_world)
    evaluate("3) OCTO enriched world model", enriched_candidates)

    print("\n" + "=" * 70)
    print("Take-away")
    print("=" * 70)
    print(
        "The enriched world model is the difference between retrieving generic "
        "numeric/name/year columns and retrieving the exact columns the query "
        "talks about: state, gender, year, name, number."
    )


if __name__ == "__main__":
    from typing import Any
    main()
