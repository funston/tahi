from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from bender.database import SQLColumnProfile, SQLForeignKey, SQLSchemaSnapshot, SQLTableProfile
from bender.sql_coprocessor import SQLSchemaCoprocessor
from bender.world_state import WorldModel


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


def _normalize_identifier(value: str) -> str:
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "_", snake.lower()).strip("_")


def _quote_sqlite_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


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
class BirdTask:
    task_id: str
    db_id: str
    question: str
    evidence: str = ""
    gold_sql: str = ""
    difficulty: str = ""
    external_knowledge_files: list[str] = field(default_factory=list)
    gold_tables: list[str] = field(default_factory=list)
    raw_record: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "BirdTask":
        return cls(
            task_id=_coerce_string(
                record.get("question_id")
                or record.get("instance_id")
                or record.get("id")
                or record.get("task_id")
                or "task"
            ),
            db_id=_coerce_string(record.get("db_id") or record.get("db") or record.get("database_id") or "unknown_db"),
            question=_coerce_string(record.get("question") or record.get("instruction") or record.get("query") or ""),
            evidence=_coerce_string(record.get("evidence") or record.get("hint") or record.get("external_knowledge")),
            gold_sql=_coerce_string(record.get("SQL") or record.get("query") or record.get("gold_sql")),
            difficulty=_coerce_string(record.get("difficulty")),
            external_knowledge_files=_coerce_string_list(
                record.get("external_knowledge")
                or record.get("evidence_files")
                or record.get("docs")
            ),
            gold_tables=_coerce_string_list(
                record.get("gold_tables")
                or record.get("relevant_tables")
                or record.get("tables")
            ),
            raw_record=dict(record),
        )


class BirdTaskLoader:
    def load(self, path: str | Path) -> list[BirdTask]:
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
                raise ValueError(f"Unsupported BIRD payload format in {path}")
        tasks: list[BirdTask] = []
        for index, record in enumerate(records, start=1):
            task = BirdTask.from_record(record)
            if task.task_id == "task":
                task.task_id = f"{task.db_id}_{index:04d}"
            tasks.append(task)
        return tasks


@dataclass
class BirdWorkspace:
    repo_root: Path | str

    def __post_init__(self) -> None:
        self.repo_root = Path(self.repo_root)

    def resolve_tasks_path(self, split: str = "mini_dev") -> Path:
        candidates = [
            self.repo_root / split / "dev.json",
            self.repo_root / split / f"{split}.json",
            self.repo_root / "dev.json",
            self.repo_root / f"{split}.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not find a BIRD task file under {self.repo_root} for split={split}")

    def load_tasks(self, split: str = "mini_dev") -> list[BirdTask]:
        return BirdTaskLoader().load(self.resolve_tasks_path(split=split))

    def resolve_database_root(self, split: str = "mini_dev") -> Path:
        candidates = [
            self.repo_root / split / "dev_databases",
            self.repo_root / split / "databases",
            self.repo_root / "dev_databases",
            self.repo_root / "databases",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not find a BIRD database root under {self.repo_root} for split={split}")

    def resolve_local_sqlite_db(self, db_id: str, split: str = "mini_dev") -> Path:
        db_root = self.resolve_database_root(split=split)
        normalized_target = _normalize_identifier(db_id)
        candidates = sorted(
            candidate
            for candidate in db_root.rglob("*.sqlite")
            if "__MACOSX" not in candidate.parts and not candidate.name.startswith("._")
        )
        for candidate in candidates:
            names = {
                _normalize_identifier(candidate.stem),
                _normalize_identifier(candidate.parent.name),
            }
            if normalized_target in names:
                return candidate
        raise FileNotFoundError(f"Could not resolve BIRD SQLite database for db_id={db_id}")

    def resolve_database_description_dir(self, db_id: str, split: str = "mini_dev") -> Path:
        db_root = self.resolve_database_root(split=split)
        normalized_target = _normalize_identifier(db_id)
        for candidate in sorted(item for item in db_root.iterdir() if item.is_dir()):
            if _normalize_identifier(candidate.name) != normalized_target:
                continue
            description_dir = candidate / "database_description"
            if description_dir.exists():
                return description_dir
        raise FileNotFoundError(f"Could not resolve BIRD database_description for db_id={db_id}")

    def load_database_documents(self, db_id: str, split: str = "mini_dev") -> dict[str, str]:
        try:
            description_dir = self.resolve_database_description_dir(db_id, split=split)
        except FileNotFoundError:
            return {}
        documents: dict[str, str] = {}
        for path in sorted(description_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".csv", ".txt", ".md", ".json"}:
                continue
            documents[str(path.relative_to(description_dir))] = path.read_text(encoding="utf-8")
        return documents

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


class BirdSQLiteDatabaseLoader:
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
            sample_values = self._fetch_sample_values(connection, table_name, column_name, limit=sample_limit)
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
        rows = connection.execute(
            f"""
            SELECT {_quote_sqlite_ident(column_name)}
            FROM {_quote_sqlite_ident(table_name)}
            WHERE {_quote_sqlite_ident(column_name)} IS NOT NULL
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [str(row[0]) for row in rows]


def enrich_world_with_bird_metadata(
    world_model: WorldModel,
    *,
    db_id: str,
    metadata_documents: dict[str, str],
) -> WorldModel:
    database_node_id = f"database:{db_id}"
    if database_node_id not in world_model.nodes:
        return world_model

    for filename, text in metadata_documents.items():
        node_id = f"document:{db_id}:{_normalize_identifier(filename)}"
        label = f"{db_id} {Path(filename).stem}"
        world_model.upsert_node(
            node_id,
            label=label,
            type="document",
            summary=_truncate_text(text, 1200),
            keywords=[db_id, "bird", "metadata", Path(filename).stem],
            source_file=filename,
        )
        world_model.add_edge(database_node_id, "has_document", node_id, score=0.9)
        for table_node_id, attrs in world_model.nodes.items():
            if attrs.get("type") != "table":
                continue
            table_name = str(attrs.get("label", "")).split(".")[-1]
            if _normalize_identifier(table_name) in _normalize_identifier(text):
                world_model.add_edge(table_node_id, "has_metadata_document", node_id, score=0.86)
    return world_model


@dataclass
class BirdBenchmarkAdapter:
    snapshots_by_db: dict[str, SQLSchemaSnapshot]
    worlds_by_db: dict[str, WorldModel] | None = None
    top_k: int = 8

    def run_task(self, task: BirdTask) -> dict[str, Any]:
        if task.db_id not in self.snapshots_by_db:
            raise KeyError(f"No schema snapshot registered for db_id={task.db_id}")

        snapshot = self.snapshots_by_db[task.db_id]
        world_model = (self.worlds_by_db or {}).get(task.db_id)
        coprocessor = SQLSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=f"bird:{task.db_id}",
            top_k=self.top_k,
            world_model=world_model,
        )
        result = coprocessor.ask(task.question, trace=True)
        candidate_tables = result.get("constraints", {}).get("candidate_tables", [])
        table_recall = None
        gold_table_names = task.gold_tables or _infer_gold_tables_from_sql(task.gold_sql)
        if gold_table_names:
            gold_tables = {_normalize_identifier(name) for name in gold_table_names}
            predicted_tables = {_normalize_identifier(name) for name in candidate_tables}
            if gold_tables:
                table_recall = len(gold_tables & predicted_tables) / len(gold_tables)
        return {
            "task_id": task.task_id,
            "db_id": task.db_id,
            "question": task.question,
            "candidate_tables": candidate_tables,
            "candidate_join_path": result.get("constraints", {}).get("candidate_join_path", []),
            "recommended_bridge_tables": result.get("constraints", {}).get("recommended_bridge_tables", []),
            "table_recall": table_recall,
            "gold_tables": gold_table_names,
            "evidence": task.evidence,
            "difficulty": task.difficulty,
            "trace": result.get("trace", []),
            "raw_result": result,
        }

    def evaluate_tasks(self, tasks: list[BirdTask]) -> dict[str, Any]:
        results = [self.run_task(task) for task in tasks if task.db_id in self.snapshots_by_db]
        table_recall_values = [result["table_recall"] for result in results if result["table_recall"] is not None]
        return {
            "tasks_evaluated": len(results),
            "tasks_with_gold_tables": len(table_recall_values),
            "average_table_recall": (
                sum(table_recall_values) / len(table_recall_values) if table_recall_values else None
            ),
            "results": results,
        }
