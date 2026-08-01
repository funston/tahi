#!/usr/bin/env python3
"""Run the OCTO drug-enforcement coprocessor evaluation.

Usage:
    export OPENAI_API_KEY="..."
    python examples/run_dea_eval.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from implementations.drug_enforcement import evaluate_drug_coprocessor


def main():
    report = evaluate_drug_coprocessor()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
