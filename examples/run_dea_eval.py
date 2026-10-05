#!/usr/bin/env python3
"""Run the TAHI drug-enforcement coprocessor evaluation.

Usage:
    export OPENAI_API_KEY="..."
    python examples/run_dea_eval.py [--verbose]

Output is written to:
    ./results/dea.json   (raw)
    ./results/dea.md     (table + ASCII chart)
    ./results/dea.svg    (bar chart)
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from implementations.drug_enforcement import evaluate_drug_coprocessor
from implementations.drug_enforcement.dea_eval import (
    DEA_ACTIONS,
    DEA_ANALOGUE_RELATIONSHIPS,
    DEA_SCHEDULES,
    DEA_SUBSTANCES,
    _coprocessor_documents,
    build_default_coprocessor,
    load_dea_eval_questions,
)
from tahi.baseline_rag import StandaloneRAG
from tahi.results_reporter import write_eval_artifacts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Print per-question evidence and answers")
    args = parser.parse_args()

    if args.verbose:
        _run_verbose()
        return

    report = evaluate_drug_coprocessor()

    meta = {
        "eval": "drug_enforcement",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    paths = write_eval_artifacts(ROOT / "results", "dea", report, meta)

    print(f"DEA eval written to:")
    print(f"  JSON: {paths['json']}")
    print(f"  MD:   {paths['md']}")
    print(f"  SVG:  {paths['svg']}")
    print(f"\n  RAG accuracy:   {report['rag']['accuracy']:.1%}")
    print(f"  TAHI accuracy:  {report['tahi']['accuracy']:.1%}")
    print(f"  Delta:          {report['delta']:+.1%}")


def _run_verbose():
    """Run standalone RAG and TAHI side-by-side and print every prompt/answer/evidence."""
    coprocessor = build_default_coprocessor()

    # Standalone RAG over the same raw documents; no graph access.
    rag = StandaloneRAG(top_k=5)
    rag.add_documents(_coprocessor_documents(coprocessor))
    rag.build_index()

    questions = load_dea_eval_questions()
    for q in questions:
        print("=" * 80)
        print(f"QUESTION: {q.text}")
        print(f"EXPECTED: {q.answer}")
        print()

        rag_answer, rag_model, rag_evidence = rag.answer(
            q.text,
            system="You answer controlled-substance questions from provided DEA sources only.",
        )
        tahi_packet = coprocessor.answer(q)

        print("--- RAG EVIDENCE ---")
        for i, e in enumerate(rag_evidence):
            print(f"[{i+1}] {e.doc_id} (score {e.score:.3f})")
            print(f"    {e.text[:200]}")
        print(f"RAG ANSWER: {rag_answer}")
        print(f"RAG MODEL:  {rag_model}")
        print()

        print("--- TAHI EVIDENCE ---")
        for i, e in enumerate(tahi_packet.evidence):
            print(f"[{i+1}] {e['node_id']} (score {e['score']:.3f}, origin {e['origin']})")
            print(f"    {e['text'][:200]}")
        print(f"TAHI ANSWER: {tahi_packet.answer}")
        print(f"TAHI MODEL:  {tahi_packet.model}")
        print()


if __name__ == "__main__":
    main()
