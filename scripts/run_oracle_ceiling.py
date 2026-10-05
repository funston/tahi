import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path

from metrics.rouge import compute_rouge_score
from openai import OpenAI


def main():
    parser = argparse.ArgumentParser(description="TAHI Step 1: Oracle Ceiling Test (TAHI_PLAN §2)")
    parser.add_argument("--questions", type=str, default="data/graphrag_bench/medical_questions.json")
    parser.add_argument("--graph", type=str, default="data/graphrag_bench/graph_clean/graph.json")
    parser.add_argument("--corpus", type=str, default="data/graphrag_bench/medical_corpus.json")
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=str, default="data/graphrag_bench/oracle")
    args = parser.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY is missing.", file=sys.stderr)
        return 1

    client = OpenAI(api_key=key)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load questions, graph, corpus
    questions = json.load(open(args.questions))
    graph_data = json.load(open(args.graph))

    # Filter Complex Reasoning questions
    complex_q = [q for q in questions if q.get("question_type") == "Complex Reasoning"]
    random.seed(args.seed)
    sampled_q = random.sample(complex_q, min(args.sample_size, len(complex_q)))

    # Map graph nodes & edges
    nodes_by_id = {n["id"]: n for n in graph_data["nodes"]}
    name_to_node_id = {n.get("name", "").lower().strip(): n["id"] for n in graph_data["nodes"]}

    adj = {n["id"]: [] for n in graph_data["nodes"]}
    for e in graph_data["edges"]:
        s, t = e.get("source"), e.get("target")
        if s in adj:
            adj[s].append((t, e))
        if t in adj:
            adj[t].append((s, e))

    print("\n============================================================")
    print("TAHI ORACLE CEILING TEST (TAHI_PLAN §2)")
    print(f"Sample: {len(sampled_q)} Complex Reasoning Questions (Seed {args.seed})")
    print("============================================================\n")

    oracle_vector_results = []
    oracle_graph_results = []

    for idx, q in enumerate(sampled_q):
        question_text = q["question"]
        gold_answer = q.get("answer") or q.get("gold_answer") or q.get("ground_truth", "")
        gold_evidence_text = q.get("evidence", "")

        # 1. Oracle Vector Arm: Gold Evidence Text Served Direct
        vec_prompt = f"Background Information:\n{gold_evidence_text}\n\nQuestion: {question_text}\n\nAnswer briefly and accurately:"
        vec_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": vec_prompt}],
            temperature=0.0
        ).choices[0].message.content.strip()

        # 2. Oracle Graph Arm: Actual Graph Triples Seeded by Gold Entities
        ev_text = (gold_evidence_text + " " + q.get("evidence_relations", "")).lower()
        matched_node_ids = [n_id for name, n_id in name_to_node_id.items() if len(name) > 3 and name in ev_text]
        matched_node_ids = list(set(matched_node_ids))

        graph_lines = ["PROPERTY GRAPH TRIPLES (ACTUALLY PRESENT IN GRAPH):"]
        seen_edges = set()
        for n_id in matched_node_ids[:10]:
            for _neighbor_id, edge in adj.get(n_id, []):
                e_key = (edge.get("source"), edge.get("target"), edge.get("relation"))
                if e_key not in seen_edges:
                    seen_edges.add(e_key)
                    s_name = nodes_by_id.get(edge["source"], {}).get("name", str(edge["source"]))
                    t_name = nodes_by_id.get(edge["target"], {}).get("name", str(edge["target"]))
                    graph_lines.append(f"- ({s_name}) --[{edge.get('relation')}]--> ({t_name})")

        graph_context = "\n".join(graph_lines)
        graph_prompt = f"Background Graph Knowledge:\n{graph_context}\n\nQuestion: {question_text}\n\nAnswer briefly and accurately:"
        graph_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": graph_prompt}],
            temperature=0.0
        ).choices[0].message.content.strip()

        oracle_vector_results.append({
            "question": question_text,
            "gold_answer": gold_answer,
            "generated_answer": vec_resp
        })
        oracle_graph_results.append({
            "question": question_text,
            "gold_answer": gold_answer,
            "generated_answer": graph_resp
        })
        print(f"[{idx+1}/{len(sampled_q)}] Processed Question: '{question_text[:50]}...'")

    # Evaluate ROUGE-L using vendored metric
    async def evaluate():
        v_scores = [await compute_rouge_score(r["generated_answer"], r["gold_answer"]) for r in oracle_vector_results]
        g_scores = [await compute_rouge_score(r["generated_answer"], r["gold_answer"]) for r in oracle_graph_results]

        v_mean = sum(v_scores) / len(v_scores) * 100
        g_mean = sum(g_scores) / len(g_scores) * 100

        print("\n============================================================")
        print("ORACLE CEILING TEST RESULTS (ROUGE-L %)")
        print("============================================================")
        print(f"oracle_vector (Gold Text Chunks) : {v_mean:.2f}%")
        print(f"oracle_graph  (Actual Triples)  : {g_mean:.2f}%")
        print(f"Delta (oracle_graph - oracle_vec): {g_mean - v_mean:+.2f}%")
        print("============================================================\n")

        artifact = {
            "sample_size": len(sampled_q),
            "seed": args.seed,
            "oracle_vector_mean_rouge": round(v_mean, 2),
            "oracle_graph_mean_rouge": round(g_mean, 2),
            "delta": round(g_mean - v_mean, 2),
            "oracle_vector_results": oracle_vector_results,
            "oracle_graph_results": oracle_graph_results
        }
        json.dump(artifact, open(out_dir / "oracle_results.json", "w"), indent=2)
        print(f"Saved artifact to {out_dir / 'oracle_results.json'}")

    asyncio.run(evaluate())

if __name__ == "__main__":
    main()
