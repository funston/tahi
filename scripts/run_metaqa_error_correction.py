import argparse
import json
import os
import random
import sys
from pathlib import Path

import networkx as nx
from openai import OpenAI


def normalize_entity(s: str) -> str:
    return s.strip().lower()

def exact_match_score(predicted_text: str, gold_answers: list[str]) -> str:
    """Classify response into RIGHT, WRONG, or MISSING based on exact match of entity answers."""
    pred_lower = predicted_text.lower()
    gold_lowers = [a.lower().strip() for a in gold_answers]

    if not predicted_text.strip() or "none" in pred_lower or "unknown" in pred_lower:
        return "MISSING"

    # Check how many gold entities are mentioned in the prediction
    found = [g for g in gold_lowers if g in pred_lower]

    if len(found) == len(gold_lowers):
        return "RIGHT"
    elif len(found) > 0:
        return "WRONG" # Partial / incomplete
    else:
        return "WRONG" # Hallucinated / wrong

def load_metaqa_graph(kb_path: Path) -> tuple[nx.Graph, dict]:
    G = nx.Graph()
    with open(kb_path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) == 3:
                s, r, o = parts[0].strip(), parts[1].strip(), parts[2].strip()
                G.add_edge(s, o, relation=r)
    return G

def main():
    parser = argparse.ArgumentParser(description="MetaQA 3-Hop Error Correction Experiment (HANDOVER_CRITICAL_REVIEW §8)")
    parser.add_argument("--metaqa-dir", type=str, default="data/metaqa")
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=str, default="data/metaqa/results")
    args = parser.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("Error: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
        return 1

    client = OpenAI(api_key=key)
    metaqa_dir = Path(args.metaqa_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load MetaQA Graph and 3-Hop Test Questions
    print("Loading MetaQA Graph (kb.txt)...")
    graph = load_metaqa_graph(metaqa_dir / "kb.txt")
    print(f"MetaQA Graph Loaded: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges.")

    qa_data = json.load(open(metaqa_dir / "qa_3hop_test.json"))
    random.seed(args.seed)
    sampled_qa = random.sample(qa_data, min(args.sample_size, len(qa_data)))

    print("\n============================================================")
    print("METAQA 3-HOP ERROR-CORRECTION EXPERIMENT")
    print(f"Sample: {len(sampled_qa)} 3-Hop Questions (Seed {args.seed})")
    print("============================================================\n")

    baseline_results = []

    # STEP 1: Standard Vector RAG Baseline
    for idx, q in enumerate(sampled_qa):
        q_text = q["question"]
        q_entities = q["q_entity"]
        gold_ans = q["answers"]

        # Retrieve text context from graph neighbors
        retrieved_triples = []
        for entity in q_entities:
            if entity in graph:
                for neighbor in graph.neighbors(entity):
                    rel = graph[entity][neighbor].get("relation", "related_to")
                    retrieved_triples.append(f"({entity}) --[{rel}]--> ({neighbor})")

        text_context = "\n".join(retrieved_triples[:15])
        prompt = f"Knowledge Context:\n{text_context}\n\nQuestion: {q_text}\n\nAnswer with the exact entity list:"

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        ).choices[0].message.content.strip()

        status = exact_match_score(resp, gold_ans)
        baseline_results.append({
            "id": q["id"],
            "question": q_text,
            "q_entity": q_entities,
            "gold_answers": gold_ans,
            "baseline_pred": resp,
            "baseline_status": status
        })
        print(f"[{idx+1}/{len(sampled_qa)}] Baseline Status: {status:7s} | Question: '{q_text[:50]}...'")

    # STEP 2: Re-Run WITH 3-Hop In-Generation Graph Traversal Query
    final_results = []
    transition_matrix = {
        ("RIGHT", "RIGHT"): 0, ("RIGHT", "WRONG"): 0, ("RIGHT", "MISSING"): 0,
        ("WRONG", "RIGHT"): 0, ("WRONG", "WRONG"): 0, ("WRONG", "MISSING"): 0,
        ("MISSING", "RIGHT"): 0, ("MISSING", "WRONG"): 0, ("MISSING", "MISSING"): 0
    }

    print("\n------------------------------------------------------------")
    print("Re-running with In-Generation 3-Hop Graph Traversal...")
    print("------------------------------------------------------------\n")

    for _idx, item in enumerate(baseline_results):
        q_text = item["question"]
        q_entities = item["q_entity"]
        gold_ans = item["gold_answers"]
        b_status = item["baseline_status"]

        # Execute 3-Hop BFS Traversal from q_entities
        subgraph_triples = []
        for seed_ent in q_entities:
            if seed_ent in graph:
                # Hop 1
                for h1 in list(graph.neighbors(seed_ent))[:8]:
                    rel1 = graph[seed_ent][h1].get("relation", "rel")
                    subgraph_triples.append(f"({seed_ent}) -> [{rel1}] -> ({h1})")
                    # Hop 2
                    for h2 in list(graph.neighbors(h1))[:5]:
                        rel2 = graph[h1][h2].get("relation", "rel")
                        subgraph_triples.append(f"  ({h1}) -> [{rel2}] -> ({h2})")
                        # Hop 3
                        for h3 in list(graph.neighbors(h2))[:3]:
                            rel3 = graph[h2][h3].get("relation", "rel")
                            subgraph_triples.append(f"    ({h2}) -> [{rel3}] -> ({h3})")

        graph_context = "\n".join(subgraph_triples[:30])
        gcca_prompt = f"Graph 3-Hop Traversal Knowledge:\n{graph_context}\n\nQuestion: {q_text}\n\nAnswer with the exact entity list:"

        gcca_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": gcca_prompt}],
            temperature=0.0
        ).choices[0].message.content.strip()

        graph_status = exact_match_score(gcca_resp, gold_ans)
        transition_matrix[(b_status, graph_status)] += 1

        final_results.append({
            **item,
            "graph_pred": gcca_resp,
            "graph_status": graph_status
        })

    # STEP 3: Report Paired Transition Table
    a = transition_matrix[("RIGHT", "RIGHT")]
    b = transition_matrix[("RIGHT", "WRONG")]
    c = transition_matrix[("RIGHT", "MISSING")]

    d = transition_matrix[("WRONG", "RIGHT")]
    e = transition_matrix[("WRONG", "WRONG")]
    f = transition_matrix[("WRONG", "MISSING")]

    g = transition_matrix[("MISSING", "RIGHT")]
    h = transition_matrix[("MISSING", "WRONG")]
    i = transition_matrix[("MISSING", "MISSING")]

    fixed = d + g
    broken = b + c
    net_correction = fixed - broken

    print("\n============================================================")
    print("METAQA 3-HOP PAIRED TRANSITION TABLE (HANDOVER §8)")
    print("============================================================")
    print("                      AFTER GRAPH INJECTION")
    print("              RIGHT        WRONG       MISSING")
    print(f"RIGHT       {a:6d}       {b:6d}       {c:6d}   <- {b+c} BROKEN by Graph")
    print(f"WRONG       {d:6d}       {e:6d}       {f:6d}   <- {d} FIXED by Graph")
    print(f"MISSING     {g:6d}       {h:6d}       {i:6d}   <- {g} FILLED by Graph")
    print("============================================================")
    print(f"Total Questions Evaluated       : {len(sampled_qa)}")
    print(f"Previously Wrong / Missing      : {d+e+f+g+h+i}")
    print(f"Total Fixed by Graph (d + g)    : {fixed}")
    print(f"Total Broken by Graph (b + c)   : {broken}")
    print(f"NET CORRECTION SCORE            : {net_correction:+d}")
    print("============================================================\n")

    out_file = out_dir / "metaqa_transition_results.json"
    with open(out_file, "w") as out_f:
        json.dump({
            "sample_size": len(sampled_qa),
            "seed": args.seed,
            "transition_matrix": {f"{k[0]}_to_{k[1]}": v for k, v in transition_matrix.items()},
            "net_correction": net_correction,
            "results": final_results
        }, out_f, indent=2)

    print(f"Saved results artifact to {out_file}")

if __name__ == "__main__":
    main()
