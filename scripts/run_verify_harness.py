#!/usr/bin/env python3
"""
A6 `tahi_verify` — the "generate, then check" harness.  TAHI_PLAN.md §6.1.

This is the first harness in the repo that tests TAHI as a VERIFIER rather than as a
retrieval substitute. Every prior run (`tahi_l1` Aug 2, L3 GCCA Aug 4, the GraphRAG-Bench
3-arm, today's oracle) put the graph in the retrieval slot, competing with dense retrieval.
The graph never ran after generation, so `src/tahi/validate/` — which has implemented exactly
this since it landed — was never reachable from any measured path.

Design: generation is held IDENTICAL across arms. Both arms retrieve the same prose and
produce the same answer text. Only the ATTRIBUTION MECHANISM differs:

    A1  vector_rag_cite   an LLM is asked which retrieved chunk supports each claim
    A6  tahi_verify       GraphFactValidator mechanically finds supporting edges,
                          and the edge's source_doc_id is the citation

Holding generation constant means any difference is attributable to the mechanism, not to
answer quality. A1 is a genuine opponent — prompt-RAG can cite the chunk it retrieved — which
is what makes the comparison fair rather than self-serving.

Judging: the judge sees ONLY the claim and the cited chunk text. Never the gold answer, never
the other arm, never which arm produced it.

Metrics (fixed in TAHI_PLAN.md §6.1 before any measurement existed):
    attribution_accuracy = judged-supported citations / total claims
    unattributed_rate    = claims carrying no citation / total claims
A system can trivially maximise accuracy by citing almost nothing, so the second is reported
beside the first and a win on accuracy with a materially worse unattributed_rate is a NULL.

TAHI_PLAN.md §0 observed: no fabricated values, no hard-coded expectations, every number
regenerable, exclusions counted not dropped, nulls reported unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.eval.stats import bootstrap_paired_delta  # noqa: E402
from tahi.validate.claim_extractor import Claim, ClaimExtractor  # noqa: E402
from tahi.validate.fact_validator import GraphFactValidator, Verdict  # noqa: E402

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

STRUCTURAL_TYPES = {
    "project_related", "constrained", "conflicting_info",
    "completeness", "intra_document_reasoning", "info_not_found",
}

ANSWER_PROMPT = """\
Answer the question using only the CONTEXT provided. Be concise and factual.
If the context does not contain the answer, say what is missing.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

CITE_PROMPT = """\
Below is a CLAIM and a list of candidate SOURCE PASSAGES, each with an id.
Which single source passage supports the claim?

Reply with ONLY the id, or the word NONE if no passage supports it.

CLAIM: {claim}

SOURCES:
{sources}

ID:"""

JUDGE_PROMPT = """\
Does the SOURCE below support the CLAIM?

Judge only against the SOURCE text. Do not use outside knowledge.
Reply with exactly one word: SUPPORTED or NOT_SUPPORTED.

SOURCE:
{source}

CLAIM: {claim}

VERDICT:"""


class GraphAdapter:
    """Presents graph.json in the shape GraphFactValidator expects.

    The validator needs `.nodes` as {node_id: attrs} and `.neighbors(id)` yielding
    (src, rel, dst, attrs). This is a format adapter only -- no validation logic here.
    """

    def __init__(self, graph_path: Path):
        g = json.loads(graph_path.read_text())
        self.nodes: dict[str, dict[str, Any]] = {
            n["id"]: {"label": n.get("name", n["id"]), "kind": n.get("kind")}
            for n in g.get("nodes", [])
        }
        self._adj: dict[str, list[tuple[str, str, str, dict]]] = defaultdict(list)
        self.n_edges = 0
        for e in g.get("edges", []):
            s, r, t = e.get("source"), e.get("relation"), e.get("target")
            if not (s and r and t):
                continue
            attrs = {"source_doc_id": e.get("source_doc_id"),
                     "source_chunk_id": e.get("source_chunk_id")}
            self._adj[s].append((s, r, t, attrs))
            self._adj[t].append((t, r, s, attrs))  # undirected for reachability
            self.n_edges += 1

    def neighbors(self, node_id: str):
        return self._adj.get(node_id, [])


def index_source_files(sources_dir: Path) -> dict[str, Path]:
    idx: dict[str, Path] = {}
    for root, _dirs, files in os.walk(sources_dir):
        for b in files:
            if b.startswith("dsid_"):
                idx.setdefault(b.split("__")[0], Path(root) / b)
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description="A6 generate-then-check harness (TAHI_PLAN.md §6.1)")
    ap.add_argument("--questions", default="data/enterprise_rag/questions.jsonl")
    ap.add_argument("--sources", default="data/enterprise_rag/sources")
    ap.add_argument("--graph", default="data/enterprise_rag/graph_gold/graph.json")
    ap.add_argument("--out-dir", default="data/enterprise_rag/verify")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--limit-questions", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-resamples", type=int, default=10000)
    ap.add_argument("--encoder", default="BAAI/bge-large-en-v1.5")
    ap.add_argument("--top-nodes", type=int, default=20)
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key and "openai" in args.base_url.lower():
        print("OPENAI_API_KEY is not set. Refusing to run.", file=sys.stderr)
        return 2
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=args.base_url,
                    timeout=args.timeout, max_retries=args.max_retries)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()
    usage = {"in": 0, "out": 0, "errors": 0}

    def llm(prompt: str, system: str | None = None) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
        try:
            r = client.chat.completions.create(model=args.model, messages=msgs,
                                               temperature=0)
            with lock:
                usage["in"] += r.usage.prompt_tokens
                usage["out"] += r.usage.completion_tokens
            return (r.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001 - counted, never silent
            with lock:
                usage["errors"] += 1
            print(f"  LLM ERROR: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            return ""

    class _Shim:
        """Minimal LLMClient surface for ClaimExtractor (.complete -> .text)."""
        def complete(self, prompt: str, system: str | None = None):
            class R:
                text = llm(prompt, system)
            return R()

    # ---- data ------------------------------------------------------------------
    questions = [json.loads(ln) for ln in Path(args.questions).read_text().splitlines() if ln.strip()]
    pool = [q for q in questions if q.get("question_type") in STRUCTURAL_TYPES]
    file_index = index_source_files(Path(args.sources))

    items, excluded = [], defaultdict(int)
    for q in pool:
        doc_ids = q.get("expected_doc_ids") or []
        if not doc_ids:
            excluded[f"no_gold_docs:{q['question_type']}"] += 1
            continue
        chunks = []
        for d in doc_ids:
            p = file_index.get(d)
            if p is None:
                excluded["gold_doc_missing_on_disk"] += 1
                continue
            chunks.append({"id": d, "text": p.read_text(encoding="utf-8", errors="replace")})
        if not chunks:
            excluded["no_gold_doc_text"] += 1
            continue
        items.append({"id": q["question_id"], "question_type": q["question_type"],
                      "question": q["question"], "gold_answer": q.get("gold_answer", ""),
                      "chunks": chunks})
    if args.limit_questions and len(items) > args.limit_questions:
        import random as _r
        items = _r.Random(args.seed).sample(items, args.limit_questions)

    graph = GraphAdapter(Path(args.graph))
    validator = GraphFactValidator(graph)
    extractor = ClaimExtractor(_Shim(), strict=False)

    print(f"items={len(items)} excluded={dict(excluded)}", flush=True)
    print(f"graph: {len(graph.nodes)} nodes, {graph.n_edges} edges, "
          f"{validator.n_aliases} aliases indexed", flush=True)
    if not items:
        print("No items. BLOCKED per TAHI_PLAN.md §0 rule 7.", file=sys.stderr)
        return 1

    # ---- stage 1: generate ONCE, shared by both arms ---------------------------
    def generate(it: dict) -> tuple[str, str]:
        ctx = "\n\n---\n\n".join(c["text"] for c in it["chunks"])
        return it["id"], llm(ANSWER_PROMPT.format(context=ctx, question=it["question"]))

    answers: dict[str, str] = {}
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for fut in as_completed([ex.submit(generate, it) for it in items]):
            qid, text = fut.result()
            answers[qid] = text
    print(f"  generated {len(answers)} answers", flush=True)

    # ---- stage 2: extract claims (shared -- same claims judged for both arms) ---
    extract_failures = {"n": 0}

    def extract(it: dict) -> tuple[str, list[Claim]]:
        """One malformed LLM reply must not kill a run that already paid for 150
        generations. Counted and surfaced in the manifest, never silently dropped."""
        try:
            return it["id"], extractor.extract(answers.get(it["id"], ""))
        except Exception as e:  # noqa: BLE001
            with lock:
                extract_failures["n"] += 1
            print(f"  CLAIM EXTRACT FAILED {it['id']}: {type(e).__name__}", file=sys.stderr, flush=True)
            return it["id"], []

    claims: dict[str, list[Claim]] = {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        for fut in as_completed([ex.submit(extract, it) for it in items]):
            qid, cl = fut.result()
            claims[qid] = cl
    total_claims = sum(len(v) for v in claims.values())
    print(f"  extracted {total_claims} claims", flush=True)

    # ---- node embedding index (dense-linked arm) --------------------------------
    import numpy as np  # noqa: E402
    from sentence_transformers import SentenceTransformer  # noqa: E402
    print(f"  embedding {len(graph.nodes)} node labels ...", flush=True)
    st_model = SentenceTransformer(args.encoder)
    node_ids = list(graph.nodes)
    node_emb = st_model.encode([graph.nodes[n].get("label") or n for n in node_ids],
                               normalize_embeddings=True, batch_size=256,
                               show_progress_bar=False)

    # ---- stage 3: attribute, per arm -------------------------------------------
    def claim_text(c: Claim) -> str:
        return c.verbatim or f"{c.subject} {c.relation or ''} {c.object}".strip()

    def attribute_a1(it: dict, c: Claim) -> str | None:
        """LLM picks which retrieved chunk supports the claim."""
        src = "\n\n".join(f"[{ch['id']}]\n{ch['text'][:4000]}" for ch in it["chunks"])
        reply = llm(CITE_PROMPT.format(claim=claim_text(c), sources=src))
        for ch in it["chunks"]:
            if ch["id"] in reply:
                return ch["id"]
        return None

    def attribute_a6(it: dict, c: Claim) -> str | None:
        """Graph validator finds a supporting edge; its source_doc_id is the citation.

        The Claim carries subject/relation/object, so the SCOPED validator path is the
        correct one -- `fact_validator.validate` docstring: "subject and relation scope
        the check when the caller knows them (the usual case)". The unscoped path
        requires two exact alias matches in free text and never reaches the multi-hop
        branch, which is why it abstained on ~95% of claims in smoke testing.

        `relation=None` deliberately: the extractor's relation vocabulary is open and
        will not string-match the graph's 3,436 relation names. Scoping by subject and
        letting object resolution do the work is the check that is actually meaningful.
        """
        span = claim_text(c)
        subj_nodes = validator.entities_in(c.subject) or validator.entities_in(span)
        v = None
        for sn in subj_nodes[:3]:
            v = validator.validate(span, subject=sn, relation=None, hops=2)
            if v.verdict is Verdict.SUPPORTED:
                break
        if v is None or v.verdict is not Verdict.SUPPORTED:
            v = validator.validate(span, hops=2)   # unscoped fallback
        if v.verdict is not Verdict.SUPPORTED or not v.supporting_edges:
            return None
        s, r, t = v.supporting_edges[0]
        for _s, _r, dst, attrs in graph.neighbors(s):
            if dst == t:
                return attrs.get("source_doc_id")
        return None

    def judge(claim: str, source_text: str) -> bool:
        reply = llm(JUDGE_PROMPT.format(source=source_text[:12000], claim=claim))
        return reply.strip().upper().startswith("SUPPORTED")

    def score_arm(it: dict, arm: str) -> dict:
        fn = {"vector_rag_cite": attribute_a1,
              "tahi_verify": attribute_a6,
              "tahi_locate": attribute_a6_locate,
              "tahi_dense": attribute_a6_dense}[arm]
        cited = judged_ok = 0
        rows = []
        for c in claims.get(it["id"], []):
            doc_id = fn(it, c)
            ok = False
            if doc_id:
                cited += 1
                src = next((ch["text"] for ch in it["chunks"] if ch["id"] == doc_id), None)
                if src is None:
                    p = file_index.get(doc_id)
                    src = p.read_text(encoding="utf-8", errors="replace") if p else None
                if src:
                    ok = judge(claim_text(c), src)
                    judged_ok += int(ok)
            rows.append({"claim": claim_text(c)[:200], "cited": doc_id, "supported": ok})
        n = len(claims.get(it["id"], []))
        return {"id": it["id"], "question_type": it["question_type"], "arm": arm,
                "n_claims": n, "n_cited": cited, "n_supported": judged_ok,
                "attribution_accuracy": (judged_ok / n) if n else 0.0,
                "unattributed_rate": ((n - cited) / n) if n else 0.0,
                "claims": rows}

    def attribute_a6_locate(it: dict, c: Claim) -> str | None:
        """Graph as LOCATOR, not validator -- the mechanism TAHI_PLAN.md §6.1 specifies:
        "for each claim: locate supporting chunk(s) among those retrieved", then let the
        judge rule. Resolve the claim's entities, take the source_doc_id of the edge that
        touches the most of them, and cite that. Strictly weaker than requiring a
        SUPPORTED verdict, and strictly more faithful to the written protocol.
        """
        span = claim_text(c)
        ents = set(validator.entities_in(span))
        if not ents:
            return None
        best_doc, best_hits = None, 0
        for e in ents:
            for _s, _r, dst, attrs in graph.neighbors(e):
                hits = 1 + (1 if dst in ents else 0)
                if hits > best_hits and attrs.get("source_doc_id"):
                    best_doc, best_hits = attrs["source_doc_id"], hits
        return best_doc

    def attribute_a6_dense(it: dict, c: Claim) -> str | None:
        """Graph locator with BGE-SCORED node resolution.

        `entities_in` returns a SET -- every match weighs the same, so hub nodes win on
        edge count. scripts/probe_graph_query.py measured the cost: doc recall@10 was
        0.5231 lexical vs 0.7540 dense, while recall@all barely moved (0.7829 -> 0.8027).
        The reachable set was always right; only the ranking was missing.
        """
        span = claim_text(c)
        if not span.strip():
            return None
        # BGE is asymmetric -- the query side takes the instruction prefix (see
        # run_graphrag_bench_3arm.py:82). Node labels are the "document" side, unprefixed.
        qp = BGE_QUERY_PREFIX if "bge" in args.encoder.lower() else ""
        qe = st_model.encode([qp + span], normalize_embeddings=True)[0]
        sims = node_emb @ qe
        idx = np.argsort(sims)[::-1][: args.top_nodes]
        # CANDIDATE-SET PARITY (TAHI_PLAN.md §6.1, Task 2.2 in MRAG.md).
        # The 2026-08-05 A6 run let this arm choose from all 403 documents in the graph
        # while vector_rag_cite chose from that question's 2.81 retrieved docs. That is a
        # candidate-set difference, not a mechanism difference, so the resulting -0.3277
        # is uninterpretable. Both arms must cite from the same retrieved set.
        allowed = {ch["id"] for ch in it["chunks"]}
        scores: dict[str, float] = defaultdict(float)
        for i in idx:
            sc = float(sims[i])
            if sc <= 0:
                continue
            for _s, _r, _dst, attrs in graph.neighbors(node_ids[i]):
                d = attrs.get("source_doc_id")
                if d in allowed:
                    scores[d] += sc
        return max(scores.items(), key=lambda x: x[1])[0] if scores else None

    ARMS = ["vector_rag_cite", "tahi_verify", "tahi_locate", "tahi_dense"]
    per_arm: dict[str, dict[str, dict]] = {a: {} for a in ARMS}
    jobs = [(it, a) for it in items for a in ARMS]
    done = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(score_arm, it, a): (it, a) for it, a in jobs}
        for fut in as_completed(futs):
            try:
                row = fut.result()
            except Exception as e:  # noqa: BLE001
                with lock:
                    usage["errors"] += 1
                print(f"  ARM FAILED: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                done += 1
                continue
            per_arm[row["arm"]][row["id"]] = row
            done += 1
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} arm-items attributed", flush=True)
    elapsed = time.perf_counter() - started

    # ---- results ---------------------------------------------------------------
    ids = [it["id"] for it in items if all(it["id"] in per_arm[a] for a in ARMS)]
    means, comparisons = {}, {}
    for metric in ("attribution_accuracy", "unattributed_rate"):
        means[metric] = {a: sum(per_arm[a][i][metric] for i in ids) / len(ids) for a in ARMS}
        base = [per_arm["vector_rag_cite"][i][metric] for i in ids]
        for arm in ARMS[1:]:
            b = [per_arm[arm][i][metric] for i in ids]
            c = bootstrap_paired_delta(base, b, arm_a="vector_rag_cite", arm_b=arm,
                                       n_resamples=args.n_resamples, seed=args.seed)
            comparisons[f"{metric}::{arm}"] = c.to_dict()

    cost = usage["in"] / 1e6 * 0.15 + usage["out"] / 1e6 * 0.60
    result = {
        "plan": "TAHI_PLAN.md §6.1 (A6 generate-then-check)",
        "hypothesis": "H2 — a graph with provenance makes generated claims checkable",
        "design": "generation held identical across arms; only the attribution mechanism differs",
        "graph_file": args.graph, "questions_file": args.questions, "model": args.model,
        "statistic": f"paired bootstrap seed={args.seed}, resamples={args.n_resamples}",
        "n_items": len(ids), "total_claims": total_claims,
        "graph_nodes": len(graph.nodes), "graph_edges": graph.n_edges,
        "validator_aliases": validator.n_aliases,
        "arm_means": means, "comparisons": comparisons,
        "excluded_counts": dict(excluded), "llm_errors": usage["errors"],
        "claim_extract_failures": extract_failures["n"],
        "usage": {"prompt_tokens": usage["in"], "completion_tokens": usage["out"]},
        "est_cost_usd": round(cost, 4), "wall_clock_s": round(elapsed, 1),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "per_question": {a: list(per_arm[a].values()) for a in ARMS},
    }
    (out_dir / "verify_results.json").write_text(json.dumps(result, indent=2))
    (out_dir / "verify_answers.json").write_text(json.dumps(answers, indent=2))

    print(f"\n=== A6 GENERATE-THEN-CHECK (n={len(ids)}, {total_claims} claims) ===")
    for metric in ("attribution_accuracy", "unattributed_rate"):
        print(f"  {metric}:")
        for a in ARMS:
            print(f"      {a:18s} {means[metric][a]:.4f}")
        for arm in ARMS[1:]:
            c = comparisons[f"{metric}::{arm}"]
            flag = "CI EXCLUDES ZERO" if c["ci_excludes_zero"] else "CI includes zero"
            print(f"      {arm} - vector_rag_cite: d={c['delta']:+.4f} "
                  f"CI[{c['ci_low']:+.4f},{c['ci_high']:+.4f}]  {flag}")
    print(f"\n  llm_errors={usage['errors']}  cost=${cost:.4f}  {elapsed:.0f}s")
    print(f"  wrote {out_dir}/verify_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
