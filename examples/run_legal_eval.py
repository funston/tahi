#!/usr/bin/env python3
"""Run the OCTO legal coprocessor evaluation.

Usage:
    export OPENAI_API_KEY="..."
    python examples/run_legal_eval.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from implementations.legal import evaluate_legal_coprocessor


def main():
    report = evaluate_legal_coprocessor()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
