#!/usr/bin/env python3
"""Run the TAHI legal coprocessor evaluation.

Usage:
    export OPENAI_API_KEY="..."
    python examples/run_legal_eval.py

Output is written to:
    ./results/legal.json   (raw)
    ./results/legal.md     (table + ASCII chart)
    ./results/legal.svg    (bar chart)
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from implementations.legal import evaluate_legal_coprocessor
from tahi.results_reporter import write_eval_artifacts


def main():
    report = evaluate_legal_coprocessor()

    meta = {
        "eval": "legal",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    paths = write_eval_artifacts(ROOT / "results", "legal", report, meta)

    print(f"Legal eval written to:")
    print(f"  JSON: {paths['json']}")
    print(f"  MD:   {paths['md']}")
    print(f"  SVG:  {paths['svg']}")
    print(f"\n  RAG accuracy:   {report['rag']['accuracy']:.1%}")
    print(f"  TAHI accuracy:  {report['tahi']['accuracy']:.1%}")
    print(f"  Delta:          {report['delta']:+.1%}")


if __name__ == "__main__":
    main()
