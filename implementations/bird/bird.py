from __future__ import annotations

import json
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
import urllib.request

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from bender.benchmarking import BenchmarkCaseResult, benchmark_report_to_dict, render_markdown_summary_table, summarize_system_results
from bender.database import SQLColumnProfile, SQLForeignKey, SQLSchemaSnapshot, SQLTableProfile
from bender.repair.sql import SQLRepairAttempt
from implementations.sql import SQLSchemaCoprocessor
from bender.validators.sql import SQLResultMatcher
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


def _extract_sql(text: str) -> str:
    stripped = text.strip()
    fenced = re.findall(r"```(?:sql)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        stripped = fenced[0].strip()
    match = re.search(r"((WITH|SELECT)\b.*)", stripped, flags=re.IGNORECASE | re.DOTALL)
    if match:
        stripped = match.group(1).strip()
    stripped = stripped.split("\n\n", 1)[0].strip()
    if "SELECT" not in stripped.upper() and "WITH" not in stripped.upper():
        return ""
    return stripped


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
            try:
                # Try UTF-8 first, fallback to latin-1 which accepts all bytes
                try:
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    content = path.read_text(encoding="latin-1")
                documents[str(path.relative_to(description_dir))] = content
            except Exception:
                # Skip files that can't be read
                continue
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


@dataclass
class BirdHFWorkspace:
    repo_id: str = "Sudnya/bird-sql"
    cache_dir: Path | str = ".local/bird_hf"

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _dataset_cache_dir(self) -> Path:
        path = self.cache_dir / "hf_datasets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _hub_cache_dir(self) -> Path:
        path = self.cache_dir / "hf_hub"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _problem_split(self, split: str) -> str:
        return "validation" if split in {"dev", "validation"} else split

    def _database_zip_name(self, split: str) -> str:
        return "dev_databases.zip" if split in {"dev", "validation"} else f"{split}_databases.zip"

    def load_tasks(self, split: str = "dev") -> list[BirdTask]:
        from datasets import load_dataset

        dataset = load_dataset(
            self.repo_id,
            split=self._problem_split(split),
            cache_dir=str(self._dataset_cache_dir()),
        )
        tasks: list[BirdTask] = []
        for index, record in enumerate(dataset, start=1):
            task = BirdTask.from_record(dict(record))
            if task.task_id == "task":
                task.task_id = f"{task.db_id}_{index:04d}"
            tasks.append(task)
        return tasks

    def ensure_database_cache(self, split: str = "dev", force_download: bool = False) -> Path:
        extract_dir = self.cache_dir / split
        if not force_download and any(extract_dir.rglob("*.sqlite")):
            return extract_dir
        if not force_download and any(extract_dir.rglob("*.db")):
            return extract_dir

        from huggingface_hub import hf_hub_download

        zip_path = hf_hub_download(
            repo_id=self.repo_id,
            filename=f"databases/{self._database_zip_name(split)}",
            repo_type="dataset",
            cache_dir=str(self._hub_cache_dir()),
        )
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)
        return extract_dir

    def resolve_local_sqlite_db(self, db_id: str, split: str = "dev") -> Path:
        db_root = self.ensure_database_cache(split=split)
        normalized_target = _normalize_identifier(db_id)
        candidates = sorted(
            candidate
            for candidate in db_root.rglob("*")
            if candidate.is_file() and candidate.suffix.lower() in {".sqlite", ".db"}
        )
        for candidate in candidates:
            names = {
                _normalize_identifier(candidate.stem),
                _normalize_identifier(candidate.parent.name),
            }
            if normalized_target in names:
                return candidate
        raise FileNotFoundError(f"Could not resolve BIRD SQLite database for db_id={db_id} in repo_id={self.repo_id}")

    def load_database_documents(self, db_id: str, split: str = "dev") -> dict[str, str]:
        """Load database description CSV files as metadata documents"""
        # Databases are extracted to cache_dir/split/dev_databases/db_id/
        split_dir = self.cache_dir / split
        db_base_path = split_dir / "dev_databases" / db_id / "database_description"
        if not db_base_path.exists():
            return {}

        documents = {}
        for csv_file in db_base_path.glob("*.csv"):
            try:
                # Read entire CSV as text for now (could parse as structured data later)
                with open(csv_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                documents[csv_file.name] = content
            except Exception:
                continue  # Skip files that can't be read

        return documents


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


class BirdSQLiteExecutionEngine:
    def __init__(self, db_path: str | Path):
        self.db_path = str(Path(db_path))

    def execute(self, sql: str) -> tuple[list[dict[str, Any]], str | None]:
        try:
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            try:
                rows = connection.execute(sql).fetchall()
                return [dict(row) for row in rows], None
            finally:
                connection.close()
        except Exception as exc:  # noqa: BLE001
            return [], f"{type(exc).__name__}: {exc}"


@dataclass
class BirdSQLCandidate:
    sql: str
    strategy: str
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BirdExecutionPacket:
    task_id: str
    db_id: str
    question: str
    evidence: str
    candidate_tables: list[str]
    snapshot: SQLSchemaSnapshot
    include_evidence: bool = False

    def to_prompt(self) -> str:
        allowed = {_normalize_identifier(name) for name in self.candidate_tables} if self.candidate_tables else set()
        table_blocks: list[str] = []
        for table in self.snapshot.tables:
            if allowed and _normalize_identifier(table.name) not in allowed:
                continue
            columns = ", ".join(f"{column.name} {column.data_type}" for column in table.columns)
            table_blocks.append(f"TABLE {table.name} ({columns})")
        schema_text = "\n".join(table_blocks) if table_blocks else "(no filtered tables available)"
        evidence_text = f"\nEvidence: {self.evidence.strip()}" if self.include_evidence and self.evidence.strip() else ""
        return (
            "You are writing SQLite SQL for the BIRD benchmark.\n"
            "Return only SQL.\n"
            "Use only the tables shown below when possible.\n\n"
            f"Database: {self.db_id}\n"
            f"Schema:\n{schema_text}\n\n"
            f"Question: {self.question}{evidence_text}\n"
        )


class BirdSQLCandidateGenerator(Protocol):
    def generate(self, packet: BirdExecutionPacket, *, max_candidates: int = 4) -> list[BirdSQLCandidate]:
        ...


class BirdHeuristicSQLCandidateGenerator:
    def generate(self, packet: BirdExecutionPacket, *, max_candidates: int = 4) -> list[BirdSQLCandidate]:
        question = packet.question.lower()
        candidate_tables = packet.candidate_tables or [table.name for table in packet.snapshot.tables]
        table_name = candidate_tables[0] if candidate_tables else ""
        if not table_name:
            return []
        aggregate_column = self._best_aggregate_column(packet.snapshot, table_name, question)
        if "how many" in question or "count" in question:
            sql = f"SELECT COUNT(*) AS count FROM {table_name}"
        elif aggregate_column and ("average" in question or "avg" in question):
            sql = f"SELECT AVG({aggregate_column}) AS average_value FROM {table_name}"
        elif aggregate_column and ("total" in question or "sum" in question):
            sql = f"SELECT SUM({aggregate_column}) AS total_value FROM {table_name}"
        else:
            sql = f"SELECT * FROM {table_name} LIMIT 10"
        return [
            BirdSQLCandidate(
                sql=sql,
                strategy="heuristic",
                rationale="Simple heuristic SQL fallback for BIRD execution benchmarking.",
            )
        ]

    def _best_aggregate_column(self, snapshot: SQLSchemaSnapshot, table_name: str, question: str) -> str | None:
        for table in snapshot.tables:
            if table.name != table_name:
                continue
            numeric = [column.name for column in table.columns if any(tok in column.data_type.upper() for tok in ("INT", "REAL", "NUM", "DEC", "FLOAT", "DOUBLE"))]
            if not numeric:
                return None
            for preferred in ("count", "amount", "value", "price", "score", "total", "salary", "diff"):
                for column in numeric:
                    if preferred in column.lower() or preferred in question:
                        return column
            return numeric[0]
        return None


class BirdPromptedSQLCandidateGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: int = 120,
        temperature: float = 0.0,
        max_tokens: int = 256,
        strict: bool = False,
        fallback: BirdSQLCandidateGenerator | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.strict = strict
        self.fallback = fallback or BirdHeuristicSQLCandidateGenerator()

    def generate(self, packet: BirdExecutionPacket, *, max_candidates: int = 4) -> list[BirdSQLCandidate]:
        texts: list[str] = []
        last_error: Exception | None = None
        try:
            payload = {
                "prompt": {"text": packet.to_prompt()},
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "n": max_candidates,
            }
            response = self._post_json(f"{self.base_url}/v1/generate", payload)
            texts.extend(self._extract_texts(response))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        candidates = self._texts_to_candidates(texts)
        candidates.extend(self.fallback.generate(packet, max_candidates=max_candidates))
        deduped: list[BirdSQLCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            sql = candidate.sql.strip()
            if not sql or sql in seen:
                continue
            seen.add(sql)
            deduped.append(candidate)
        if deduped:
            return deduped[:max_candidates]
        if self.strict:
            detail = f"{type(last_error).__name__}: {last_error}" if last_error is not None else "empty_candidate_set"
            raise RuntimeError(
                f"bird_prompted_candidate_generation_failed model={self.model} base_url={self.base_url} detail={detail}"
            )
        return []

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _extract_texts(self, payload: dict[str, Any]) -> list[str]:
        texts: list[str] = []
        for key in ("results", "outputs", "choices"):
            value = payload.get(key)
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, dict):
                    if isinstance(item.get("response"), str):
                        texts.append(item["response"])
                    if isinstance(item.get("text"), str):
                        texts.append(item["text"])
                    message = item.get("message")
                    if isinstance(message, dict) and isinstance(message.get("content"), str):
                        texts.append(message["content"])
                else:
                    texts.append(str(item))
        for key in ("text", "generated_text"):
            value = payload.get(key)
            if value:
                texts.append(str(value))
        return texts

    def _texts_to_candidates(self, texts: list[str]) -> list[BirdSQLCandidate]:
        candidates: list[BirdSQLCandidate] = []
        for index, text in enumerate(texts):
            sql = _extract_sql(text)
            if not sql:
                continue
            candidates.append(
                BirdSQLCandidate(
                    sql=sql,
                    strategy="prompted",
                    rationale="Candidate generated by prompted SQL backend.",
                    metadata={"candidate_index": index},
                )
            )
        return candidates


class BirdOllamaSQLCandidateGenerator:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11435",
        model: str = "qwen2.5-coder:latest",
        timeout: int = 240,
        strict: bool = True,
        temperatures: tuple[float, ...] = (0.0, 0.1, 0.2),
        fallback: BirdSQLCandidateGenerator | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.strict = strict
        self.temperatures = temperatures
        self.fallback = fallback or BirdHeuristicSQLCandidateGenerator()

    def generate(self, packet: BirdExecutionPacket, *, max_candidates: int = 4) -> list[BirdSQLCandidate]:
        candidates: list[BirdSQLCandidate] = []
        errors: list[str] = []
        for index in range(max_candidates):
            temperature = self.temperatures[index % len(self.temperatures)]
            try:
                payload = {
                    "model": self.model,
                    "prompt": packet.to_prompt(),
                    "stream": False,
                    "options": {"temperature": temperature},
                }
                response = self._post_json(f"{self.base_url}/api/generate", payload)
                sql = _extract_sql(str(response.get("response", "")))
                if not sql:
                    continue
                candidates.append(
                    BirdSQLCandidate(
                        sql=sql,
                        strategy="ollama",
                        rationale=f"Ollama SQL candidate {index + 1}",
                        metadata={"temperature": temperature},
                    )
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")
        candidates.extend(self.fallback.generate(packet, max_candidates=max_candidates))
        deduped: list[BirdSQLCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            sql = candidate.sql.strip()
            if not sql or sql in seen:
                continue
            seen.add(sql)
            deduped.append(candidate)
        if deduped:
            return deduped[:max_candidates]
        if self.strict:
            detail = "; ".join(errors) if errors else "empty_candidate_set"
            raise RuntimeError(
                f"bird_ollama_candidate_generation_failed model={self.model} base_url={self.base_url} detail={detail}"
            )
        return []

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


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
    include_evidence: bool = False

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
        query = task.question
        if self.include_evidence and task.evidence.strip():
            query = f"{task.question}\nEvidence: {task.evidence.strip()}"
        result = coprocessor.ask(query, trace=True)
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
            "query": query,
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


@dataclass
class BirdABBenchmarkRunner:
    baseline_adapter: BirdBenchmarkAdapter
    bender_adapter: BirdBenchmarkAdapter
    evidence_adapter: BirdBenchmarkAdapter | None = None

    def run(self, tasks: list[BirdTask]) -> dict[str, Any]:
        naive_results: list[BenchmarkCaseResult] = []
        baseline_results: list[BenchmarkCaseResult] = []
        bender_results: list[BenchmarkCaseResult] = []
        evidence_results: list[BenchmarkCaseResult] = []
        for task in tasks:
            naive = _run_bird_naive_baseline(self.baseline_adapter.snapshots_by_db[task.db_id], task)
            baseline = self.baseline_adapter.run_task(task)
            bender = self.bender_adapter.run_task(task)
            evidence = self.evidence_adapter.run_task(task) if self.evidence_adapter is not None else None
            naive_results.append(
                BenchmarkCaseResult(
                    case_id=task.task_id,
                    system="naive_lexical",
                    correct=bool((naive.get("table_recall") or 0.0) >= 1.0),
                    metrics={
                        "table_recall": naive.get("table_recall"),
                        "top1_hit": _bird_top1_hit(naive),
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
                        "top1_hit": _bird_top1_hit(baseline),
                    },
                    detail=baseline,
                )
            )
            bender_results.append(
                BenchmarkCaseResult(
                    case_id=task.task_id,
                    system="bender",
                    correct=bool((bender.get("table_recall") or 0.0) >= 1.0),
                    metrics={
                        "table_recall": bender.get("table_recall"),
                        "top1_hit": _bird_top1_hit(bender),
                    },
                    detail=bender,
                )
            )
            if evidence is not None:
                evidence_results.append(
                    BenchmarkCaseResult(
                        case_id=task.task_id,
                        system="bender_with_evidence",
                        correct=bool((evidence.get("table_recall") or 0.0) >= 1.0),
                        metrics={
                            "table_recall": evidence.get("table_recall"),
                            "top1_hit": _bird_top1_hit(evidence),
                        },
                        detail=evidence,
                    )
                )

        summaries = [
            summarize_system_results("naive_lexical", naive_results, metric_names=["table_recall", "top1_hit"]),
            summarize_system_results("schema_only", baseline_results, metric_names=["table_recall", "top1_hit"]),
            summarize_system_results("bender", bender_results, metric_names=["table_recall", "top1_hit"]),
        ]
        if evidence_results:
            summaries.append(
                summarize_system_results(
                    "bender_with_evidence",
                    evidence_results,
                    metric_names=["table_recall", "top1_hit"],
                )
            )
        results_by_system: dict[str, list[BenchmarkCaseResult]] = {
            "naive_lexical": naive_results,
            "schema_only": baseline_results,
            "bender": bender_results,
        }
        if evidence_results:
            results_by_system["bender_with_evidence"] = evidence_results
        payload = benchmark_report_to_dict(
            benchmark_name="bird_ab_grounding",
            summaries=summaries,
            results_by_system=results_by_system,
        )
        payload["markdown_summary"] = render_markdown_summary_table(summaries)
        return payload


def _bird_top1_hit(result: dict[str, Any]) -> float:
    candidate_tables = result.get("candidate_tables", [])
    gold_tables = result.get("gold_tables", [])
    if not candidate_tables or not gold_tables:
        return 0.0
    predicted = _normalize_identifier(candidate_tables[0])
    gold = {_normalize_identifier(name) for name in gold_tables}
    return 1.0 if predicted in gold else 0.0


def _run_bird_naive_baseline(snapshot: SQLSchemaSnapshot, task: BirdTask) -> dict[str, Any]:
    question_tokens = set(re.findall(r"[a-z0-9_]+", task.question.lower()))
    scored: list[tuple[float, str]] = []
    for table in snapshot.tables:
        table_tokens = set(re.findall(r"[a-z0-9_]+", table.name.lower()))
        column_tokens = {
            token
            for column in table.columns
            for token in re.findall(r"[a-z0-9_]+", column.name.lower())
        }
        score = len(question_tokens & table_tokens) * 2.0 + len(question_tokens & column_tokens) * 0.5
        scored.append((score, table.name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    candidate_tables = [name for score, name in scored if score > 0.0][:3]
    gold_table_names = task.gold_tables or _infer_gold_tables_from_sql(task.gold_sql)
    table_recall = None
    if gold_table_names:
        gold_tables = {_normalize_identifier(name) for name in gold_table_names}
        predicted_tables = {_normalize_identifier(name) for name in candidate_tables}
        table_recall = len(gold_tables & predicted_tables) / len(gold_tables) if gold_tables else None
    return {
        "task_id": task.task_id,
        "db_id": task.db_id,
        "question": task.question,
        "candidate_tables": candidate_tables,
        "candidate_join_path": [],
        "recommended_bridge_tables": [],
        "table_recall": table_recall,
        "gold_tables": gold_table_names,
        "evidence": task.evidence,
        "difficulty": task.difficulty,
        "trace": [],
        "raw_result": {
            "baseline": "naive_lexical",
        },
    }
