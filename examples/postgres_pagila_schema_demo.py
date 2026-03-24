import argparse
import json

from bender import (
    PostgresSchemaIntrospector,
    SQLSchemaCoprocessor,
    build_pagila_fixture_snapshot,
    format_connection_help,
    summarize_snapshot,
)


DEFAULT_QUERY = "Which tables connect customers to the films they rented?"


def load_snapshot(use_fixture: bool):
    if use_fixture:
        return build_pagila_fixture_snapshot()
    introspector = PostgresSchemaIntrospector()
    return introspector.introspect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Question to run against the schema world model.",
    )
    parser.add_argument(
        "--live-postgres",
        action="store_true",
        help="Introspect a live PostgreSQL database using PG* environment variables.",
    )
    args = parser.parse_args()

    try:
        snapshot = load_snapshot(use_fixture=not args.live_postgres)
    except Exception as exc:
        raise SystemExit(f"{exc}\n{format_connection_help()}") from exc

    coprocessor = SQLSchemaCoprocessor.from_snapshot(
        snapshot,
        model_name="pagila-schema-coprocessor",
        top_k=8,
    )
    result = coprocessor.ask(args.query, trace=True)

    print("SCHEMA SNAPSHOT")
    print(json.dumps(summarize_snapshot(snapshot), indent=2))
    print()
    print("QUESTION")
    print(args.query)
    print()
    print("BENDER RESULT")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
