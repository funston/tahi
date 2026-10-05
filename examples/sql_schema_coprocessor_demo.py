import argparse
import json

from tahi import SQLSchemaCoprocessor, build_pagila_fixture_snapshot, summarize_snapshot


DEFAULT_QUERY = "Which tables connect customers to the films they rented?"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Generic SQL schema question to run through the SQL coprocessor.",
    )
    args = parser.parse_args()

    snapshot = build_pagila_fixture_snapshot()
    coprocessor = SQLSchemaCoprocessor.from_snapshot(snapshot)
    result = coprocessor.ask(args.query, trace=True)

    print("SCHEMA SNAPSHOT")
    print(json.dumps(summarize_snapshot(snapshot), indent=2))
    print()
    print("QUESTION")
    print(args.query)
    print()
    print("SQL COPROCESSOR RESULT")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
