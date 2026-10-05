#!/usr/bin/env python3
"""Run the TAHI HotpotQA multi-hop evaluation.

Usage:
    export OPENAI_API_KEY="..."
    python examples/run_hotpotqa_eval.py [--max-samples 50]

Output is written to:
    ./results/hotpotqa.json   (raw)
    ./results/hotpotqa.md     (table + ASCII chart)
    ./results/hotpotqa.svg    (bar chart)
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from implementations.hotpotqa import evaluate_hotpotqa
from tahi.results_reporter import write_eval_artifacts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=50)
    args = parser.parse_args()

    report = evaluate_hotpotqa(max_samples=args.max_samples)

    meta = {
        "eval": "hotpotqa",
        "max_samples": args.max_samples,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    paths = write_eval_artifacts(ROOT / "results", "hotpotqa", report, meta)

    print(f"HotpotQA eval written to:")
    print(f"  JSON: {paths['json']}")
    print(f"  MD:   {paths['md']}")
    print(f"  SVG:  {paths['svg']}")
    print(f"\n  RAG accuracy:   {report['rag']['accuracy']:.1%}")
    print(f"  TAHI accuracy:  {report['tahi']['accuracy']:.1%}")
    print(f"  Delta:          {report['delta']:+.1%}")


if __name__ == "__main__":
    main()
