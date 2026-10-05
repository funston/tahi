#!/usr/bin/env python3
"""
Build an LLM-extracted knowledge graph over the EnterpriseRAG gold documents.

Per TAHI_PLAN.md §2 (Step 1 — Oracle ceiling test), the oracle comparison serves the
SAME source documents in two representations:

  oracle_vector : the gold documents' text
  oracle_graph  : the triples extracted from those same documents

For that to work, every edge must carry the document it came from. The existing
scripts/build_corpus_graph.py concatenates the corpus into one string before chunking,
which destroys the document boundary. This builder therefore chunks PER DOCUMENT so that
chunk_id encodes the source dsid, and every edge records source_doc_id.

Extraction contract (prompt shape, gleaning, "guidance not filter") is kept identical to
scripts/build_corpus_graph.py so the two graphs are comparable. The domain wording and the
suggested kinds/relations differ because the corpus is not medical; both are recorded in
the manifest as author-chosen knobs (GATE1_SPEC.md Rule 2).

TAHI_PLAN.md §0 rules observed:
  - nothing is silently dropped: parse failures and empty extractions are counted and
    written to the manifest
  - no hard-coded expected values anywhere
  - every reported number is regenerable from this script plus committed inputs
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import networkx as nx
import tiktoken

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# The six structure-sensitive categories that form the pre-registered primary pool.
# Source: benchmarks/PREREGISTRATION_enterprise_rag.md ("Primary metric", n=170).
STRUCTURAL_TYPES = {
    "project_related",
    "constrained",
    "conflicting_info",
    "completeness",
    "intra_document_reasoning",
    "info_not_found",
}

# Author-chosen (Claude), recorded in manifest. Guidance only — never a filter.
# Deliberately generic: the failure this project already suffered was a hand-typed
# schema that silently rejected the corpus's most frequent relation.
SUGGESTED_KINDS = [
    "Person", "Team", "Customer", "Organization", "Product", "Service",
    "Feature", "Ticket", "Incident", "Project", "Document", "Policy",
    "Metric", "System", "Component", "Environment", "Release", "Date",
]
SUGGESTED_RELATIONS = [
    "reported_by", "assigned_to", "belongs_to", "depends_on", "affects",
    "resolves", "caused_by", "mentions", "owns", "part_of", "blocked_by",
    "requested_by", "deployed_to", "related_to", "has_status", "occurred_on",
]

SYSTEM_PROMPT = (
    "You are a Knowledge Graph Specialist extracting structured triples from enterprise "
    "documents (support threads, tickets, CRM records, docs, email). "
    "Only extract facts explicitly stated in the text. Do not add outside knowledge. "
    "Reply with valid JSON only."
)

PROMPT_TEMPLATE = """\
Extract factual triples from the TEXT.

SUGGESTED ENTITY KINDS:
{kinds}

SUGGESTED RELATIONS:
{relations}

Return a JSON array of objects. Each object must have:
  "source":      entity name, verbatim or normalized from text
  "source_kind": entity category (e.g. Person, Customer, Ticket, System)
  "relation":    relationship type (e.g. reported_by, affects, depends_on)
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


def norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def normalize_relation(rel_str: str) -> str:
    return rel_str.strip().lower().replace(" ", "_")


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


def token_chunk_doc(text: str, doc_id: str, model_name: str,
                    chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    """Chunk ONE document. chunk_id encodes the source doc so provenance survives."""
    try:
        enc = tiktoken.encoding_for_model(model_name)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    step = max(1, chunk_size - overlap)
    chunks: list[dict[str, Any]] = []
    idx = 0
    while idx < len(tokens):
        ct = tokens[idx: idx + chunk_size]
        chunks.append({
            "chunk_id": f"{doc_id}#{len(chunks):02d}",
            "doc_id": doc_id,
            "token_count": len(ct),
            "text": enc.decode(ct),
        })
        idx += step
    return chunks


def index_source_files(sources_dir: Path) -> dict[str, Path]:
    """Map dsid -> path. Files are named dsid_<hash>__<slug>.txt under nested dirs."""
    idx: dict[str, Path] = {}
    for root, _dirs, files in os.walk(sources_dir):
        for b in files:
            if b.startswith("dsid_"):
                idx.setdefault(b.split("__")[0], Path(root) / b)
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description="Build enterprise graph over gold docs (TAHI_PLAN.md §2)")
    ap.add_argument("--questions", default="data/enterprise_rag/questions.jsonl")
    ap.add_argument("--sources", default="data/enterprise_rag/sources")
    ap.add_argument("--out-dir", default="data/enterprise_rag/graph_gold")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--chunk-size", type=int, default=1200)
    ap.add_argument("--chunk-overlap", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--limit-docs", type=int, default=None, help="Process first N gold docs only")
    ap.add_argument("--no-gleaning", action="store_true")
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key and "openai" in args.base_url.lower():
        print("OPENAI_API_KEY is not set. Refusing to run.", file=sys.stderr)
        return 2

    from openai import OpenAI
    client = OpenAI(api_key=key or "ollama", base_url=args.base_url,
                    timeout=args.timeout, max_retries=args.max_retries)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- select gold documents of the structural pool -------------------------------
    questions = [json.loads(ln) for ln in Path(args.questions).read_text().splitlines() if ln.strip()]
    pool = [q for q in questions if q.get("question_type") in STRUCTURAL_TYPES]
    wanted: set[str] = set()
    for q in pool:
        wanted.update(q.get("expected_doc_ids") or [])

    file_index = index_source_files(Path(args.sources))
    located = {d: file_index[d] for d in sorted(wanted) if d in file_index}
    missing = sorted(wanted - set(located))
    if args.limit_docs:
        located = dict(list(located.items())[: args.limit_docs])

    print(f"structural pool questions : {len(pool)}", flush=True)
    print(f"gold docs referenced      : {len(wanted)}", flush=True)
    print(f"gold docs located on disk : {len(located)} (missing {len(missing)})", flush=True)

    # ---- chunk per document ---------------------------------------------------------
    chunks: list[dict[str, Any]] = []
    for doc_id, path in located.items():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"  UNREADABLE {doc_id}: {e}", file=sys.stderr)
            continue
        chunks.extend(token_chunk_doc(text, doc_id, args.model,
                                      args.chunk_size, args.chunk_overlap))
    print(f"chunks to extract         : {len(chunks)}", flush=True)

    kinds_str = ", ".join(SUGGESTED_KINDS)
    rels_str = ", ".join(SUGGESTED_RELATIONS)
    prompt_hash = hashlib.sha256(
        (SYSTEM_PROMPT + PROMPT_TEMPLATE + GLEANING_PROMPT_TEMPLATE + kinds_str + rels_str)
        .encode()
    ).hexdigest()[:16]

    lock = threading.Lock()
    counters = {"in_tok": 0, "out_tok": 0, "done": 0,
                "parse_fail": 0, "empty_extraction": 0, "api_error": 0,
                "gleaning_added": 0}

    def extract(chunk: dict[str, Any]) -> tuple[dict[str, Any], list[dict]]:
        """One chunk -> list of raw triple dicts. Never raises; failures are counted."""
        triples: list[dict] = []
        try:
            r = client.chat.completions.create(
                model=args.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": PROMPT_TEMPLATE.format(
                              kinds=kinds_str, relations=rels_str, text=chunk["text"])}],
                temperature=0,
            )
            content = r.choices[0].message.content or ""
            with lock:
                counters["in_tok"] += r.usage.prompt_tokens
                counters["out_tok"] += r.usage.completion_tokens
            first = parse_json_array(content)
            if not first and content.strip():
                with lock:
                    counters["parse_fail"] += 1
            triples.extend(first)

            if not args.no_gleaning:
                g = client.chat.completions.create(
                    model=args.model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT},
                              {"role": "user", "content": GLEANING_PROMPT_TEMPLATE.format(
                                  text=chunk["text"],
                                  previous_json=json.dumps(first)[:6000])}],
                    temperature=0,
                )
                gc = g.choices[0].message.content or ""
                with lock:
                    counters["in_tok"] += g.usage.prompt_tokens
                    counters["out_tok"] += g.usage.completion_tokens
                extra = parse_json_array(gc)
                triples.extend(extra)
                with lock:
                    counters["gleaning_added"] += len(extra)

            if not triples:
                with lock:
                    counters["empty_extraction"] += 1
        except Exception as e:  # noqa: BLE001 - counted, reported, never silent
            with lock:
                counters["api_error"] += 1
            print(f"  API ERROR {chunk['chunk_id']}: {type(e).__name__}: {e}",
                  file=sys.stderr, flush=True)
        return chunk, triples

    nodes_map: dict[str, dict[str, Any]] = {}
    edges_list: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, str]] = set()
    relation_counts: defaultdict[str, int] = defaultdict(int)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(extract, c) for c in chunks]
        for fut in as_completed(futures):
            chunk, triples = fut.result()
            for t in triples:
                s, rel, tgt = t.get("source"), t.get("relation"), t.get("target")
                if not (isinstance(s, str) and isinstance(rel, str) and isinstance(tgt, str)):
                    continue
                if not (s.strip() and rel.strip() and tgt.strip()):
                    continue
                sn, tn = norm_name(s), norm_name(tgt)
                rn = normalize_relation(rel)
                for nm, raw, kind in ((sn, s, t.get("source_kind")), (tn, tgt, t.get("target_kind"))):
                    if nm not in nodes_map:
                        nodes_map[nm] = {"id": nm, "name": raw.strip(),
                                         "kind": kind or "Unknown", "count": 0}
                    nodes_map[nm]["count"] += 1
                sig = (sn, rn, tn, chunk["doc_id"])
                if sig in seen_edges:
                    continue
                seen_edges.add(sig)
                edges_list.append({
                    "source": sn, "relation": rn, "target": tn,
                    "source_kind": t.get("source_kind") or "Unknown",
                    "target_kind": t.get("target_kind") or "Unknown",
                    "source_chunk_id": chunk["chunk_id"],
                    "source_doc_id": chunk["doc_id"],
                })
                relation_counts[rn] += 1
            with lock:
                counters["done"] += 1
                d = counters["done"]
            if d % 25 == 0 or d == len(chunks):
                print(f"  {d}/{len(chunks)} chunks | nodes={len(nodes_map)} "
                      f"edges={len(edges_list)}", flush=True)

    elapsed = time.perf_counter() - started

    # ---- write artifacts ------------------------------------------------------------
    nodes = list(nodes_map.values())
    graph_json = {"nodes": nodes, "edges": edges_list,
                  "num_nodes": len(nodes), "num_edges": len(edges_list)}
    (out_dir / "graph.json").write_text(json.dumps(graph_json, indent=2))

    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], name=n["name"], kind=n["kind"])
    for e in edges_list:
        G.add_edge(e["source"], e["target"], relation=e["relation"],
                   source_doc_id=e["source_doc_id"])
    nx.write_graphml(G, out_dir / "graph.graphml")

    cost = counters["in_tok"] / 1e6 * 0.15 + counters["out_tok"] / 1e6 * 0.60
    manifest = {
        "plan": "TAHI_PLAN.md §2 (Step 1 oracle ceiling test)",
        "purpose": "graph over EnterpriseRAG gold documents of the structural pool",
        "questions_file": args.questions,
        "structural_types": sorted(STRUCTURAL_TYPES),
        "structural_pool_questions": len(pool),
        "gold_docs_referenced": len(wanted),
        "gold_docs_located": len(located),
        "gold_docs_missing": missing,
        "model": args.model,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "chunking": "per-document; chunk_id = <dsid>#<nn> so provenance survives",
        "tokenizer": "tiktoken",
        "prompt_hash": prompt_hash,
        "gleaning_enabled": not args.no_gleaning,
        "concurrency": args.concurrency,
        "timeout_s": args.timeout,
        "max_retries": args.max_retries,
        "suggested_kinds": SUGGESTED_KINDS,
        "suggested_relations": SUGGESTED_RELATIONS,
        "suggested_schema_provenance": (
            "AUTHOR-CHOSEN (Claude). Guidance only, never a filter — any relation the model "
            "emits is kept and counted in relation_distribution. Recorded per GATE1_SPEC.md Rule 2."
        ),
        "relation_canonicalization": "NONE applied at build time",
        "num_chunks": len(chunks),
        "num_nodes": len(nodes),
        "num_edges": len(edges_list),
        "relation_distribution": dict(sorted(relation_counts.items(),
                                             key=lambda x: -x[1])),
        "extraction_failures": {
            "api_error_chunks": counters["api_error"],
            "json_parse_failures": counters["parse_fail"],
            "chunks_yielding_zero_triples": counters["empty_extraction"],
            "note": "counted, not dropped silently (TAHI_PLAN.md §0 rule 5)",
        },
        "gleaning_triples_added": counters["gleaning_added"],
        "usage": {"prompt_tokens": counters["in_tok"],
                  "completion_tokens": counters["out_tok"]},
        "est_cost_usd": round(cost, 4),
        "cost_basis": "gpt-4o-mini $0.15/1M input, $0.60/1M output",
        "wall_clock_s": round(elapsed, 1),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\nnodes={len(nodes)} edges={len(edges_list)} "
          f"relations={len(relation_counts)} cost=${cost:.4f} in {elapsed:.0f}s")
    print(f"api_errors={counters['api_error']} parse_fail={counters['parse_fail']} "
          f"empty={counters['empty_extraction']}")
    print(f"wrote {out_dir}/graph.json, graph.graphml, manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
