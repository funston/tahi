import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from octo import build_pagila_fixture_snapshot, summarize_snapshot
from implementations.spider import SpiderSchemaCoprocessor


DEFAULT_QUERY = "Which actors appeared in Action films?"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Spider-style schema question to run through the schema coprocessor.",
    )
    args = parser.parse_args()

    snapshot = build_pagila_fixture_snapshot()
    coprocessor = SpiderSchemaCoprocessor.from_snapshot(snapshot)
    result = coprocessor.ask(args.query, trace=True)

    print("SCHEMA SNAPSHOT")
    print(json.dumps(summarize_snapshot(snapshot), indent=2))
    print()
    print("QUESTION")
    print(args.query)
    print()
    print("SPIDER COPROCESSOR RESULT")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
