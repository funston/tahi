from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bender.database import SQLColumnProfile, SQLSchemaSnapshot, SQLTableProfile
from .spider_lite import SpiderLiteTask, SpiderLiteTaskLoader
from bender.world_state import WorldModel


def _truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


@dataclass
class SpiderSnowWorkspace:
    repo_root: Path | str

    def __post_init__(self) -> None:
        self.repo_root = Path(self.repo_root)

    def resolve_tasks_path(self) -> Path:
        candidates = [
            self.repo_root / "spider2-snow" / "spider2-snow.jsonl",
            self.repo_root / "spider2-snow.jsonl",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not find spider2-snow.jsonl under {self.repo_root}")

    def load_tasks(self) -> list[SpiderLiteTask]:
        return SpiderLiteTaskLoader().load(self.resolve_tasks_path())

    def load_oracle_tables(self) -> dict[str, list[str]]:
        candidates = [
            self.repo_root / "methods" / "gold-tables" / "spider2-snow-gold-tables.jsonl",
            self.repo_root / "spider2-snow-gold-tables.jsonl",
        ]
        for candidate in candidates:
            if candidate.exists():
                oracle_map: dict[str, list[str]] = {}
                for task in SpiderLiteTaskLoader().load(candidate):
                    if task.gold_tables:
                        oracle_map[task.task_id] = list(task.gold_tables)
                return oracle_map
        return {}

    def attach_oracle_tables(self, tasks: list[SpiderLiteTask]) -> list[SpiderLiteTask]:
        oracle_tables = self.load_oracle_tables()
        if not oracle_tables:
            return tasks
        enriched: list[SpiderLiteTask] = []
        for task in tasks:
            if task.gold_tables:
                enriched.append(task)
                continue
            tables = oracle_tables.get(task.task_id, [])
            enriched.append(
                SpiderLiteTask(
                    task_id=task.task_id,
                    db_id=task.db_id,
                    question=task.question,
                    dialect=task.dialect,
                    evidence=task.evidence,
                    gold_sql=task.gold_sql,
                    gold_tables=list(tables),
                    external_knowledge_files=list(task.external_knowledge_files),
                    raw_record=dict(task.raw_record),
                )
            )
        return enriched

    def resolve_database_metadata_dir(self, db_id: str) -> Path:
        root = self.repo_root / "spider2-snow" / "resource" / "databases"
        if (root / db_id).exists():
            return root / db_id
        # Case-insensitive fallback
        for child in root.iterdir():
            if child.is_dir() and child.name.upper() == db_id.upper():
                return child
        raise FileNotFoundError(f"Could not resolve Snowflake metadata directory for db_id={db_id}")

    def load_snapshot_manifest(self, path: str | Path) -> dict[str, SQLSchemaSnapshot]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        manifest = payload.get("snapshots", payload)
        snapshots: dict[str, SQLSchemaSnapshot] = {}
        for db_id, snapshot_path in manifest.items():
            resolved = (self.repo_root / snapshot_path).resolve()
            snapshot_payload = json.loads(resolved.read_text(encoding="utf-8"))
            snapshots[str(db_id)] = SQLSchemaSnapshot.from_dict(snapshot_payload)
        return snapshots

    def load_world_cache_index(self, path: str | Path) -> dict[str, WorldModel]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        manifest = payload.get("worlds", payload)
        worlds: dict[str, WorldModel] = {}
        for db_id, world_path in manifest.items():
            resolved = (self.repo_root / world_path).resolve()
            worlds[str(db_id)] = WorldModel.load_json(resolved)
        return worlds

    def load_metadata_documents(self, db_id: str) -> dict[str, str]:
        db_root = self.resolve_database_metadata_dir(db_id)
        documents: dict[str, str] = {}
        for path in sorted(db_root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".json", ".csv", ".md"}:
                continue
            key = str(path.relative_to(db_root))
            documents[key] = path.read_text(encoding="utf-8")
        return documents

    def resolve_gold_exec_result_paths(self, instance_id: str) -> list[Path]:
        root = self.repo_root / "spider2-snow" / "evaluation_suite" / "gold" / "exec_result"
        pattern = f"{instance_id}"
        return sorted(root.glob(f"{pattern}*.csv"))


class SpiderSnowflakeMetadataLoader:
    def load(self, metadata_root: str | Path, *, db_id: str | None = None) -> SQLSchemaSnapshot:
        metadata_root = Path(metadata_root)
        tables: list[SQLTableProfile] = []
        for schema_dir in sorted(item for item in metadata_root.iterdir() if item.is_dir()):
            for table_json in sorted(schema_dir.glob("*.json")):
                payload = json.loads(table_json.read_text(encoding="utf-8"))
                table_fullname = str(payload.get("table_fullname") or "")
                parts = table_fullname.split(".")
                if len(parts) >= 3:
                    database_name, schema_name, table_name = parts[-3], parts[-2], parts[-1]
                else:
                    database_name = db_id or metadata_root.name
                    schema_name = schema_dir.name
                    table_name = str(payload.get("table_name") or table_json.stem)
                column_names = [str(name) for name in payload.get("column_names", [])]
                column_types = [str(value) for value in payload.get("column_types", [])]
                descriptions = [str(value) for value in payload.get("description", [])]
                sample_rows = payload.get("sample_rows", []) or []
                columns: list[SQLColumnProfile] = []
                for index, column_name in enumerate(column_names):
                    sample_values: list[str] = []
                    for row in sample_rows[:5]:
                        if column_name in row and row[column_name] is not None:
                            sample_values.append(str(row[column_name]))
                    columns.append(
                        SQLColumnProfile(
                            schema=schema_name,
                            table=table_name,
                            name=column_name,
                            data_type=column_types[index] if index < len(column_types) else "TEXT",
                            is_nullable=True,
                            ordinal_position=index + 1,
                            description=descriptions[index] if index < len(descriptions) else "",
                            sample_values=sample_values[:3],
                        )
                    )
                tables.append(
                    SQLTableProfile(
                        schema=schema_name,
                        name=table_name,
                        columns=columns,
                    )
                )
        return SQLSchemaSnapshot(
            database_name=db_id or (database_name if tables else metadata_root.name),
            tables=tables,
            foreign_keys=[],
        )


def enrich_world_with_spider_snow_metadata(
    world_model: WorldModel,
    *,
    db_id: str,
    metadata_documents: dict[str, str],
) -> WorldModel:
    database_node_id = f"database:{db_id}"
    if database_node_id not in world_model.nodes:
        return world_model

    for filename, text in metadata_documents.items():
        if filename.endswith("DDL.csv"):
            ddl_node_id = f"document:{db_id}:ddl"
            world_model.upsert_node(
                ddl_node_id,
                label=f"{db_id} DDL",
                type="document",
                summary=_truncate_text(text, 1200),
                keywords=[db_id, "ddl", "schema", "snowflake"],
                source_file=filename,
            )
            world_model.add_edge(database_node_id, "has_document", ddl_node_id, score=0.94)
            continue

        if not filename.endswith(".json"):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        table_fullname = str(payload.get("table_fullname") or payload.get("table_name") or filename)
        table_name = table_fullname.split(".")[-1]
        column_names = [str(name) for name in payload.get("column_names", [])]
        summary_parts = [f"Metadata for Snowflake table {table_fullname}."]
        if column_names:
            summary_parts.append("Columns: " + ", ".join(column_names[:12]) + ".")
        sample_rows = payload.get("sample_rows") or []
        if sample_rows:
            sample = sample_rows[0]
            preview = ", ".join(f"{key}={sample[key]}" for key in list(sample)[:5])
            summary_parts.append(f"Sample row: {preview}.")
        node_id = f"document:{db_id}:table:{table_name}"
        world_model.upsert_node(
            node_id,
            label=f"{table_name} metadata",
            type="document",
            summary=" ".join(summary_parts),
            keywords=[db_id, table_name, "metadata", *column_names[:8]],
            source_file=filename,
        )
        world_model.add_edge(database_node_id, "has_document", node_id, score=0.9)
        table_node_id = _find_table_node_id(world_model, table_name)
        if table_node_id:
            world_model.add_edge(table_node_id, "has_metadata_document", node_id, score=0.93)
    return world_model


def _find_table_node_id(world_model: WorldModel, table_name: str) -> str | None:
    normalized = table_name.lower()
    for node_id, attrs in world_model.nodes.items():
        if attrs.get("type") != "table":
            continue
        label = str(attrs.get("label", ""))
        if label.split(".")[-1].lower() == normalized:
            return node_id
    return None


def load_gold_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
