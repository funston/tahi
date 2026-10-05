#!/usr/bin/env python
"""
Run Step 2 Evidence Recall Verification Gate per docs/GATE1_SPEC.md §2.

Measures what percentage of gold facts in `medical_questions.json` are present
in the built Property Graph (`graph.json`).

Question-specific graph context: Retrieves top-K graph nodes and edges matching
each question's entities/keywords rather than taking a static global snippet.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src"), str(ROOT / "third_party" / "graphrag_bench_eval")):
    if p not in sys.path:
        sys.path.insert(0, p)

from metrics.evidence_recall import compute_evidence_recall  # noqa: E402


class CustomOpenAILLM:
    """Lightweight LangChain-compatible wrapper for OpenAI / Ollama calls."""
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None, base_url: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or "ollama"
        self.base_url = base_url or "https://api.openai.com/v1"
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def ainvoke(self, prompt: str, config: dict | None = None) -> Any:
        resp = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}]
        )
        class ResponseWrapper:
            def __init__(self, content: str):
                self.content = content
        return ResponseWrapper(resp.choices[0].message.content or "")


def tokenize_text(text: str) -> set[str]:
    """Extract lowercased alphanumeric tokens from text."""
    return set(re.findall(r"\w+", text.lower()))


def build_question_relevant_graph_context(
    question: str,
    graph_nodes: list[dict[str, Any]],
    graph_edges: list[dict[str, Any]],
    nodes_by_id: dict[str, dict[str, Any]],
    max_triples: int = 50
) -> str:
    """Retrieve top-K graph nodes and edges matching words/concepts in the question."""
    q_tokens = tokenize_text(question)

    # Score nodes by word overlap with query
    scored_nodes: list[tuple[float, str]] = []
    for n in graph_nodes:
        n_name = n.get("name", "")
        n_tokens = tokenize_text(n_name)
        if not n_tokens:
            continue
        overlap = len(q_tokens & n_tokens)
        if overlap > 0:
            scored_nodes.append((overlap / len(n_tokens), n["id"]))

    scored_nodes.sort(key=lambda x: x[0], reverse=True)
    top_node_ids = {n_id for _, n_id in scored_nodes[:max_triples]}

    # Collect edges connecting top nodes or matching query tokens
    relevant_edges: list[dict[str, Any]] = []
    for e in graph_edges:
        s_id, t_id, r = e.get("source"), e.get("target"), e.get("relation")
        s_name = nodes_by_id.get(s_id, {}).get("name", str(s_id))
        t_name = nodes_by_id.get(t_id, {}).get("name", str(t_id))

        if s_id in top_node_ids or t_id in top_node_ids:
            relevant_edges.append(e)
        else:
            e_tokens = tokenize_text(f"{s_name} {r} {t_name}")
            if len(q_tokens & e_tokens) >= 2:
                relevant_edges.append(e)

    # Fallback if keyword match found few triples: include first edges
    if len(relevant_edges) < 10:
        relevant_edges = graph_edges[:max_triples]

    # Format context string
    lines: list[str] = ["RETRIEVED GRAPH FACTS:"]
    for e in relevant_edges[:max_triples]:
        s_name = nodes_by_id.get(e["source"], {}).get("name", str(e["source"]))
        t_name = nodes_by_id.get(e["target"], {}).get("name", str(e["target"]))
        lines.append(f"- ({s_name}) --[{e['relation']}]--> ({t_name})")

    return "\n".join(lines)


import random


def get_stratified_questions(questions: list[dict[str, Any]], n_total: int = 100, seed: int = 42) -> list[dict[str, Any]]:
    random.seed(seed)
    by_type: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for q in questions:
        by_type[q.get("question_type", "Fact Retrieval")].append(q)

    per_type = max(1, n_total // len(by_type))
    sampled: list[dict[str, Any]] = []
    for _q_type, q_list in sorted(by_type.items()):
        sampled.extend(random.sample(q_list, min(per_type, len(q_list))))
    return sampled


async def main_async() -> int:
    ap = argparse.ArgumentParser(description="Run Step 2 Evidence Recall Verification Gate per docs/GATE1_SPEC.md")
    ap.add_argument("--graph", default="data/graphrag_bench/graph_out/graph.json")
    ap.add_argument("--questions", default="data/graphrag_bench/medical_questions.json")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--limit-questions", type=int, default=None, help="Process N questions")
    ap.add_argument("--stratified", action="store_true", help="Use stratified random sampling across question types")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for stratified sampling")
    ap.add_argument("--out", default="data/graphrag_bench/graph_out/evidence_recall_results.json")
    args = ap.parse_args()

    graph_path = Path(args.graph)
    if not graph_path.exists():
        print(f"Error: graph file not found: {args.graph}", file=sys.stderr)
        return 1

    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"Error: questions file not found: {args.questions}", file=sys.stderr)
        return 1

    graph_data = json.loads(graph_path.read_text(encoding="utf-8"))
    questions_data = json.loads(questions_path.read_text(encoding="utf-8"))

    if args.limit_questions:
        if args.stratified:
            questions_data = get_stratified_questions(questions_data, n_total=args.limit_questions, seed=args.seed)
        else:
            questions_data = questions_data[: args.limit_questions]

    llm = CustomOpenAILLM(model=args.model, base_url=args.base_url)

    graph_nodes = graph_data.get("nodes", [])
    graph_edges = graph_data.get("edges", [])
    nodes_by_id = {n["id"]: n for n in graph_nodes}

    print(f"STEP 2 EVIDENCE RECALL GATE: {len(questions_data)} questions against graph ({len(graph_nodes)} nodes, {len(graph_edges)} edges)", flush=True)

    type_scores: defaultdict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []
    started = time.perf_counter()

    for i, q in enumerate(questions_data):
        q_text = q.get("question", "")
        q_type = q.get("question_type", "Unknown")
        evidence_list = q.get("evidence", [])

        if not evidence_list:
            continue

        if isinstance(evidence_list, str):
            evidence_list = [evidence_list]

        # Retrieve question-specific graph context
        context_str = build_question_relevant_graph_context(
            question=q_text,
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
            nodes_by_id=nodes_by_id,
            max_triples=50
        )

        if i % 10 == 0 or i == len(questions_data) - 1:
            mean_so_far = sum(all_scores) / len(all_scores) if all_scores else 0.0
            print(f"  Question {i+1}/{len(questions_data)} [{q_type}] current recall mean: {mean_so_far:.4f}...", flush=True)

        try:
            score = await compute_evidence_recall(
                question=q_text,
                contexts=[context_str],
                reference_evidence=evidence_list,
                llm=llm
            )
            if score is not None and not (isinstance(score, float) and score != score):  # filter NaN
                all_scores.append(score)
                type_scores[q_type].append(score)
        except Exception as e:
            print(f"  Question {i+1} failed: {e}", file=sys.stderr)

    overall_recall = sum(all_scores) / len(all_scores) if all_scores else 0.0
    type_averages = {k: round(sum(v) / len(v), 4) for k, v in type_scores.items() if v}
    wall_clock = round(time.perf_counter() - started, 1)

    out_data = {
        "spec": "docs/GATE1_SPEC.md §2",
        "model": args.model,
        "graph_file": args.graph,
        "questions_file": args.questions,
        "questions_evaluated": len(all_scores),
        "overall_evidence_recall": round(overall_recall, 4),
        "recall_by_question_type": type_averages,
        "wall_clock_s": wall_clock,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("STEP 2 EVIDENCE RECALL GATE RESULTS")
    print(f"  evaluated questions   : {len(all_scores)}")
    print(f"  OVERALL EVIDENCE RECALL: {overall_recall * 100:.2f}%")
    print("  per question type recall:")
    for k, v in type_averages.items():
        print(f"    - {k:22s}: {v * 100:.2f}%")
    print(f"  wall clock             : {wall_clock}s")
    print(f"  wrote results to       : {args.out}")
    print("=" * 60)

    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
