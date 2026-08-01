#!/usr/bin/env python3
"""Run the OCTO MuSiQue multi-hop evaluation.

Usage:
    export OPENAI_API_KEY="..."
    python examples/run_musique_eval.py [--max-samples 50] [--path path/to/musique.json]

Output is written to:
    ./results/musique.json   (raw)
    ./results/musique.md     (table + ASCII chart)
    ./results/musique.svg    (bar chart)
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from implementations.musique import evaluate_musique
from octo.results_reporter import write_eval_artifacts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--path", type=str, default=None)
    args = parser.parse_args()

    report = evaluate_musique(max_samples=args.max_samples, path=args.path)

    meta = {
        "eval": "musique",
        "max_samples": args.max_samples,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    paths = write_eval_artifacts(ROOT / "results", "musique", report, meta)

    print(f"MuSiQue eval written to:")
    print(f"  JSON: {paths['json']}")
    print(f"  MD:   {paths['md']}")
    print(f"  SVG:  {paths['svg']}")
    print(f"\n  RAG accuracy:   {report['rag']['accuracy']:.1%}")
    print(f"  OCTO accuracy:  {report['octo']['accuracy']:.1%}")
    print(f"  Delta:          {report['delta']:+.1%}")


if __name__ == "__main__":
    main()
