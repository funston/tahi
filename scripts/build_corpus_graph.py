#!/usr/bin/env python
"""
Build a typed property graph from a raw text corpus according to docs/GATE1_SPEC.md.

Implements GraphRAG-Bench / LightRAG specification:
- 1200-token chunking with tiktoken tokenizer.
- Schema guidance (derived_schema.json) without hard rejection.
- 1 extra aggressive gleaning pass to catch missed facts.
- Node merging by normalized entity name.
- Provenance tracking (source_chunk_id on every edge).
- Exports graph.json, graph.graphml (via networkx), and manifest.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
import tiktoken

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Load derived schema suggestions if available
SCHEMA_PATH = ROOT / "data" / "graphrag_bench" / "derived_schema.json"
SUGGESTED_KINDS = [
    "Disease", "Symptom", "RiskFactor", "Treatment", "Test",
    "BodyPart", "Gene", "Drug", "Stage", "Anatomy", "Procedure"
]
SUGGESTED_RELATIONS = [
    "has_symptom", "treated_by", "diagnosed_by", "located_in", "has_stage",
    "subtype_of", "associated_with", "increases_risk_of", "treats", "targets",
    "metastasizes_to", "causes", "indicates", "prevents"
]

if SCHEMA_PATH.exists():
    try:
        schema_data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        if "kinds" in schema_data:
            SUGGESTED_KINDS = sorted(set(SUGGESTED_KINDS + schema_data["kinds"]))
        if "relations" in schema_data:
            SUGGESTED_RELATIONS = sorted(set(SUGGESTED_RELATIONS + schema_data["relations"]))
    except Exception as e:
        print(f"Warning: Failed to parse derived_schema.json: {e}", file=sys.stderr)

RELATION_CANONICAL_MAP = {
    "metastazises_to": "metastasizes_to",
    "metastazies_to": "metastasizes_to",
    "can_metastasize_to": "metastasizes_to",
    "can_metastasize": "metastasizes_to",
    "is_metastatic": "metastasizes_to",
}

def normalize_relation(rel_str: str) -> str:
    r = rel_str.strip().lower().replace(" ", "_")
    return RELATION_CANONICAL_MAP.get(r, r)

SYSTEM_PROMPT = (
    "You are a Knowledge Graph Specialist extracting structured medical triples from text. "
    "Only extract facts explicitly stated in the text. Do not add outside knowledge. Reply with valid JSON only."
)

PROMPT_TEMPLATE = """\
Extract factual triples from the TEXT.

SUGGESTED ENTITY KINDS:
{kinds}

SUGGESTED RELATIONS:
{relations}

Return a JSON array of objects. Each object must have:
  "source":      entity name, verbatim or normalized from text
  "source_kind": entity category (e.g. Disease, Symptom, Treatment, BodyPart)
  "relation":    relationship type (e.g. treated_by, metastasizes_to, located_in)
  "target":      entity name, verbatim or normalized from text
  "target_kind": entity category

Rules:
- Only emit triples explicitly stated in the TEXT.
- The suggested kinds and relations above are guidance. You may emit other relations if stated in the text.
- Do NOT return an empty list if factual statements exist in the text.

TEXT:
{text}

JSON:"""

GLEANING_PROMPT_TEMPLATE = """\
Review the TEXT below and your PREVIOUS EXTRACTIONS.
Extract any ADDITIONAL factual triples that were missed in the previous pass.

TEXT:
{text}

PREVIOUS EXTRACTIONS:
{previous_json}

Return a JSON array of NEW, ADDITIONAL triples only. If no additional facts remain, return [].
JSON:"""


def token_chunk_text(text: str, model_name: str = "gpt-4o-mini",
                     chunk_size: int = 1200, overlap: int = 100) -> list[dict[str, Any]]:
    """Chunk text into 1200-token windows with overlap using tiktoken."""
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")

    tokens = enc.encode(text)
    step = chunk_size - overlap
    chunks: list[dict[str, Any]] = []

    idx = 0
    while idx < len(tokens):
        chunk_tokens = tokens[idx : idx + chunk_size]
        chunk_text_str = enc.decode(chunk_tokens)
        chunks.append({
            "chunk_id": f"chunk_{len(chunks):04d}",
            "token_count": len(chunk_tokens),
            "text": chunk_text_str
        })
        idx += step
        if idx >= len(tokens) and len(chunks) > 0:
            break

    return chunks


def parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    a, b = text.find("["), text.rfind("]")
    if a == -1 or b == -1 or b < a:
        return []
    try:
        parsed = json.loads(text[a:b + 1])
    except json.JSONDecodeError:
        return []
    return [p for p in parsed if isinstance(p, dict)]


def norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def main() -> int:
    ap = argparse.ArgumentParser(description="Build property graph per docs/GATE1_SPEC.md")
    ap.add_argument("--corpus", default="data/graphrag_bench/medical_corpus.json")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--chunk-size", type=int, default=1200, help="Token chunk size (default: 1200)")
    ap.add_argument("--chunk-overlap", type=int, default=100, help="Token chunk overlap (default: 100)")
    ap.add_argument("--enable-gleaning", action="store_true", default=True, help="Enable 1 extra gleaning pass")
    ap.add_argument("--limit-chunks", type=int, default=None, help="Process first N chunks only")
    ap.add_argument("--out-dir", default="data/graphrag_bench/graph_out", help="Output directory")
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key and "openai" in args.base_url.lower():
        print("OPENAI_API_KEY is not set. Refusing to run.", file=sys.stderr)
        return 2

    from openai import OpenAI
    client = OpenAI(api_key=key or "ollama", base_url=args.base_url)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        print(f"Corpus file not found: {args.corpus}", file=sys.stderr)
        return 1

    corpus_raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    if isinstance(corpus_raw, dict):
        text = corpus_raw.get("context") or corpus_raw.get("text") or str(corpus_raw)
    elif isinstance(corpus_raw, list):
        text = "\n\n".join([doc.get("text") or doc.get("context") or str(doc) for doc in corpus_raw])
    else:
        text = str(corpus_raw)

    chunks = token_chunk_text(text, model_name=args.model, chunk_size=args.chunk_size, overlap=args.chunk_overlap)
    if args.limit_chunks:
        chunks = chunks[: args.limit_chunks]

    print(f"GATE 1 GRAPH BUILD: {len(text)} chars -> {len(chunks)} chunks ({args.chunk_size} tokens each)", flush=True)

    suggested_kinds_str = ", ".join(SUGGESTED_KINDS)
    suggested_rels_str = ", ".join(SUGGESTED_RELATIONS)

    # Accumulators
    nodes_map: dict[str, dict[str, Any]] = {}  # norm_name -> {name, kind, count}
    edges_list: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    relation_counts: defaultdict[str, int] = defaultdict(int)

    in_tok = out_tok = 0
    started = time.perf_counter()

    for i, ch in enumerate(chunks):
        chunk_id = ch["chunk_id"]
        ch_text = ch["text"]

        if i % 5 == 0 or i == len(chunks) - 1:
            print(f"  Processing chunk {i+1}/{len(chunks)} [{chunk_id}] (nodes={len(nodes_map)}, edges={len(edges_list)})...", flush=True)

        # Pass 1: Extraction
        try:
            resp1 = client.chat.completions.create(
                model=args.model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": PROMPT_TEMPLATE.format(
                        kinds=suggested_kinds_str, relations=suggested_rels_str, text=ch_text
                    )}
                ]
            )
            if resp1.usage:
                in_tok += resp1.usage.prompt_tokens
                out_tok += resp1.usage.completion_tokens
            extracted_1 = parse_json_array(resp1.choices[0].message.content or "")
        except Exception as e:
            print(f"  chunk {chunk_id} pass 1 failed: {e}", file=sys.stderr)
            extracted_1 = []

        # Pass 2: Gleaning (if enabled)
        extracted_2 = []
        if args.enable_gleaning and extracted_1:
            try:
                resp2 = client.chat.completions.create(
                    model=args.model,
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": GLEANING_PROMPT_TEMPLATE.format(
                            text=ch_text, previous_json=json.dumps(extracted_1, indent=2)
                        )}
                    ]
                )
                if resp2.usage:
                    in_tok += resp2.usage.prompt_tokens
                    out_tok += resp2.usage.completion_tokens
                extracted_2 = parse_json_array(resp2.choices[0].message.content or "")
            except Exception as e:
                print(f"  chunk {chunk_id} gleaning pass failed: {e}", file=sys.stderr)

        combined_extracted = extracted_1 + extracted_2

        for row in combined_extracted:
            s, sk = row.get("source"), row.get("source_kind")
            t, tk = row.get("target"), row.get("target_kind")
            r = row.get("relation")

            if not all(isinstance(x, str) and x.strip() for x in (s, sk, t, tk, r)):
                continue

            ns, nt = norm_name(s), norm_name(t)
            rel_name = normalize_relation(r)

            # Record nodes
            if ns not in nodes_map:
                nodes_map[ns] = {"name": s.strip(), "kind": sk.strip(), "count": 1}
            else:
                nodes_map[ns]["count"] += 1

            if nt not in nodes_map:
                nodes_map[nt] = {"name": t.strip(), "kind": tk.strip(), "count": 1}
            else:
                nodes_map[nt]["count"] += 1

            # Record edge with provenance
            edge_key = (ns, rel_name, nt)
            relation_counts[rel_name] += 1

            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges_list.append({
                    "source": ns,
                    "relation": rel_name,
                    "target": nt,
                    "source_kind": sk.strip(),
                    "target_kind": tk.strip(),
                    "source_chunk_id": chunk_id
                })

    # Construct final graph JSON & NetworkX GraphML
    nx_graph = nx.DiGraph()
    json_nodes = []

    for n_id, n_info in sorted(nodes_map.items()):
        json_nodes.append({
            "id": n_id,
            "name": n_info["name"],
            "kind": n_info["kind"],
            "count": n_info["count"]
        })
        nx_graph.add_node(n_id, label=n_info["name"], kind=n_info["kind"])

    json_edges = []
    for e in edges_list:
        json_edges.append(e)
        nx_graph.add_edge(e["source"], e["target"], relation=e["relation"], source_chunk_id=e["source_chunk_id"])

    wall_clock = round(time.perf_counter() - started, 1)

    # 1. Save graph.json
    graph_json_path = out_dir / "graph.json"
    graph_json_data = {
        "nodes": json_nodes,
        "edges": json_edges,
        "num_nodes": len(json_nodes),
        "num_edges": len(json_edges)
    }
    graph_json_path.write_text(json.dumps(graph_json_data, indent=2), encoding="utf-8")

    # 2. Save graph.graphml (for indexing_eval.py)
    graphml_path = out_dir / "graph.graphml"
    nx.write_graphml(nx_graph, graphml_path)

    # 3. Save manifest.json
    prompt_hash = hashlib.sha256((SYSTEM_PROMPT + PROMPT_TEMPLATE).encode("utf-8")).hexdigest()[:16]
    est_cost = (in_tok / 1e6 * 0.15) + (out_tok / 1e6 * 0.60)  # gpt-4o-mini rate estimate

    manifest_data = {
        "spec": "docs/GATE1_SPEC.md",
        "corpus": str(args.corpus),
        "model": args.model,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "tokenizer": "tiktoken (cl100k_base / o200k_base)",
        "prompt_hash": prompt_hash,
        "gleaning_enabled": args.enable_gleaning,
        "num_chunks_processed": len(chunks),
        "num_nodes": len(json_nodes),
        "num_edges": len(json_edges),
        "relation_distribution": dict(sorted(relation_counts.items(), key=lambda x: x[1], reverse=True)),
        "usage": {"prompt_tokens": in_tok, "completion_tokens": out_tok},
        "est_cost_usd": round(est_cost, 4),
        "wall_clock_s": wall_clock,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("GATE 1 GRAPH BUILD COMPLETE")
    print(f"  chunks processed : {len(chunks)}")
    print(f"  nodes created    : {len(json_nodes)}")
    print(f"  edges created    : {len(json_edges)}")
    print(f"  unique relations : {len(relation_counts)}")
    print(f"  tokens           : in={in_tok}  out={out_tok}")
    print(f"  est. cost        : ${est_cost:.4f}")
    print(f"  wall clock       : {wall_clock}s")
    print(f"  wrote graph.json : {graph_json_path}")
    print(f"  wrote graphml    : {graphml_path}")
    print(f"  wrote manifest   : {manifest_path}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
