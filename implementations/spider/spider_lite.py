from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from octo.database import SQLColumnProfile, SQLForeignKey, SQLSchemaSnapshot, SQLTableProfile
from .spider import SpiderSchemaCoprocessor
from octo.world_state import WorldModel


def _coerce_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


@dataclass
class SpiderLiteTask:
    task_id: str
    db_id: str
    question: str
    dialect: str = ""
    evidence: str = ""
    gold_sql: str = ""
    gold_tables: list[str] = field(default_factory=list)
    external_knowledge_files: list[str] = field(default_factory=list)
    raw_record: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "SpiderLiteTask":
        task_id = _coerce_string(
            record.get("instance_id")
            or record.get("id")
            or record.get("question_id")
            or record.get("task_id")
            or "task",
        )
        db_id = _coerce_string(
            record.get("db_id")
            or record.get("db")
            or record.get("database_id")
            or "unknown_db",
        )
        question = _coerce_string(
            record.get("question")
            or record.get("query")
            or record.get("instruction")
            or "",
        )
        return cls(
            task_id=task_id,
            db_id=db_id,
            question=question,
            dialect=_coerce_string(record.get("db_type") or record.get("dialect")),
            evidence=_coerce_string(record.get("evidence") or record.get("external_knowledge")),
            gold_sql=_coerce_string(record.get("query") or record.get("gold_sql")),
            gold_tables=_coerce_string_list(
                record.get("gold_tables")
                or record.get("relevant_tables")
                or record.get("tables")
            )
            or _coerce_string_list(record.get("oracle_tables")),
            external_knowledge_files=_coerce_string_list(
                record.get("external_knowledge")
                or record.get("evidence_files")
                or record.get("docs")
            ),
            raw_record=dict(record),
        )


class SpiderLiteTaskLoader:
    def load(self, path: str | Path) -> list[SpiderLiteTask]:
        path = Path(path)
        if path.suffix == ".jsonl":
            records = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                records = payload
            elif isinstance(payload, dict) and isinstance(payload.get("examples"), list):
                records = payload["examples"]
            else:
                raise ValueError(f"Unsupported Spider Lite payload format in {path}")
        return [SpiderLiteTask.from_record(record) for record in records]


class SpiderLiteWorkspace:
    def __init__(self, repo_root: str | Path):
        self.repo_root = Path(repo_root)

    def resolve_tasks_path(self) -> Path:
        candidates = [
            self.repo_root / "spider2-lite" / "spider2-lite.jsonl",
            self.repo_root / "spider2-lite.jsonl",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(
            f"Could not find spider2-lite.jsonl under {self.repo_root}"
        )

    def load_tasks(self) -> list[SpiderLiteTask]:
        return SpiderLiteTaskLoader().load(self.resolve_tasks_path())

    def resolve_gold_exec_result_paths(self, instance_id: str) -> list[Path]:
        root = self.repo_root / "spider2-lite" / "evaluation_suite" / "gold" / "exec_result"
        base_path = root / f"{instance_id}.csv"
        if base_path.exists():
            return [base_path]
        pattern = re.compile(rf"^{re.escape(instance_id)}(_[a-z])?\.csv$")
        return sorted(path for path in root.iterdir() if path.is_file() and pattern.match(path.name))

    def resolve_external_knowledge_paths(self, task: SpiderLiteTask) -> list[Path]:
        roots = [
            self.repo_root / "spider2-lite",
            self.repo_root / "spider2-lite" / "resource",
            self.repo_root / "spider2-lite" / "resources",
            self.repo_root / "spider2" / "resource",
            self.repo_root / "spider2" / "resource" / "databases" / "local",
        ]
        resolved: list[Path] = []
        for filename in task.external_knowledge_files:
            for root in roots:
                candidate = root / filename
                if candidate.exists():
                    resolved.append(candidate)
                    break
        return resolved

    def load_oracle_tables(self) -> dict[str, list[str]]:
        candidates = [
            self.repo_root / "methods" / "gold-tables" / "spider2-lite-gold-tables.jsonl",
            self.repo_root / "spider2-lite-gold-tables.jsonl",
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

    def list_sqlite_metadata_databases(self) -> list[str]:
        root = self.repo_root / "spider2-lite" / "resource" / "databases" / "sqlite"
        if not root.exists():
            return []
        return sorted(item.name for item in root.iterdir() if item.is_dir())

    def resolve_sqlite_metadata_dir(self, db_id: str) -> Path:
        root = self.repo_root / "spider2-lite" / "resource" / "databases" / "sqlite"
        if not root.exists():
            raise FileNotFoundError(f"SQLite metadata root not found under {self.repo_root}")

        normalized_target = _normalize_db_name(db_id)
        candidates = sorted(item for item in root.iterdir() if item.is_dir())
        for candidate in candidates:
            if _normalize_db_name(candidate.name) == normalized_target:
                return candidate
        raise FileNotFoundError(f"Could not resolve SQLite metadata directory for db_id={db_id}")

    def load_sqlite_metadata_documents(self, db_id: str) -> dict[str, str]:
        metadata_dir = self.resolve_sqlite_metadata_dir(db_id)
        documents: dict[str, str] = {}
        ddl_path = metadata_dir / "DDL.csv"
        if ddl_path.exists():
            documents["DDL.csv"] = ddl_path.read_text(encoding="utf-8")
        for path in sorted(metadata_dir.glob("*.json")):
            documents[path.name] = path.read_text(encoding="utf-8")
        return documents

    def resolve_local_sqlite_db(self, db_id: str) -> Path:
        root = self.repo_root / "spider2-lite" / "resource" / "databases" / "spider2-localdb"
        if not root.exists():
            raise FileNotFoundError(f"Local Spider2 SQLite root not found under {self.repo_root}")

        normalized_target = _normalize_db_name(db_id)
        candidates = sorted(
            candidate
            for candidate in root.rglob("*.sqlite")
            if "__MACOSX" not in candidate.parts and not candidate.name.startswith("._")
        )
        for candidate in candidates:
            if _normalize_db_name(candidate.stem) == normalized_target:
                return candidate
        raise FileNotFoundError(f"Could not resolve local SQLite database for db_id={db_id}")


class SpiderLiteSQLiteMetadataLoader:
    def load(self, metadata_dir: str | Path, *, db_id: str | None = None) -> SQLSchemaSnapshot:
        metadata_dir = Path(metadata_dir)
        sample_rows_by_table = self._load_table_json(metadata_dir)
        columns_by_table = {
            table_name: self._columns_from_metadata(table_name, payload)
            for table_name, payload in sample_rows_by_table.items()
        }
        foreign_keys = self._infer_foreign_keys(columns_by_table)
        tables = [
            SQLTableProfile(
                schema="main",
                name=table_name,
                columns=columns_by_table[table_name],
            )
            for table_name in sorted(columns_by_table)
        ]
        return SQLSchemaSnapshot(
            database_name=db_id or metadata_dir.name,
            tables=tables,
            foreign_keys=foreign_keys,
        )

    def _load_table_json(self, metadata_dir: Path) -> dict[str, dict[str, Any]]:
        payloads: dict[str, dict[str, Any]] = {}
        for path in sorted(metadata_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            table_name = str(payload.get("table_name") or path.stem)
            payloads[table_name] = payload
        if not payloads:
            raise FileNotFoundError(f"No table metadata JSON files found in {metadata_dir}")
        return payloads

    def _columns_from_metadata(
        self,
        table_name: str,
        payload: dict[str, Any],
    ) -> list[SQLColumnProfile]:
        column_names = [str(name) for name in payload.get("column_names", [])]
        column_types = [str(value) for value in payload.get("column_types", [])]
        sample_rows = payload.get("sample_rows", []) or []

        columns: list[SQLColumnProfile] = []
        for index, column_name in enumerate(column_names):
            sample_values: list[str] = []
            for row in sample_rows[:5]:
                if column_name in row and row[column_name] is not None:
                    sample_values.append(str(row[column_name]))
            columns.append(
                SQLColumnProfile(
                    schema="main",
                    table=table_name,
                    name=column_name,
                    data_type=column_types[index] if index < len(column_types) else "TEXT",
                    is_nullable=True,
                    ordinal_position=index + 1,
                    sample_values=sample_values[:3],
                )
            )
        return columns

    def _infer_foreign_keys(
        self,
        columns_by_table: dict[str, list[SQLColumnProfile]],
    ) -> list[SQLForeignKey]:
        primary_keys: dict[str, str] = {}
        by_column_name: dict[str, list[str]] = {}

        for table_name, columns in columns_by_table.items():
            pk_name = _guess_primary_key(table_name, columns)
            if pk_name:
                primary_keys[table_name] = pk_name
                normalized = _normalize_identifier(pk_name)
                by_column_name.setdefault(normalized, []).append(table_name)

        foreign_keys: list[SQLForeignKey] = []
        seen: set[tuple[str, str, str]] = set()
        for table_name, columns in columns_by_table.items():
            for column in columns:
                normalized_column = _normalize_identifier(column.name)
                if normalized_column in {"id", _normalize_identifier(primary_keys.get(table_name, ""))}:
                    continue
                candidate_targets = by_column_name.get(normalized_column, [])
                for target_table in candidate_targets:
                    if target_table == table_name:
                        continue
                    key = (table_name, column.name, target_table)
                    if key in seen:
                        continue
                    seen.add(key)
                    foreign_keys.append(
                        SQLForeignKey(
                            source_schema="main",
                            source_table=table_name,
                            source_column=column.name,
                            target_schema="main",
                            target_table=target_table,
                            target_column=primary_keys[target_table],
                            constraint_name=f"fk_{table_name}_{column.name}_{target_table}",
                        )
                    )
        return foreign_keys


class SpiderLiteSQLiteDatabaseLoader:
    def load(
        self,
        db_path: str | Path,
        *,
        db_id: str | None = None,
        sample_limit: int = 3,
    ) -> SQLSchemaSnapshot:
        db_path = Path(db_path)
        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        try:
            table_rows = connection.execute(
                """
                SELECT name, type
                FROM sqlite_master
                WHERE type IN ('table', 'view')
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()

            tables: list[SQLTableProfile] = []
            foreign_keys: list[SQLForeignKey] = []
            for row in table_rows:
                table_name = row["name"]
                columns = self._load_columns(connection, table_name, sample_limit=sample_limit)
                tables.append(
                    SQLTableProfile(
                        schema="main",
                        name=table_name,
                        description=row["type"],
                        columns=columns,
                    )
                )
                foreign_keys.extend(self._load_foreign_keys(connection, table_name))
            return SQLSchemaSnapshot(
                database_name=db_id or db_path.stem,
                tables=tables,
                foreign_keys=foreign_keys,
            )
        finally:
            connection.close()

    def _load_columns(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        *,
        sample_limit: int,
    ) -> list[SQLColumnProfile]:
        pragma_rows = connection.execute(
            f"PRAGMA table_info({_quote_sqlite_ident(table_name)})"
        ).fetchall()
        columns: list[SQLColumnProfile] = []
        for row in pragma_rows:
            column_name = row["name"]
            sample_values = self._fetch_sample_values(
                connection,
                table_name,
                column_name,
                limit=sample_limit,
            )
            columns.append(
                SQLColumnProfile(
                    schema="main",
                    table=table_name,
                    name=column_name,
                    data_type=str(row["type"] or "TEXT"),
                    is_nullable=not bool(row["notnull"]),
                    ordinal_position=int(row["cid"]) + 1,
                    sample_values=sample_values,
                )
            )
        return columns

    def _load_foreign_keys(
        self,
        connection: sqlite3.Connection,
        table_name: str,
    ) -> list[SQLForeignKey]:
        pragma_rows = connection.execute(
            f"PRAGMA foreign_key_list({_quote_sqlite_ident(table_name)})"
        ).fetchall()
        foreign_keys: list[SQLForeignKey] = []
        for row in pragma_rows:
            foreign_keys.append(
                SQLForeignKey(
                    source_schema="main",
                    source_table=table_name,
                    source_column=str(row["from"]),
                    target_schema="main",
                    target_table=str(row["table"]),
                    target_column=str(row["to"]),
                    constraint_name=f"fk_{table_name}_{row['from']}_{row['table']}",
                )
            )
        return foreign_keys

    def _fetch_sample_values(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        *,
        limit: int,
    ) -> list[str]:
        try:
            rows = connection.execute(
                f"""
                SELECT DISTINCT {_quote_sqlite_ident(column_name)} AS sample_value
                FROM {_quote_sqlite_ident(table_name)}
                WHERE {_quote_sqlite_ident(column_name)} IS NOT NULL
                LIMIT {int(limit)}
                """
            ).fetchall()
        except sqlite3.DatabaseError:
            return []
        return [str(row["sample_value"]) for row in rows if row["sample_value"] is not None]


def _normalize_identifier(value: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "_", snake.lower()).strip("_")


def _normalize_db_name(value: str) -> str:
    return _normalize_identifier(value)


def _quote_sqlite_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def enrich_world_with_spider_sqlite_metadata(
    world_model: WorldModel,
    *,
    db_id: str,
    metadata_documents: dict[str, str],
) -> WorldModel:
    database_node_id = f"database:{db_id}"
    if database_node_id not in world_model.nodes:
        return world_model

    ddl_text = metadata_documents.get("DDL.csv")
    if ddl_text:
        ddl_node_id = f"document:{db_id}:ddl"
        world_model.upsert_node(
            ddl_node_id,
            label=f"{db_id} DDL",
            type="document",
            summary=_truncate_text(ddl_text, 800),
            keywords=["ddl", "schema", db_id],
            source_file="DDL.csv",
        )
        world_model.add_edge(database_node_id, "has_document", ddl_node_id, score=0.94)

    for filename, text in metadata_documents.items():
        if not filename.endswith(".json"):
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        table_name = str(payload.get("table_name") or Path(filename).stem)
        sample_rows = payload.get("sample_rows") or []
        column_names = [str(name) for name in payload.get("column_names", [])]
        summary_parts = [f"Metadata for table {table_name}."]
        if column_names:
            summary_parts.append("Columns: " + ", ".join(column_names[:12]) + ".")
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
    normalized = _normalize_identifier(table_name)
    for node_id, attrs in world_model.nodes.items():
        if attrs.get("type") != "table":
            continue
        label = str(attrs.get("label", ""))
        if _normalize_identifier(label.split(".")[-1]) == normalized:
            return node_id
    return None


def load_gold_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _truncate_text(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def _singularize(name: str) -> str:
    if name.endswith("ies") and len(name) > 3:
        return name[:-3] + "y"
    if name.endswith("s") and not name.endswith("ss") and len(name) > 3:
        return name[:-1]
    return name


def _guess_primary_key(table_name: str, columns: list[SQLColumnProfile]) -> str | None:
    normalized_table = _normalize_identifier(table_name)
    singular_table = _singularize(normalized_table)
    candidate_names = [
        f"{singular_table}_id",
        f"{normalized_table}_id",
        "id",
    ]
    normalized_columns = {_normalize_identifier(column.name): column.name for column in columns}
    for candidate in candidate_names:
        if candidate in normalized_columns:
            return normalized_columns[candidate]
    for column in columns:
        if _normalize_identifier(column.name).endswith("_id"):
            return column.name
    return columns[0].name if columns else None


@dataclass
class SpiderLiteBenchmarkAdapter:
    snapshots_by_db: dict[str, SQLSchemaSnapshot]
    worlds_by_db: dict[str, WorldModel] | None = None
    top_k: int = 8

    def run_task(self, task: SpiderLiteTask) -> dict[str, Any]:
        if task.db_id not in self.snapshots_by_db:
            raise KeyError(f"No schema snapshot registered for db_id={task.db_id}")

        snapshot = self.snapshots_by_db[task.db_id]
        world_model = (self.worlds_by_db or {}).get(task.db_id)
        coprocessor = SpiderSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"spider-lite:{task.db_id}",
            top_k=self.top_k,
            world_model=world_model,
        )
        result = coprocessor.ask(task.question, trace=True)

        candidate_tables = result.get("constraints", {}).get("candidate_tables", [])
        candidate_join_path = result.get("constraints", {}).get("candidate_join_path", [])
        table_recall = None
        if task.gold_tables:
            normalized_gold = {table.lower() for table in task.gold_tables}
            normalized_predicted = {table.lower() for table in candidate_tables}
            matched = normalized_gold & normalized_predicted
            table_recall = len(matched) / max(1, len(normalized_gold))

        return {
            "task_id": task.task_id,
            "db_id": task.db_id,
            "question": task.question,
            "dialect": task.dialect,
            "evidence": task.evidence,
            "gold_tables": list(task.gold_tables),
            "candidate_tables": candidate_tables,
            "candidate_join_path": candidate_join_path,
            "hypotheses": result.get("hypotheses", []),
            "table_recall": table_recall,
            "raw_result": result,
        }

    def evaluate_tasks(self, tasks: list[SpiderLiteTask]) -> dict[str, Any]:
        per_task: list[dict[str, Any]] = []
        per_db: dict[str, dict[str, Any]] = {}
        total_with_gold = 0
        total_recall = 0.0

        for task in tasks:
            if task.db_id not in self.snapshots_by_db:
                continue
            result = self.run_task(task)
            per_task.append(result)

            bucket = per_db.setdefault(
                task.db_id,
                {
                    "db_id": task.db_id,
                    "tasks": 0,
                    "tasks_with_gold_tables": 0,
                    "average_table_recall": None,
                },
            )
            bucket["tasks"] += 1
            if result["table_recall"] is not None:
                bucket["tasks_with_gold_tables"] += 1
                total_with_gold += 1
                total_recall += float(result["table_recall"])
                running = bucket.get("_table_recall_total", 0.0) + float(result["table_recall"])
                bucket["_table_recall_total"] = running

        for bucket in per_db.values():
            if bucket["tasks_with_gold_tables"]:
                bucket["average_table_recall"] = (
                    bucket["_table_recall_total"] / bucket["tasks_with_gold_tables"]
                )
            bucket.pop("_table_recall_total", None)

        return {
            "tasks_evaluated": len(per_task),
            "tasks_with_gold_tables": total_with_gold,
            "average_table_recall": (
                total_recall / total_with_gold if total_with_gold else None
            ),
            "per_db": sorted(per_db.values(), key=lambda item: item["db_id"]),
            "tasks": per_task,
        }
