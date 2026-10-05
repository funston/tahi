#!/usr/bin/env python
"""
Level 3 native benchmark: in-process GCCA residual injection.

The previous "Level 3" arm instantiated a GCCA block, ran it on `torch.randn`
dummy hidden states, discarded the output, and then sent a text prompt over HTTP
to vLLM. Nothing it computed reached a generated token, so it measured Level 1
with a different prompt template.

This runs the real thing: the model is loaded in-process, `TahiNativeAdapter`
attaches GCCA blocks to intermediate transformer layers via forward hooks, and
generation happens with those hooks live. What GCCA computes goes into the
residual stream or the run is invalid.

Four arms, sharing one model, one corpus, one prompt shape:

    base        no retrieval, no adapter                    (floor)
    rag_prompt  dense top-k pasted into the prompt          (Level 1 baseline)
    l3_alpha0   adapter attached, UNTRAINED (alpha = 0)     (identity control)
    l3_trained  adapter attached with trained weights       (the thesis)

`l3_alpha0` is not filler. `h + tanh(0) * attn == h` exactly, so it MUST equal
`base` token for token. If it does not, the harness is wrong and every other
number in the run is suspect. The run asserts this before reporting anything.

Usage:
    python benchmarks/run_l3_native.py \
        --model Qwen/Qwen2.5-1.5B-Instruct \
        --checkpoint checkpoints/gcca/gcca_epoch2.pt \
        --questions data/enterprise_rag/questions.jsonl \
        --corpus data/enterprise_rag/sources \
        --limit 200
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from implementations.enterprise_rag import (  # noqa: E402
    STRUCTURE_SENSITIVE,
    iter_documents,
    load_questions,
    summarize,
)
from implementations.enterprise_rag.world_model import (  # noqa: E402
    build_world_model,
    graph_health,
)
from tahi.eval.faithfulness import score_faithfulness  # noqa: E402
from tahi.eval.manifest import RunManifest, sha256_of_obj, write_artifact  # noqa: E402
from tahi.eval.metrics import exact_match, supporting_fact_recall, token_f1  # noqa: E402
from tahi.eval.report import write_report  # noqa: E402
from tahi.eval.stats import bootstrap_paired_delta  # noqa: E402
from tahi.graph.gnn_encoder import SubgraphRGATEncoder  # noqa: E402
from tahi.native.huggingface_adapter import TahiNativeAdapter  # noqa: E402
from tahi.native.memory import build_memory_tensor, memory_is_informative  # noqa: E402
from tahi.runtime import TahiRuntime  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tahi.l3")

ABSTAIN = "I don't know"
SYSTEM = ("Answer using only the provided context. If the context does not "
          f'contain the answer, reply exactly "{ABSTAIN}". Be concise.')


@dataclass
class Item:
    question_id: str
    category: str
    answer: str
    retrieved_ids: list[str]
    exact_match: float
    token_f1: float
    fact_coverage: float
    groundedness: float
    unsupported_rate: float
    doc_recall: float
    correct_abstention: float
    output_tokens: int


@dataclass
class Arm:
    name: str
    items: list[Item] = field(default_factory=list)

    def _mean(self, a: str) -> float:
        v = [getattr(i, a) for i in self.items if getattr(i, a) is not None]
        return sum(v) / len(v) if v else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name, "n": len(self.items),
            "exact_match": self._mean("exact_match"),
            "token_f1": self._mean("token_f1"),
            "fact_coverage": self._mean("fact_coverage"),
            "groundedness": self._mean("groundedness"),
            "unsupported_rate": self._mean("unsupported_rate"),
            "supporting_fact_recall": self._mean("doc_recall"),
            "abstention_accuracy": self._mean("correct_abstention"),
            "output_tokens": self._mean("output_tokens"),
            "ttft_ms": None, "cost_per_correct_usd": None,
        }

    def scores(self, metric: str) -> list[float]:
        return [getattr(i, metric) for i in self.items]


def build_prompt(tok, question: str, context: str) -> str:
    user = (f"CONTEXT:\n{context}\n\nQUESTION: {question}\nANSWER:"
            if context else f"QUESTION: {question}\nANSWER:")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    try:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    except Exception:
        return f"{SYSTEM}\n\n{user}"


@torch.no_grad()
def generate(model, tok, prompt: str, memory: torch.Tensor | None,
             adapter: TahiNativeAdapter | None, max_new_tokens: int,
             device: str) -> tuple[str, int]:
    """Greedy decode. When `adapter` is given, hooks are live for this call."""
    enc = tok(prompt, return_tensors="pt", truncation=True, max_length=3072).to(device)
    if adapter is not None:
        if memory is not None:
            adapter.set_retrieved_memory(memory.to(device))
        else:
            adapter.clear_retrieved_memory()
    try:
        out = model.generate(
            **enc, max_new_tokens=max_new_tokens, do_sample=False,
            pad_token_id=tok.pad_token_id or tok.eos_token_id,
        )
    finally:
        if adapter is not None:
            adapter.clear_retrieved_memory()
    new = out[0, enc["input_ids"].shape[1]:]
    return tok.decode(new, skip_special_tokens=True).strip(), int(new.shape[0])


def score(q, answer: str, retrieved: list[str], evidence: str, n_tok: int) -> Item:
    abstained = ABSTAIN.lower() in answer.lower()
    if q.is_unanswerable:
        ca = 1.0 if abstained else 0.0
        em = f1 = ca
    else:
        ca = 0.0 if abstained else 1.0
        em = exact_match(answer, q.gold_answer)
        f1 = token_f1(answer, q.gold_answer)
    fa = score_faithfulness(answer, evidence, q.atomic_facts)
    return Item(
        question_id=q.id, category=q.category, answer=answer,
        retrieved_ids=retrieved, exact_match=em, token_f1=f1,
        fact_coverage=fa.fact_coverage, groundedness=fa.groundedness,
        unsupported_rate=fa.unsupported_rate,
        doc_recall=supporting_fact_recall(retrieved, q.gold_document_ids),
        correct_abstention=ca, output_tokens=n_tok,
    )


def pack(pieces: list[tuple[str, str]], doc_chars: int, total_chars: int) -> str:
    out, used = [], 0
    for did, text in pieces:
        block = f"[{did}] {(text or '')[:doc_chars].strip()}"
        if used + len(block) > total_chars:
            break
        out.append(block)
        used += len(block)
    return "\n\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--checkpoint", default=None,
                    help="Trained GCCA weights. Without it, only the alpha=0 "
                         "identity control can run.")
    ap.add_argument("--questions", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--max-docs", type=int, default=None)
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--max-slots", type=int, default=16)
    ap.add_argument("--max-new-tokens", type=int, default=35,
                    help="Length-matched decoding token cap")
    ap.add_argument("--doc-chars", type=int, default=1200)
    ap.add_argument("--context-chars", type=int, default=8000)
    ap.add_argument("--interleave-step", type=int, default=4)
    ap.add_argument("--memory-store", default=None,
                    help="Precomputed memory_vectors.npz written by "
                         "build_gcca_training_data.py. When set, L3 memory comes "
                         "from this file -- the SAME bytes training consumed -- "
                         "instead of being re-derived here. Required for Gate A.")
    ap.add_argument("--question-ids-from", default=None,
                    help="JSONL (e.g. data/gcca_oracle/test.jsonl) whose "
                         "question_id values restrict evaluation to the held-out "
                         "split. Prevents scoring on trained items.")
    ap.add_argument("--gnn", choices=("on", "off"), default="off",
                    help="Graph encoder in the memory path. Default off: the RGAT "
                         "is untrained and has no training script, so 'on' injects "
                         "a random projection and voids the comparison.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--output", default="benchmarks/results/l3_native.json")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    started = time.perf_counter()

    from transformers import AutoModelForCausalLM, AutoTokenizer

    log.info("Loading %s in-process on %s", args.model, args.device)
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float32).to(args.device).eval()

    questions = load_questions(args.questions)

    # Restrict to a held-out split before sampling, so `--limit` cannot silently
    # pull in trained items.
    if args.question_ids_from:
        keep = set()
        with open(args.question_ids_from, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    keep.add(json.loads(line)["question_id"])
        before = len(questions)
        questions = [q for q in questions if q.id in keep]
        log.info("Restricted to %d held-out ids from %s (was %d)",
                 len(questions), args.question_ids_from, before)
        if not questions:
            log.error("No questions survived the held-out id filter.")
            return 1

    if args.limit and args.limit < len(questions):
        import random
        from collections import defaultdict
        buckets = defaultdict(list)
        for q in questions:
            buckets[q.category].append(q)
        rng = random.Random(args.seed)
        share = args.limit / len(questions)
        picked = []
        for c in sorted(buckets):
            items = sorted(buckets[c], key=lambda x: x.id)
            rng.shuffle(items)
            picked.extend(items[: max(1, round(len(items) * share))])
        questions = sorted(picked, key=lambda x: x.id)[: args.limit]
    stats_q = summarize(questions)
    log.info("%d questions; structure-sensitive pool n=%d",
             len(questions), stats_q["structure_sensitive_n"])

    docs = []
    for d in iter_documents(args.corpus):
        docs.append(d)
        if args.max_docs and len(docs) >= args.max_docs:
            log.warning("Corpus CAPPED at %d -- recall not comparable to full runs.",
                        args.max_docs)
            break
    log.info("Loaded %d documents", len(docs))

    wm, gstats = build_world_model(docs)
    for w in graph_health(gstats):
        log.warning(w)
    runtime = TahiRuntime(world_model=wm, top_k=args.top_k)

    d_ret = wm._encoder.dimension  # noqa: SLF001
    adapter = TahiNativeAdapter(base_model=model, d_retriever=d_ret,
                                interleave_step=args.interleave_step).to(args.device)
    log.info("Attached %d GCCA blocks (d_retriever=%d)",
             len(adapter.gcca_layers), d_ret)

    trained_ok = False
    ck_store_sha = None
    alphas: list[float] = []
    if args.checkpoint:
        ck = torch.load(args.checkpoint, map_location=args.device)
        adapter.gcca_layers.load_state_dict(ck["gcca_state_dict"])
        ck_store_sha = ck.get("memory_store_sha256")
        alphas = [float(torch.tanh(g.alpha)) for g in adapter.gcca_layers.values()]
        log.info("Loaded checkpoint; tanh(alpha) = %s", [round(a, 5) for a in alphas])
        log.info("Checkpoint memory store sha: %s", ck_store_sha or "NOT RECORDED")
        if max(abs(a) for a in alphas) < 1e-4:
            log.error("Checkpoint has alpha == 0: the adapter is still an identity "
                      "function. Level 3 cannot be measured with these weights.")
        else:
            trained_ok = True
    else:
        log.warning("No --checkpoint: only the alpha=0 identity control will run.")

    arms = {n: Arm(n) for n in ("base", "rag_prompt", "l3_alpha0", "l3_trained")}
    degenerate_memory = 0

    # The RGAT has no training script and no validated checkpoint. Running it
    # with random weights projects every memory slot through noise the adapter
    # never saw in training -- which is precisely what voided the 2026-08-03
    # run. It is therefore opt-in, and the manifest records the choice.
    gnn_encoder = None
    if args.gnn == "on":
        log.warning("--gnn on: SubgraphRGATEncoder is UNTRAINED (no checkpoint "
                    "loader exists). Memory will be a random projection and the "
                    "L3 comparison will not be interpretable.")
        gnn_encoder = SubgraphRGATEncoder(d_in=d_ret, d_hidden=d_ret, d_out=d_ret,
                                          num_relations=16).to(args.device)

    store = None
    if args.memory_store:
        from tahi.native.memory_store import load_memory_store
        store = load_memory_store(args.memory_store)
        if store.d_model != d_ret:
            log.error("Memory store is d=%d but the world model encoder is d=%d.",
                      store.d_model, d_ret)
            return 1
        if args.gnn == "on":
            log.error("--memory-store with --gnn on is contradictory: the store "
                      "holds the exact vectors training used, and the GNN would "
                      "transform them into something it never saw.")
            return 1
        missing = [q.id for q in questions if q.id not in store]
        if missing:
            log.error("%d evaluated questions are absent from the memory store "
                      "(first: %s). Their L3 memory would be built by a different "
                      "path than training used.", len(missing), missing[0])
            return 1
        log.info("Memory from store %s: %d questions, d=%d, source=%s, sha=%s",
                 args.memory_store, len(store), store.d_model,
                 store.meta.get("memory_source"), store.sha256[:16])
        if ck_store_sha and ck_store_sha != store.sha256:
            log.error("Checkpoint was trained on memory store %s but this run uses "
                      "%s. The comparison would be void.",
                      ck_store_sha[:16], store.sha256[:16])
            return 1

    for i, q in enumerate(questions):
        if i % 25 == 0:
            log.info("item %d/%d", i, len(questions))

        state = runtime.infer(query=q.text)
        doc_ids = [r.node_id.split("doc::", 1)[-1] for r in state.retrievals
                   if r.node_id.startswith("doc::")]
        evidence = pack(
            [(r.node_id, wm.nodes.get(r.node_id, {}).get("text", ""))
             for r in state.retrievals], args.doc_chars, args.context_chars)
        if store is not None:
            # The exact bytes training consumed. Not re-derived here.
            memory = store.tensor(q.id, device=args.device)
        else:
            memory = build_memory_tensor(state, wm, max_slots=args.max_slots,
                                         gnn_encoder=gnn_encoder,
                                         device=args.device)
        if memory is not None and not memory_is_informative(memory):
            degenerate_memory += 1

        # base -- no retrieval, hooks inert (memory cleared)
        a, n = generate(model, tok, build_prompt(tok, q.text, ""), None,
                        adapter, args.max_new_tokens, args.device)
        arms["base"].items.append(score(q, a, [], "", n))

        # rag_prompt -- Level 1: evidence in the prompt, hooks inert
        a, n = generate(model, tok, build_prompt(tok, q.text, evidence), None,
                        adapter, args.max_new_tokens, args.device)
        arms["rag_prompt"].items.append(score(q, a, doc_ids, evidence, n))

        # l3_alpha0 -- identity control: memory injected, gate at zero
        with torch.no_grad():
            saved = [g.alpha.detach().clone() for g in adapter.gcca_layers.values()]
            for g in adapter.gcca_layers.values():
                g.alpha.zero_()
        a, n = generate(model, tok, build_prompt(tok, q.text, ""), memory,
                        adapter, args.max_new_tokens, args.device)
        arms["l3_alpha0"].items.append(score(q, a, doc_ids, "", n))
        with torch.no_grad():
            for g, s in zip(adapter.gcca_layers.values(), saved, strict=False):
                g.alpha.copy_(s)

        # l3_trained -- the actual thesis: memory into the residual stream
        if trained_ok:
            a, n = generate(model, tok, build_prompt(tok, q.text, ""), memory,
                            adapter, args.max_new_tokens, args.device)
            arms["l3_trained"].items.append(score(q, a, doc_ids, evidence, n))

    # --- Validity gate -------------------------------------------------------
    # tanh(0) == 0, so the alpha=0 arm must reproduce base exactly. A mismatch
    # means hooks are altering hidden states when they must not, and no other
    # number in this run can be trusted.
    mismatches = sum(
        1 for b, z in zip(arms["base"].items, arms["l3_alpha0"].items, strict=False)
        if b.answer != z.answer
    )
    identity_holds = mismatches == 0
    if identity_holds:
        log.info("IDENTITY CONTROL PASSED: alpha=0 reproduced base on all %d items.",
                 len(arms["base"].items))
    else:
        log.error("IDENTITY CONTROL FAILED: %d/%d items differ from base at alpha=0. "
                  "The harness is wrong -- results are INVALID.",
                  mismatches, len(arms["base"].items))

    live = [a for a in arms.values() if a.items]
    comparisons = []
    idx = [i for i, q in enumerate(questions) if q.category in STRUCTURE_SENSITIVE]
    for a, b in (("base", "rag_prompt"), ("rag_prompt", "l3_trained"),
                 ("base", "l3_trained"), ("base", "l3_alpha0")):
        if not (arms[a].items and arms[b].items):
            continue
        for metric in ("fact_coverage", "token_f1"):
            comparisons.append(bootstrap_paired_delta(
                arms[a].scores(metric), arms[b].scores(metric),
                arm_a=f"{a}[{metric}]", arm_b=f"{b}[{metric}]", seed=args.seed
            ).to_dict())
        if len(idx) >= 30:
            comparisons.append(bootstrap_paired_delta(
                [arms[a].scores("fact_coverage")[i] for i in idx],
                [arms[b].scores("fact_coverage")[i] for i in idx],
                arm_a=f"{a}[fact_coverage|structural]",
                arm_b=f"{b}[fact_coverage|structural]", seed=args.seed
            ).to_dict())

    manifest = RunManifest(
        benchmark="EnterpriseRAG-Bench Level 3 (in-process GCCA)",
        dataset=str(args.questions),
        dataset_sha256=sha256_of_obj([q.id for q in questions]),
        n_items=len(questions), seed=args.seed,
        provider="in-process-pytorch", model=args.model,
        encoder=f"sentence-transformers (d={d_ret})",
        encoder_is_fallback=False, strict_mode=True,
        wall_clock_s=time.perf_counter() - started,
        llm_usage={"total_calls": len(questions) * len(live), "est_cost_usd": 0.0,
                   "fallback_calls": 0},
        notes=(
            f"IDENTITY CONTROL: {'PASSED' if identity_holds else 'FAILED'} "
            f"({mismatches} mismatches). GCCA blocks: {len(adapter.gcca_layers)}, "
            f"interleave_step={args.interleave_step}, max_slots={args.max_slots}. "
            f"Trained checkpoint: {args.checkpoint or 'NONE'}. "
            f"max|tanh(alpha)|={max((abs(a) for a in alphas), default=0.0):.4f}. "
            f"Memory: source={store.meta.get('memory_source') if store else 'live-retrieval'}, "
            f"store={args.memory_store or 'NONE'}, "
            f"store_sha={store.sha256[:16] if store else 'n/a'}, "
            f"gnn={args.gnn}. "
            f"Degenerate (non-informative) memory on {degenerate_memory} items. "
            f"Corpus: {len(docs)} docs, "
            f"{sum(v for k, v in gstats.items() if k.startswith('edge::'))} edges."
        ),
    )

    out = write_artifact(args.output, manifest, {
        "arms": [a.summary() for a in live],
        "comparisons": comparisons,
        "identity_control_passed": identity_holds,
        "identity_mismatches": mismatches,
        "question_stats": stats_q,
        "graph_stats": gstats,
        "per_item": [{"arm": a.name, **vars(i)} for a in live for i in a.items],
    })
    log.info("Wrote %s and %s", out, write_report(out))

    print()
    if not identity_holds:
        print("  *** RESULTS INVALID: alpha=0 did not reproduce base. ***")
    for c in comparisons:
        print("  " + c["verdict"])
    return 0 if identity_holds else 1


if __name__ == "__main__":
    sys.exit(main())
