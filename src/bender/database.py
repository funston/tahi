from __future__ import annotations

import csv
import io
import os
import subprocess
from shutil import which
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .world_state import WorldModel


def _tokenize_name(value: str) -> list[str]:
    return [part for part in value.replace(".", "_").replace("-", "_").split("_") if part]


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _join_schema_list(schemas: Sequence[str]) -> str:
    return ", ".join(f"'{schema}'" for schema in schemas)


@dataclass
class SQLColumnProfile:
    schema: str
    table: str
    name: str
    data_type: str
    is_nullable: bool = True
    ordinal_position: int = 0
    description: str = ""
    sample_values: list[str] = field(default_factory=list)
    semantic_role: str | None = None

    @property
    def node_id(self) -> str:
        return f"column:{self.schema}.{self.table}.{self.name}"


@dataclass
class SQLForeignKey:
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str
    constraint_name: str = ""


@dataclass
class SQLTableProfile:
    schema: str
    name: str
    description: str = ""
    row_estimate: int | None = None
    columns: list[SQLColumnProfile] = field(default_factory=list)

    @property
    def node_id(self) -> str:
        return f"table:{self.schema}.{self.name}"


@dataclass
class SQLSchemaSnapshot:
    database_name: str
    tables: list[SQLTableProfile]
    foreign_keys: list[SQLForeignKey] = field(default_factory=list)

    def table_map(self) -> dict[tuple[str, str], SQLTableProfile]:
        return {(table.schema, table.name): table for table in self.tables}

    def compression_plan(self):
        from .schema_compression import build_schema_compression_plan

        return build_schema_compression_plan(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "SQLSchemaSnapshot":
        tables: list[SQLTableProfile] = []
        for table_payload in payload.get("tables", []):
            columns = [
                SQLColumnProfile(
                    schema=str(column_payload.get("schema", table_payload.get("schema", "public"))),
                    table=str(column_payload.get("table", table_payload.get("name", ""))),
                    name=str(column_payload.get("name", "")),
                    data_type=str(column_payload.get("data_type", "text")),
                    is_nullable=bool(column_payload.get("is_nullable", True)),
                    ordinal_position=int(column_payload.get("ordinal_position", 0) or 0),
                    description=str(column_payload.get("description", "")),
                    sample_values=[str(value) for value in column_payload.get("sample_values", [])],
                )
                for column_payload in table_payload.get("columns", [])
            ]
            tables.append(
                SQLTableProfile(
                    schema=str(table_payload.get("schema", "public")),
                    name=str(table_payload.get("name", "")),
                    description=str(table_payload.get("description", "")),
                    row_estimate=(
                        int(table_payload["row_estimate"])
                        if table_payload.get("row_estimate") is not None
                        else None
                    ),
                    columns=columns,
                )
            )
        foreign_keys = [
            SQLForeignKey(
                source_schema=str(fk_payload.get("source_schema", "public")),
                source_table=str(fk_payload.get("source_table", "")),
                source_column=str(fk_payload.get("source_column", "")),
                target_schema=str(fk_payload.get("target_schema", "public")),
                target_table=str(fk_payload.get("target_table", "")),
                target_column=str(fk_payload.get("target_column", "")),
                constraint_name=str(fk_payload.get("constraint_name", "")),
            )
            for fk_payload in payload.get("foreign_keys", [])
        ]
        return cls(
            database_name=str(payload.get("database_name", "sql_snapshot")),
            tables=tables,
            foreign_keys=foreign_keys,
        )


class SQLSchemaIntrospector:
    def introspect(
        self,
        *,
        schemas: Sequence[str] = ("public",),
        sample_limit: int = 3,
    ) -> SQLSchemaSnapshot:
        raise NotImplementedError


class PostgresSchemaIntrospector(SQLSchemaIntrospector):
    def __init__(
        self,
        *,
        psql_bin: str = "psql",
        dbname: str | None = None,
        host: str | None = None,
        port: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.psql_bin = _resolve_psql_bin(psql_bin)
        self.dbname = dbname or os.getenv("PGDATABASE")
        self.host = host or os.getenv("PGHOST")
        self.port = port or os.getenv("PGPORT")
        self.user = user or os.getenv("PGUSER")
        self.password = password or os.getenv("PGPASSWORD")

    def introspect(
        self,
        *,
        schemas: Sequence[str] = ("public",),
        sample_limit: int = 3,
    ) -> SQLSchemaSnapshot:
        tables = self._fetch_tables(schemas)
        columns = self._fetch_columns(schemas)
        foreign_keys = self._fetch_foreign_keys(schemas)

        table_map = {(table.schema, table.name): table for table in tables}
        for column in columns:
            table = table_map.get((column.schema, column.table))
            if table is None:
                continue
            if sample_limit > 0:
                column.sample_values = self._fetch_sample_values(column, limit=sample_limit)
            table.columns.append(column)

        return SQLSchemaSnapshot(
            database_name=self.dbname or "postgres",
            tables=tables,
            foreign_keys=foreign_keys,
        )

    def _base_command(self) -> list[str]:
        command = [self.psql_bin, "-X", "--csv", "-v", "ON_ERROR_STOP=1"]
        if self.host:
            command.extend(["-h", self.host])
        if self.port:
            command.extend(["-p", self.port])
        if self.user:
            command.extend(["-U", self.user])
        if self.dbname:
            command.extend(["-d", self.dbname])
        return command

    def _run_query(self, sql: str) -> list[dict[str, str]]:
        env = os.environ.copy()
        if self.password:
            env["PGPASSWORD"] = self.password
        command = self._base_command() + ["-c", sql]
        process = subprocess.run(
            command,
            capture_output=True,
            check=True,
            text=True,
            env=env,
        )
        text = process.stdout.strip()
        if not text:
            return []
        return list(csv.DictReader(io.StringIO(text)))

    def _fetch_tables(self, schemas: Sequence[str]) -> list[SQLTableProfile]:
        schema_list = _join_schema_list(schemas)
        rows = self._run_query(
            f"""
            SELECT
                n.nspname AS table_schema,
                c.relname AS table_name,
                COALESCE(obj_description(c.oid), '') AS description,
                GREATEST(c.reltuples::bigint, 0) AS row_estimate
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND n.nspname IN ({schema_list})
            ORDER BY n.nspname, c.relname
            """
        )
        return [
            SQLTableProfile(
                schema=row["table_schema"],
                name=row["table_name"],
                description=row.get("description", ""),
                row_estimate=int(row["row_estimate"]) if row.get("row_estimate") else None,
            )
            for row in rows
        ]

    def _fetch_columns(self, schemas: Sequence[str]) -> list[SQLColumnProfile]:
        schema_list = _join_schema_list(schemas)
        rows = self._run_query(
            f"""
            SELECT
                table_schema,
                table_name,
                column_name,
                data_type,
                is_nullable,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema IN ({schema_list})
            ORDER BY table_schema, table_name, ordinal_position
            """
        )
        return [
            SQLColumnProfile(
                schema=row["table_schema"],
                table=row["table_name"],
                name=row["column_name"],
                data_type=row["data_type"],
                is_nullable=row.get("is_nullable", "YES") == "YES",
                ordinal_position=int(row.get("ordinal_position") or 0),
            )
            for row in rows
        ]

    def _fetch_foreign_keys(self, schemas: Sequence[str]) -> list[SQLForeignKey]:
        schema_list = _join_schema_list(schemas)
        rows = self._run_query(
            f"""
            SELECT
                tc.constraint_name,
                tc.table_schema AS source_schema,
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_schema AS target_schema,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema IN ({schema_list})
            ORDER BY tc.table_schema, tc.table_name, tc.constraint_name
            """
        )
        return [
            SQLForeignKey(
                source_schema=row["source_schema"],
                source_table=row["source_table"],
                source_column=row["source_column"],
                target_schema=row["target_schema"],
                target_table=row["target_table"],
                target_column=row["target_column"],
                constraint_name=row.get("constraint_name", ""),
            )
            for row in rows
        ]

    def _fetch_sample_values(
        self,
        column: SQLColumnProfile,
        *,
        limit: int,
    ) -> list[str]:
        table_ident = f"{_quote_ident(column.schema)}.{_quote_ident(column.table)}"
        column_ident = _quote_ident(column.name)
        rows = self._run_query(
            f"""
            SELECT DISTINCT LEFT({column_ident}::text, 64) AS sample_value
            FROM {table_ident}
            WHERE {column_ident} IS NOT NULL
            LIMIT {int(limit)}
            """
        )
        return [row["sample_value"] for row in rows if row.get("sample_value")]


def snapshot_to_world_model(snapshot: SQLSchemaSnapshot) -> WorldModel:
    world_model = WorldModel(domain=f"postgres:{snapshot.database_name}")
    database_node_id = f"database:{snapshot.database_name}"
    table_map = snapshot.table_map()
    compression_plan = snapshot.compression_plan()
    family_map = compression_plan.family_map()

    world_model.upsert_node(
        database_node_id,
        label=snapshot.database_name,
        type="database",
        summary=f"PostgreSQL database {snapshot.database_name}.",
        keywords=[snapshot.database_name, "postgres", "database", "schema"],
    )

    for table in snapshot.tables:
        column_names = [column.name for column in table.columns]
        table_summary = (
            f"Table {table.schema}.{table.name} with columns {', '.join(column_names)}."
        )
        if table.row_estimate is not None:
            table_summary += f" Estimated rows: {table.row_estimate}."
        if table.description:
            table_summary += f" {table.description}"
        table_keywords = _tokenize_name(table.name) + _tokenize_name(table.schema) + column_names
        world_model.upsert_node(
            table.node_id,
            label=f"{table.schema}.{table.name}",
            type="table",
            summary=table_summary,
            keywords=table_keywords,
            schema=table.schema,
            table_name=table.name,
            row_estimate=table.row_estimate,
        )
        world_model.add_edge(database_node_id, "contains_table", table.node_id, score=0.99)

        for column in table.columns:
            sample_suffix = ""
            if column.sample_values:
                sample_suffix = f" Sample values: {', '.join(column.sample_values)}."
            summary = (
                f"Column {column.schema}.{column.table}.{column.name} has type {column.data_type}."
                f" Nullable: {column.is_nullable}.{sample_suffix}"
            )
            if column.description:
                summary += f" {column.description}"
            keywords = (
                _tokenize_name(column.name)
                + _tokenize_name(column.table)
                + list(column.sample_values)
                + [column.data_type]
            )
            world_model.upsert_node(
                column.node_id,
                label=f"{column.table}.{column.name}",
                type="column",
                summary=summary,
                keywords=keywords,
                schema=column.schema,
                table_name=column.table,
                column_name=column.name,
                data_type=column.data_type,
                sample_values=list(column.sample_values),
                semantic_role=column.semantic_role,
            )
            world_model.add_edge(table.node_id, "has_column", column.node_id, score=0.98)

        family_id = compression_plan.table_to_family.get(f"{table.schema}.{table.name}".lower())
        if family_id and family_id in family_map:
            family = family_map[family_id]
            world_model.nodes[table.node_id]["schema_family_id"] = family_id
            world_model.nodes[table.node_id]["schema_family_label"] = family.label
            world_model.nodes[table.node_id]["keywords"] = list(
                dict.fromkeys(
                    list(world_model.nodes[table.node_id].get("keywords", []))
                    + list(family.prototype_tokens)
                    + list(family.common_columns[:8])
                )
            )

    for foreign_key in snapshot.foreign_keys:
        source_table_id = f"table:{foreign_key.source_schema}.{foreign_key.source_table}"
        target_table_id = f"table:{foreign_key.target_schema}.{foreign_key.target_table}"
        source_column_id = (
            f"column:{foreign_key.source_schema}.{foreign_key.source_table}.{foreign_key.source_column}"
        )
        target_column_id = (
            f"column:{foreign_key.target_schema}.{foreign_key.target_table}.{foreign_key.target_column}"
        )
        if (foreign_key.source_schema, foreign_key.source_table) in table_map:
            world_model.add_edge(
                source_table_id,
                "references_table",
                target_table_id,
                score=0.97,
                constraint=foreign_key.constraint_name,
                source_column=foreign_key.source_column,
                target_column=foreign_key.target_column,
            )
        world_model.add_edge(
            source_column_id,
            "references_column",
            target_column_id,
            score=0.97,
            constraint=foreign_key.constraint_name,
        )

    for family in compression_plan.families:
        if len(family.members) < 2:
            continue
        world_model.upsert_node(
            family.family_id,
            label=family.label,
            type="schema_family",
            summary=family.summary(),
            keywords=list(family.prototype_tokens) + family.common_columns[:10] + family.distinguishing_tokens[:10],
            member_count=len(family.members),
            common_columns=list(family.common_columns),
        )
        world_model.add_edge(database_node_id, "contains_schema_family", family.family_id, score=0.95)
        for member in family.members:
            table_id = f"table:{member.schema}.{member.table}"
            if table_id in world_model.nodes:
                world_model.add_edge(family.family_id, "contains_table", table_id, score=0.94)
                world_model.add_edge(table_id, "member_of_schema_family", family.family_id, score=0.94)

    return world_model


def build_pagila_fixture_snapshot() -> SQLSchemaSnapshot:
    tables = [
        SQLTableProfile(
            schema="public",
            name="actor",
            row_estimate=200,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="actor",
                    name="actor_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="actor",
                    name="first_name",
                    data_type="text",
                    sample_values=["PENELOPE", "NICK"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="actor",
                    name="last_name",
                    data_type="text",
                    sample_values=["GUINESS", "WAHLBERG"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="film",
            row_estimate=1000,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="film",
                    name="film_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="film",
                    name="title",
                    data_type="text",
                    sample_values=["ACADEMY DINOSAUR", "ACE GOLDFINGER"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="film",
                    name="rating",
                    data_type="text",
                    sample_values=["PG", "G"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="category",
            row_estimate=16,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="category",
                    name="category_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="category",
                    name="name",
                    data_type="text",
                    sample_values=["Action", "Comedy"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="film_actor",
            row_estimate=5462,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="film_actor",
                    name="actor_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="film_actor",
                    name="film_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="film_category",
            row_estimate=1000,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="film_category",
                    name="film_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="film_category",
                    name="category_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="customer",
            row_estimate=599,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="customer",
                    name="customer_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="customer",
                    name="first_name",
                    data_type="text",
                    sample_values=["MARY", "PATRICIA"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="customer",
                    name="last_name",
                    data_type="text",
                    sample_values=["SMITH", "JOHNSON"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="customer",
                    name="address_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["5", "12"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="customer",
                    name="store_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="address",
            row_estimate=603,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="address",
                    name="address_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="address",
                    name="address",
                    data_type="text",
                    sample_values=["47 MySakila Drive", "28 MySQL Boulevard"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="address",
                    name="postal_code",
                    data_type="text",
                    sample_values=["35200", "17886"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="store",
            row_estimate=2,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="store",
                    name="store_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="store",
                    name="address_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="inventory",
            row_estimate=4581,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="inventory",
                    name="inventory_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="inventory",
                    name="film_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="rental",
            row_estimate=16044,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="rental",
                    name="rental_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1", "2"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="rental",
                    name="rental_date",
                    data_type="timestamp",
                    is_nullable=False,
                    sample_values=["2005-05-24 22:53:30", "2005-05-25 11:30:37"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="rental",
                    name="inventory_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["367", "1525"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="rental",
                    name="customer_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["130", "459"],
                ),
            ],
        ),
        SQLTableProfile(
            schema="public",
            name="payment_p2007_01",
            row_estimate=2709,
            columns=[
                SQLColumnProfile(
                    schema="public",
                    table="payment_p2007_01",
                    name="payment_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["17503", "17504"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="payment_p2007_01",
                    name="customer_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["341", "72"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="payment_p2007_01",
                    name="rental_id",
                    data_type="integer",
                    is_nullable=False,
                    sample_values=["1520", "1778"],
                ),
                SQLColumnProfile(
                    schema="public",
                    table="payment_p2007_01",
                    name="amount",
                    data_type="numeric",
                    is_nullable=False,
                    sample_values=["2.99", "4.99"],
                ),
            ],
        ),
    ]
    foreign_keys = [
        SQLForeignKey("public", "film_actor", "actor_id", "public", "actor", "actor_id"),
        SQLForeignKey("public", "film_actor", "film_id", "public", "film", "film_id"),
        SQLForeignKey("public", "film_category", "film_id", "public", "film", "film_id"),
        SQLForeignKey("public", "film_category", "category_id", "public", "category", "category_id"),
        SQLForeignKey("public", "customer", "address_id", "public", "address", "address_id"),
        SQLForeignKey("public", "customer", "store_id", "public", "store", "store_id"),
        SQLForeignKey("public", "store", "address_id", "public", "address", "address_id"),
        SQLForeignKey("public", "inventory", "film_id", "public", "film", "film_id"),
        SQLForeignKey("public", "rental", "inventory_id", "public", "inventory", "inventory_id"),
        SQLForeignKey("public", "rental", "customer_id", "public", "customer", "customer_id"),
        SQLForeignKey("public", "payment_p2007_01", "customer_id", "public", "customer", "customer_id"),
        SQLForeignKey("public", "payment_p2007_01", "rental_id", "public", "rental", "rental_id"),
    ]
    return SQLSchemaSnapshot(
        database_name="pagila_fixture",
        tables=tables,
        foreign_keys=foreign_keys,
    )


def format_connection_help() -> str:
    parts = [
        "Use standard PostgreSQL environment variables:",
        "PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE.",
        "Example:",
        "PGHOST=127.0.0.1 PGPORT=55432 PGDATABASE=pagila PGUSER=postgres python3 examples/postgres_pagila_schema_demo.py --live-postgres",
    ]
    return " ".join(parts)


def summarize_snapshot(snapshot: SQLSchemaSnapshot) -> dict[str, object]:
    return {
        "database_name": snapshot.database_name,
        "tables": [f"{table.schema}.{table.name}" for table in snapshot.tables],
        "foreign_keys": [
            {
                "source": f"{fk.source_schema}.{fk.source_table}.{fk.source_column}",
                "target": f"{fk.target_schema}.{fk.target_table}.{fk.target_column}",
            }
            for fk in snapshot.foreign_keys
        ],
    }


# Backward-compatible aliases while the codebase moves to generic SQL naming.
PostgresColumnProfile = SQLColumnProfile
PostgresForeignKey = SQLForeignKey
PostgresTableProfile = SQLTableProfile
DatabaseSchemaSnapshot = SQLSchemaSnapshot


def _resolve_psql_bin(psql_bin: str) -> str:
    candidates = [
        psql_bin,
        os.getenv("PSQL_BIN", ""),
        "/opt/homebrew/opt/postgresql@15/bin/psql",
        "/opt/homebrew/opt/postgresql@16/bin/psql",
        "/opt/homebrew/opt/postgresql@17/bin/psql",
        "/opt/homebrew/opt/libpq/bin/psql",
        "/usr/local/bin/psql",
        which(psql_bin) or "",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return psql_bin
