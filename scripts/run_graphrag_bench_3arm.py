#!/usr/bin/env python
"""
Run Step 3 3-Arm Generation Benchmark per docs/GATE1_SPEC.md §3.

Evaluates:
  1. base        : Un-augmented gpt-4o-mini (No context)
  2. vector_rag  : Dense BGE-Large vector retrieval over 1200-token chunks
  3. octo_graph  : OCTO Property Graph retrieval over Kùzu C++ Graph

Strictly outputs GraphRAG-Bench compatible JSON files for generation_eval.py and retrieval_eval.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import tiktoken

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src"), str(ROOT / "third_party" / "graphrag_bench_eval")):
    if p not in sys.path:
        sys.path.insert(0, p)

SYSTEM_PROMPT = "You are a helpful medical assistant answering patient questions accurately based on context. Reply concisely."

RAG_PROMPT_TEMPLATE = """\
Context Information is below:
---------------------
{context}
---------------------
Given the context information and not prior knowledge, answer the question.

Question: {question}
Answer:"""


def tokenize_text(text: str) -> set[str]:
    """Extract lowercased alphanumeric tokens from text."""
    return set(re.findall(r"\w+", text.lower()))


def compute_bootstrap_ci(scores: list[float], n_bootstraps: int = 1000, ci: float = 0.95) -> tuple[float, float]:
    """Compute non-parametric 95% bootstrap confidence intervals for a list of scores."""
    if not scores:
        return 0.0, 0.0
    boot_means: list[float] = []
    n = len(scores)
    rng = np.random.default_rng(42)
    for _ in range(n_bootstraps):
        sample = rng.choice(scores, size=n, replace=True)
        boot_means.append(float(np.mean(sample)))
    lower = float(np.percentile(boot_means, (1 - ci) / 2 * 100))
    upper = float(np.percentile(boot_means, (1 + ci) / 2 * 100))
    return round(lower, 4), round(upper, 4)


class VectorRetriever:
    """Dense vector retriever using sentence-transformers (BGE-Large or MiniLM)."""
    def __init__(self, corpus_chunks: list[dict[str, Any]], model_name: str = "BAAI/bge-large-en-v1.5"):
        from sentence_transformers import SentenceTransformer
        print(f"Initializing VectorRetriever with {model_name}...", flush=True)
        self.model_name = model_name
        self.st_model = SentenceTransformer(model_name)
        self.chunks = corpus_chunks
        
        # Encode corpus chunks (without query instruction prefix)
        chunk_texts = [c["text"] for c in corpus_chunks]
        self.chunk_embeddings = self.st_model.encode(chunk_texts, show_progress_bar=True, normalize_embeddings=True)

    def retrieve(self, question: str, top_k: int = 5, max_tokens: int = 4000) -> str:
        # BGE models require query instruction prefix
        if "bge" in self.model_name.lower():
            query_str = f"Represent this sentence for searching relevant passages: {question}"
        else:
            query_str = question
            
        q_emb = self.st_model.encode([query_str], normalize_embeddings=True)[0]
        scores = np.dot(self.chunk_embeddings, q_emb)
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        retrieved_texts = [self.chunks[idx]["text"] for idx in top_indices]
        full_context = "\n\n---\n\n".join(retrieved_texts)
        
        # Cap at max_tokens using tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(full_context)
        if len(tokens) > max_tokens:
            full_context = enc.decode(tokens[:max_tokens])
            
        return full_context


class GraphRetriever:
    """OCTO Property Graph retriever with BGE Dense Neural Node Matching & 2-Hop BFS Traversal."""
    def __init__(self, graph_data: dict[str, Any], embedding_model: str = "BAAI/bge-large-en-v1.5"):
        from sentence_transformers import SentenceTransformer
        self.nodes = graph_data.get("nodes", [])
        self.edges = graph_data.get("edges", [])
        self.nodes_by_id = {n["id"]: n for n in self.nodes}
        self.model_name = embedding_model

        # Build adjacency list for 2-Hop BFS Traversal
        self.adj = {}
        for n in self.nodes:
            self.adj[n["id"]] = []
        for e in self.edges:
            s, t = e.get("source"), e.get("target")
            if s in self.adj:
                self.adj[s].append((t, e))
            if t in self.adj:
                self.adj[t].append((s, e))

        # Dense BGE Neural Encoder for Nodes (Confound Fix: exact same encoder as Vector RAG)
        logger.info(f"Initializing GraphRetriever Node Encoder with {embedding_model}...")
        self.st_model = SentenceTransformer(embedding_model)
        self.node_texts = [f"{n.get('name', '')}: {n.get('type', '')}" for n in self.nodes]
        self.node_embeddings = self.st_model.encode(self.node_texts, normalize_embeddings=True, show_progress_bar=False)

    def retrieve(self, question: str, top_k: int = 5, max_tokens: int = 4000) -> str:
        # Query encoding with BGE instruction prefix
        if "bge" in self.model_name.lower():
            query_str = f"Represent this sentence for searching relevant passages: {question}"
        else:
            query_str = question

        q_emb = self.st_model.encode([query_str], normalize_embeddings=True)[0]
        
        # Dense cosine similarity node matching
        scores = np.dot(self.node_embeddings, q_emb)
        top_node_indices = np.argsort(scores)[::-1][:top_k]
        seed_node_ids = [self.nodes[idx]["id"] for idx in top_node_indices]

        # 2-Hop BFS Graph Traversal
        visited_nodes = set(seed_node_ids)
        traversed_edges: list[dict[str, Any]] = []
        seen_edge_keys = set()

        # Hop 1: Direct incident edges
        hop1_neighbors = []
        for n_id in seed_node_ids:
            for neighbor_id, edge in self.adj.get(n_id, []):
                e_key = (edge.get("source"), edge.get("target"), edge.get("relation"))
                if e_key not in seen_edge_keys:
                    seen_edge_keys.add(e_key)
                    traversed_edges.append(edge)
                if neighbor_id not in visited_nodes:
                    visited_nodes.add(neighbor_id)
                    hop1_neighbors.append(neighbor_id)

        # Hop 2: Secondary neighbor edges (Multi-Hop Path Expansion)
        for n_id in hop1_neighbors[:10]:
            for neighbor_id, edge in self.adj.get(n_id, []):
                e_key = (edge.get("source"), edge.get("target"), edge.get("relation"))
                if e_key not in seen_edge_keys:
                    seen_edge_keys.add(e_key)
                    traversed_edges.append(edge)

        if not traversed_edges:
            logger.warning(f"OCTO Graph Traversal found 0 matching edges for query: '{question[:60]}...'")
            return "RETRIEVED PROPERTY GRAPH SUBGRAPH:\nNo relevant graph paths found."

        # Format Graph Subgraph Context with Edge Provenance
        lines: list[str] = ["RETRIEVED PROPERTY GRAPH SUBGRAPH & PROVENANCE:"]
        for e in traversed_edges[: top_k * 12]:
            s_name = self.nodes_by_id.get(e["source"], {}).get("name", str(e["source"]))
            t_name = self.nodes_by_id.get(e["target"], {}).get("name", str(e["target"]))
            cid = e.get("source_chunk_id", "unknown")
            lines.append(f"- ({s_name}) --[{e.get('relation')}]--> ({t_name}) [source_chunk: {cid}]")

        full_context = "\n".join(lines)

        # Cap at max_tokens to equalize context budget with Vector RAG
        enc = tiktoken.get_encoding("cl100k_base")
        tokens = enc.encode(full_context)
        if len(tokens) > max_tokens:
            full_context = enc.decode(tokens[:max_tokens])

        return full_context


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Step 3 3-Arm Generation Benchmark per docs/GATE1_SPEC.md")
    ap.add_argument("--corpus", default="data/graphrag_bench/medical_corpus.json")
    ap.add_argument("--graph", default="data/graphrag_bench/graph_out/graph.json")
    ap.add_argument("--questions", default="data/graphrag_bench/medical_questions.json")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--embedding-model", default="BAAI/bge-large-en-v1.5")
    ap.add_argument("--limit-questions", type=int, default=None, help="Evaluate first N questions only")
    ap.add_argument("--out-dir", default="data/graphrag_bench/results")
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key and "openai" in args.base_url.lower():
        print("OPENAI_API_KEY is not set. Refusing to run.", file=sys.stderr)
        return 2

    from openai import OpenAI
    client = OpenAI(api_key=key or "ollama", base_url=args.base_url)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load corpus, graph, and questions
    corpus_raw = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    if isinstance(corpus_raw, dict):
        text = corpus_raw.get("context") or corpus_raw.get("text") or str(corpus_raw)
    else:
        text = str(corpus_raw)

    # Build 1200-token chunks for vector_rag (identical to graph build)
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunk_size, overlap = 1200, 100
    step = chunk_size - overlap
    chunks = [{"chunk_id": f"chunk_{i:04d}", "text": enc.decode(tokens[i : i + chunk_size])}
              for i in range(0, len(tokens), step)]

    graph_data = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))

    if args.limit_questions:
        questions = questions[: args.limit_questions]

    print(f"STEP 3 3-ARM BENCHMARK: {len(questions)} questions across base, vector_rag, octo_graph", flush=True)

    # Initialize Retrievers
    vec_retriever = VectorRetriever(chunks, model_name=args.embedding_model)
    graph_retriever = GraphRetriever(graph_data, embedding_model=args.embedding_model)

    arms = ["base", "vector_rag", "octo_graph"]
    results_by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arms}

    for i, q_item in enumerate(questions):
        q_id = q_item.get("id", f"q_{i:04d}")
        q_text = q_item.get("question", "")
        q_source = q_item.get("source", "Medical")
        q_type = q_item.get("question_type", "Fact Retrieval")
        evidence = q_item.get("evidence", [])
        ground_truth = q_item.get("answer") or q_item.get("ground_truth") or ""

        if i % 10 == 0 or i == len(questions) - 1:
            print(f"  Question {i+1}/{len(questions)} [{q_type}] id={q_id}...", flush=True)

        for arm in arms:
            if arm == "base":
                context_str = ""
                user_msg = q_text
            elif arm == "vector_rag":
                context_str = vec_retriever.retrieve(q_text, top_k=5, max_tokens=4000)
                user_msg = RAG_PROMPT_TEMPLATE.format(context=context_str, question=q_text)
            elif arm == "octo_graph":
                context_str = graph_retriever.retrieve(q_text, top_k=5, max_tokens=4000)
                user_msg = RAG_PROMPT_TEMPLATE.format(context=context_str, question=q_text)

            try:
                resp = client.chat.completions.create(
                    model=args.model,
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg}
                    ]
                )
                gen_answer = resp.choices[0].message.content or ""
            except Exception as e:
                print(f"  [{arm}] question {i+1} failed: {e}", file=sys.stderr)
                gen_answer = ""

            record = {
                "id": q_id,
                "question": q_text,
                "source": q_source,
                "context": context_str,
                "evidence": evidence,
                "question_type": q_type,
                "generated_answer": gen_answer,
                "ground_truth": ground_truth,
                "gold_answer": ground_truth
            }
            results_by_arm[arm].append(record)

    # Save output JSONs (flat and grouped by question_type for GraphRAG-Bench compatibility)
    for arm in arms:
        flat_path = out_dir / f"{arm}.json"
        flat_path.write_text(json.dumps(results_by_arm[arm], indent=2), encoding="utf-8")

        grouped_data: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in results_by_arm[arm]:
            grouped_data[item["question_type"]].append(item)

        grouped_path = out_dir / f"{arm}_grouped.json"
        grouped_path.write_text(json.dumps(dict(grouped_data), indent=2), encoding="utf-8")

        print(f"  Wrote {flat_path} ({len(results_by_arm[arm])} items) and {grouped_path}")

    print("\n" + "=" * 60)
    print("STEP 3 3-ARM BENCHMARK GENERATION COMPLETE")
    print(f"  evaluated questions : {len(questions)}")
    print(f"  arms executed       : {', '.join(arms)}")
    print(f"  results directory   : {out_dir}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
