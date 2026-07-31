#!/usr/bin/env python3
"""
kimi_wikipedia_benchmark.py

Benchmark harness for the Kimi Wikipedia multi-hop QA coprocessor against
HotpotQA, 2WikiMultiHopQA, MuSiQue, and FRAMES-style multi-hop questions.

This is a scaffold that defines the expected interface and evaluation metrics.
A full run requires downloading the datasets and a world model built from Wikipedia.

Usage:
  PYTHONPATH=src:. python examples/kimi_wikipedia_benchmark.py \
      --world-model path/to/world_model.json.gz \
      --dataset hotpotqa \
      --input path/to/hotpotqa_dev.jsonl \
      --output kimi_wikipedia_hotpotqa_report.json

No existing files are modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from implementations.kimi_wikipedia import KimiWikipediaCoprocessor
from bender.world_state import WorldModel


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def exact_match(prediction: str, gold: str) -> bool:
    return normalize(prediction) == normalize(gold)


def f1_score(prediction: str, gold: str) -> float:
    pred_tokens = set(normalize(prediction).split())
    gold_tokens = set(normalize(gold).split())
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    overlap = pred_tokens & gold_tokens
    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(gold_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def bridge_entity_recall(predicted_path: list[str], gold_bridge: str | None) -> bool:
    if gold_bridge is None:
        return False
    gold_norm = normalize(gold_bridge)
    return any(gold_norm in normalize(node) for node in predicted_path)


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def baseline_no_retrieval(question: str) -> str:
    """Placeholder: returns empty / would call LLM with no retrieval."""
    return ""


def baseline_single_shot_rag(
    question: str,
    world_model: WorldModel,
    top_k: int = 5,
) -> str:
    """Placeholder for single-shot RAG baseline over wiki chunks."""
    retrievals = world_model.retrieve(question, top_k=top_k)
    context = "\n".join(r.label for r in retrievals)
    return f"[single-shot RAG context]\n{context}"


def baseline_iterative_rag(
    question: str,
    world_model: WorldModel,
    steps: int = 3,
) -> str:
    """Placeholder for iterative RAG baseline: re-retrieve after extracting entities."""
    context_parts = []
    current_query = question
    for _ in range(steps):
        retrievals = world_model.retrieve(current_query, top_k=3)
        context_parts.extend(r.label for r in retrievals)
        # in a real implementation, extract next query from retrieved text
        break
    return "[iterative RAG context]\n" + "\n".join(context_parts)


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def make_bender_answer_fn(
    world_model: WorldModel,
    llm_generate_fn: Callable[[str], str] | None = None,
) -> Callable[[str], dict[str, Any]]:
    coprocessor = KimiWikipediaCoprocessor.from_world_model(world_model, top_k=8, max_hops=4)

    def answer(question: str) -> dict[str, Any]:
        return coprocessor.generate_answer(question, llm_generate_fn=llm_generate_fn)

    return answer


# ---------------------------------------------------------------------------
# Dataset loaders (scaffolds)
# ---------------------------------------------------------------------------

def load_hotpotqa(path: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Load HotpotQA dev set."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("data", [])
    tasks = []
    for item in data[:limit]:
        tasks.append({
            "id": item.get("_id"),
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "type": item.get("type", "bridge"),
            "gold_bridge": _extract_hotpot_bridge(item),
        })
    return tasks


def load_jsonl(path: str, limit: int | None = None) -> list[dict[str, Any]]:
    tasks = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            tasks.append(json.loads(line))
    return tasks


def _extract_hotpot_bridge(item: dict[str, Any]) -> str | None:
    """Try to extract the bridge entity from HotpotQA supporting facts."""
    support = item.get("supporting_facts", [])
    if len(support) >= 2:
        return support[0][0]  # title of first supporting doc as proxy
    return None


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_system(
    name: str,
    answer_fn: Callable[[str], dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    results = []
    em_total = 0.0
    f1_total = 0.0
    bridge_recall_total = 0.0
    bridge_count = 0

    for task in tasks:
        question = task["question"]
        gold = task.get("answer", "")
        gold_bridge = task.get("gold_bridge")

        output = answer_fn(question)
        prediction = output.get("answer") or ""
        path = output.get("candidate_path_labels", [])

        em = exact_match(prediction, gold)
        f1 = f1_score(prediction, gold)
        bridge_hit = bridge_entity_recall(path, gold_bridge) if gold_bridge else None

        em_total += float(em)
        f1_total += f1
        if gold_bridge:
            bridge_recall_total += float(bridge_hit or False)
            bridge_count += 1

        results.append({
            "id": task.get("id"),
            "question": question,
            "gold": gold,
            "prediction": prediction,
            "exact_match": em,
            "f1": f1,
            "bridge_recall": bridge_hit,
            "candidate_path": path,
        })

    n = len(tasks) or 1
    return {
        "system": name,
        "tasks_evaluated": len(tasks),
        "exact_match": em_total / n,
        "f1": f1_total / n,
        "bridge_recall": bridge_recall_total / bridge_count if bridge_count else None,
        "results": results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Kimi Wikipedia coprocessor.")
    parser.add_argument("--world-model", required=True, help="Path to built world model JSON(.gz).")
    parser.add_argument("--dataset", choices=["hotpotqa", "2wikimultihopqa", "musique", "frames"], required=True)
    parser.add_argument("--input", required=True, help="Path to dataset file.")
    parser.add_argument("--output", required=True, help="Output JSON report path.")
    parser.add_argument("--limit", type=int, help="Limit number of tasks.")
    parser.add_argument("--no-llm", action="store_true", help="Run without LLM; measure retrieval/control only.")
    args = parser.parse_args()

    print(f"Loading world model from {args.world_model}...")
    world_model = WorldModel.load_json(args.world_model)

    print(f"Loading {args.dataset} from {args.input}...")
    if args.dataset == "hotpotqa":
        tasks = load_hotpotqa(args.input, limit=args.limit)
    else:
        tasks = load_jsonl(args.input, limit=args.limit)
    print(f"Loaded {len(tasks)} tasks.")

    # LLM stub — replace with real model call
    def llm_stub(prompt: str) -> str:
        return "[LLM answer not configured — replace llm_stub with real generator]"

    llm_generate_fn = None if args.no_llm else llm_stub

    systems = {
        "bender": make_bender_answer_fn(world_model, llm_generate_fn),
        # "single_shot_rag": lambda q: {"answer": baseline_single_shot_rag(q, world_model)},
        # "iterative_rag": lambda q: {"answer": baseline_iterative_rag(q, world_model)},
    }

    report = {
        "dataset": args.dataset,
        "world_model": args.world_model,
        "systems": [],
    }
    for name, answer_fn in systems.items():
        print(f"Evaluating {name}...")
        result = evaluate_system(name, answer_fn, tasks)
        report["systems"].append(result)
        print(f"  EM: {result['exact_match']:.3f}, F1: {result['f1']:.3f}, Bridge recall: {result['bridge_recall']}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote report to {args.output}")


if __name__ == "__main__":
    main()
