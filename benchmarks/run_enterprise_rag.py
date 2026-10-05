"""
EnterpriseRAG-Bench: RAG vs TAHI.

Three arms. The only difference between them is WHICH SYSTEM FINDS THE EVIDENCE.

    Arm 1  base       question only, no retrieval          (floor)
    Arm 2  rag        StandaloneRAG: dense top-k           (the honest baseline)
    Arm 3  tahi_l1    TahiRuntime: vector seed + graph      (the thesis)
                      expansion -> ControlPacket

HARD RULE, asserted at runtime: no arm ever sees `gold_document_ids` or
`gold_answer`. Gold is used only for scoring. The previous harness pasted gold
supporting facts into every arm's context, which made the retrieval question
unanswerable -- every arm was handed the answer and the measured differences
came from prompt formatting.

Usage:
    export TAHI_LLM_PROVIDER=vllm VLLM_BASE_URL=http://localhost:8000/v1
    export TAHI_LLM_MODEL=Qwen/Qwen2.5-72B-Instruct-AWQ TAHI_STRICT=1

    PYTHONPATH=src python benchmarks/run_enterprise_rag.py \
        --questions data/enterprise_rag/questions.jsonl \
        --corpus    data/enterprise_rag/sources \
        --limit 500 --output benchmarks/results/enterprise_rag.json

Smoke test without a corpus download:
    PYTHONPATH=src python benchmarks/run_enterprise_rag.py --self-test
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from implementations.enterprise_rag import (  # noqa: E402
    STRUCTURE_SENSITIVE,
    EnterpriseDocument,
    EnterpriseQuestion,
    iter_documents,
    load_questions,
    summarize,
)
from implementations.enterprise_rag.world_model import (  # noqa: E402
    build_world_model,
    graph_health,
)
from tahi.baseline_rag import RAGDocument, StandaloneRAG  # noqa: E402
from tahi.eval.faithfulness import score_faithfulness  # noqa: E402
from tahi.eval.manifest import RunManifest, sha256_of_obj, write_artifact  # noqa: E402
from tahi.eval.metrics import exact_match, supporting_fact_recall, token_f1  # noqa: E402
from tahi.eval.preflight import require_ready  # noqa: E402
from tahi.eval.report import write_report  # noqa: E402
from tahi.eval.stats import bootstrap_paired_delta  # noqa: E402
from tahi.llm_client import LLMClient  # noqa: E402
from tahi.runtime import TahiRuntime  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tahi.enterprise_rag")

ABSTAIN = "I don't know"
SYSTEM = (
    "Answer using only the provided context. If the context does not contain "
    f'the answer, reply exactly "{ABSTAIN}". Answer concisely -- no preamble.'
)

# Every retrieval arm gets the SAME character budget for evidence. Enterprise
# documents run to many thousands of characters, so an uncapped top-10 overflows
# an 8k context window -- but the cap must be identical across arms or the
# comparison measures prompt engineering instead of retrieval.
#
# This also makes the experiment sharper: at a fixed context budget, which
# system puts better evidence in it?
DEFAULT_CONTEXT_CHARS = 12000
DEFAULT_DOC_CHARS = 1200


def _pack_context(pieces: list[tuple[str, str]], doc_chars: int,
                  total_chars: int) -> str:
    """Render retrieved evidence under a fixed budget, best-ranked first.

    `pieces` is [(doc_id, text)] in rank order. Identical logic for every arm.
    """
    out: list[str] = []
    used = 0
    for doc_id, text in pieces:
        snippet = (text or "")[:doc_chars].strip()
        block = f"[{doc_id}] {snippet}"
        if used + len(block) > total_chars:
            break
        out.append(block)
        used += len(block)
    return "\n\n".join(out)


@dataclass
class ItemResult:
    question_id: str
    category: str
    answer: str
    retrieved_ids: list[str]
    exact_match: float
    token_f1: float
    doc_recall: float
    abstained: bool
    correct_abstention: float | None
    ttft_ms: float | None
    output_tokens: int
    fact_coverage: float = 0.0
    groundedness: float = 0.0
    unsupported_rate: float = 0.0


@dataclass
class ArmResult:
    name: str
    items: list[ItemResult] = field(default_factory=list)

    def _mean(self, attr: str) -> float:
        vals = [getattr(i, attr) for i in self.items if getattr(i, attr) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    def summary(self, cost_usd: float, n_correct: int) -> dict[str, Any]:
        return {
            "name": self.name,
            "n": len(self.items),
            "exact_match": self._mean("exact_match"),
            "token_f1": self._mean("token_f1"),
            "fact_coverage": self._mean("fact_coverage"),
            "groundedness": self._mean("groundedness"),
            "unsupported_rate": self._mean("unsupported_rate"),
            "supporting_fact_recall": self._mean("doc_recall"),
            "abstention_accuracy": self._mean("correct_abstention"),
            "ttft_ms": self._mean("ttft_ms") or None,
            "output_tokens": self._mean("output_tokens"),
            # Phase 4: the commercial question. Requires correctness data,
            # which is why it could not be computed before this runner existed.
            "cost_per_correct_usd": (cost_usd / n_correct) if n_correct else None,
        }

    def f1_scores(self) -> list[float]:
        return [i.token_f1 for i in self.items]

    def coverage_scores(self) -> list[float]:
        return [i.fact_coverage for i in self.items]

    def em_scores(self) -> list[float]:
        return [i.exact_match for i in self.items]


def _assert_no_gold_leak(prompt: str, q: EnterpriseQuestion) -> None:
    """Fail the run if gold ever reaches a prompt. This is the invariant the
    previous harness violated, so it is checked rather than trusted."""
    if q.gold_answer and len(q.gold_answer) > 20 and q.gold_answer in prompt:
        raise AssertionError(
            f"GOLD LEAK on {q.question_id if hasattr(q, 'question_id') else q.id}: "
            "the gold answer appeared in an arm's prompt."
        )
    for doc_id in q.gold_document_ids:
        if doc_id and f"gold:{doc_id}" in prompt:
            raise AssertionError(f"GOLD LEAK: gold document id {doc_id} in prompt.")


def _score(q: EnterpriseQuestion, answer: str, retrieved: list[str],
           ttft: float | None, out_tokens: int, evidence: str = "") -> ItemResult:
    abstained = ABSTAIN.lower() in answer.lower()
    if q.is_unanswerable:
        # For info_not_found, abstaining IS the correct answer. Scoring these
        # with F1 against a gold string would reward confident fabrication.
        correct_abstention = 1.0 if abstained else 0.0
        em = f1 = correct_abstention
    else:
        correct_abstention = 0.0 if abstained else 1.0
        em = exact_match(answer, q.gold_answer)
        f1 = token_f1(answer, q.gold_answer)
    faith = score_faithfulness(answer, evidence, q.atomic_facts)
    return ItemResult(
        question_id=q.id,
        category=q.category,
        answer=answer,
        retrieved_ids=retrieved,
        exact_match=em,
        token_f1=f1,
        doc_recall=supporting_fact_recall(retrieved, q.gold_document_ids),
        abstained=abstained,
        correct_abstention=correct_abstention,
        ttft_ms=ttft,
        output_tokens=out_tokens,
        fact_coverage=faith.fact_coverage,
        groundedness=faith.groundedness,
        unsupported_rate=faith.unsupported_rate,
    )


def _ask(client: LLMClient, prompt: str, streaming: bool) -> tuple[str, float | None, int]:
    resp = (client.complete_streaming(prompt, system=SYSTEM) if streaming
            else client.complete(prompt, system=SYSTEM))
    tokens = (resp.usage or {}).get("completion_tokens") or len(resp.text.split())
    return resp.text.strip(), resp.ttft_ms, tokens


def run_base(qs: list[EnterpriseQuestion], client: LLMClient, streaming: bool) -> ArmResult:
    """Arm 1: no retrieval. Establishes what the model already knows."""
    arm = ArmResult("base")
    for q in qs:
        prompt = f"QUESTION: {q.text}\nANSWER:"
        _assert_no_gold_leak(prompt, q)
        answer, ttft, tok = _ask(client, prompt, streaming)
        arm.items.append(_score(q, answer, [], ttft, tok))
    return arm


def run_rag(qs: list[EnterpriseQuestion], rag: StandaloneRAG,
            client: LLMClient, streaming: bool, top_k: int,
            doc_chars: int, total_chars: int) -> ArmResult:
    """Arm 2: StandaloneRAG retrieves for itself over the full corpus."""
    arm = ArmResult("rag")
    for q in qs:
        hits = rag.retrieve(q.text, top_k=top_k)
        ctx = _pack_context([(h.doc_id, h.text) for h in hits], doc_chars, total_chars)
        prompt = f"CONTEXT:\n{ctx}\n\nQUESTION: {q.text}\nANSWER:"
        _assert_no_gold_leak(prompt, q)
        answer, ttft, tok = _ask(client, prompt, streaming)
        arm.items.append(_score(q, answer, [h.doc_id for h in hits], ttft, tok, ctx))
    return arm


def run_tahi_l1(qs: list[EnterpriseQuestion], runtime: TahiRuntime,
                client: LLMClient, streaming: bool,
                doc_chars: int, total_chars: int) -> ArmResult:
    """Arm 3: the real TahiRuntime -- retrieve, plan, apply rules, fuse, inject.

    Unlike the retracted harness, this does not hand-build a CognitiveState from
    gold titles. It calls infer(), so Planner / RuleEngine / Simulator / Fusion
    are all exercised and the ControlPacket is the genuine product.
    """
    arm = ArmResult("tahi_l1")
    for q in qs:
        state = runtime.infer(query=q.text)
        packet = state.control_packet

        retrieved_ids = [
            r.node_id.split("doc::", 1)[-1]
            for r in state.retrievals
            if r.node_id.startswith("doc::")
        ]
        evidence = _pack_context(
            [(r.node_id, runtime.world_model.nodes.get(r.node_id, {}).get("text", ""))
             for r in state.retrievals],
            doc_chars, total_chars,
        )
        hints = "\n".join(f"- {h}" for h in (packet.prompt_hints if packet else []))
        entities = ", ".join(packet.active_entities) if packet else ""

        prompt = (
            f"WORLD MODEL GUIDANCE:\n{hints}\n"
            f"RELATED ENTITIES: {entities}\n\n"
            f"CONTEXT:\n{evidence}\n\n"
            f"QUESTION: {q.text}\nANSWER:"
        )
        _assert_no_gold_leak(prompt, q)
        answer, ttft, tok = _ask(client, prompt, streaming)
        arm.items.append(_score(q, answer, retrieved_ids, ttft, tok, evidence))
    return arm


def _self_test() -> int:
    """Verify wiring end-to-end on a tiny synthetic corpus, no download, no LLM."""
    log.info("Self-test: building a world model from 6 synthetic documents.")
    docs = [
        EnterpriseDocument(doc_id=f"d{i}", text=txt, source=src, container=cont)
        for i, (txt, src, cont) in enumerate([
            ("Kickoff for Project Atlas. Owner Dana.", "linear", "Atlas"),
            ("Atlas latency budget is 200ms p99. See ENG-412.", "confluence", "Atlas"),
            ("ENG-412: reduce p99 latency", "jira", "engineering"),
            ("Unrelated: office snacks poll.", "slack", "random"),
            ("Q3 revenue for Northwind closed at 1.2M.", "hubspot", ""),
            ("Atlas rollout scheduled for Nov.", "linear", "Atlas"),
        ])
    ]
    wm, stats = build_world_model(docs)
    log.info("nodes=%s edges=%s", stats.get("total_nodes"),
             sum(v for k, v in stats.items() if k.startswith("edge::")))
    for w in graph_health(stats):
        log.warning(w)

    runtime = TahiRuntime(world_model=wm, top_k=3)
    state = runtime.infer(query="What is the latency budget for Project Atlas?")
    docs_found = [r.node_id for r in state.retrievals if r.node_id.startswith("doc::")]
    log.info("retrieved: %s", docs_found)
    log.info("entities: %s", state.control_packet.active_entities if state.control_packet else [])
    assert state.control_packet is not None, "runtime produced no control packet"
    assert stats.get("edge::in_project", 0) >= 2, "project edges missing"
    assert stats.get("edge::mentions", 0) >= 1, "ticket extraction failed"
    log.info("SELF-TEST PASSED -- graph, runtime and control packet all wired.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="EnterpriseRAG-Bench: RAG vs TAHI")
    ap.add_argument("--questions", help="Path to questions.jsonl")
    ap.add_argument("--corpus", help="Path to extracted corpus directory")
    ap.add_argument("--limit", type=int, default=None, help="Max questions")
    ap.add_argument("--max-docs", type=int, default=None, help="Cap corpus size")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--doc-chars", type=int, default=DEFAULT_DOC_CHARS,
                    help="Per-document character cap (identical across arms)")
    ap.add_argument("--context-chars", type=int, default=DEFAULT_CONTEXT_CHARS,
                    help="Total evidence character budget (identical across arms)")
    ap.add_argument("--max-tokens", type=int, default=256,
                    help="Answer token budget; must leave room inside the model context")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--arms", default="base,rag,tahi_l1")
    ap.add_argument("--no-streaming", action="store_true",
                    help="Disable streaming (loses real TTFT)")
    ap.add_argument("--output", default="benchmarks/results/enterprise_rag.json")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if not args.questions or not args.corpus:
        ap.error("--questions and --corpus are required (or use --self-test)")

    started = time.perf_counter()
    arms_wanted = {a.strip() for a in args.arms.split(",") if a.strip()}

    # Fail loudly before spending anything.
    env = require_ready(need_llm=True, need_encoder=True)
    log.info("Preflight OK: encoder=%s on %s", env.encoder_name, env.encoder_device)
    for w in env.warnings:
        log.warning(w)

    questions = load_questions(args.questions)
    if args.limit and args.limit < len(questions):
        # Stratified, NOT first-N. questions.jsonl is ordered by category, so a
        # head-slice silently yields an all-`basic` sample with zero
        # structure-sensitive items -- i.e. it excludes exactly the categories
        # the thesis is about, while still looking like a valid subset.
        import random as _random
        from collections import defaultdict
        buckets = defaultdict(list)
        for q in questions:
            buckets[q.category].append(q)
        rng = _random.Random(args.seed)
        share = args.limit / len(questions)
        sampled = []
        for cat in sorted(buckets):
            items = sorted(buckets[cat], key=lambda x: x.id)
            rng.shuffle(items)
            take = max(1, round(len(items) * share))
            sampled.extend(items[:take])
        questions = sorted(sampled, key=lambda x: x.id)[: args.limit]
        log.info("Stratified sample of %d questions (proportional by category).",
                 len(questions))
    stats_q = summarize(questions)
    log.info("Loaded %d questions: %s", len(questions), stats_q["by_category"])
    log.warning("Underpowered per-category: %s", stats_q["underpowered_categories"])
    log.info("Pooled structure-sensitive n=%d (need %d) -> primary comparison",
             stats_q["structure_sensitive_n"], stats_q["required_n_for_0.10_delta"])

    log.info("Loading corpus from %s ...", args.corpus)
    docs: list[EnterpriseDocument] = []
    for d in iter_documents(args.corpus):
        docs.append(d)
        if args.max_docs and len(docs) >= args.max_docs:
            log.warning("Corpus capped at --max-docs=%d. This is a COVERAGE LIMIT: "
                        "recall figures are not comparable to a full-corpus run.",
                        args.max_docs)
            break
    log.info("Loaded %d documents.", len(docs))

    client = LLMClient(strict=True, max_tokens=args.max_tokens)
    streaming = not args.no_streaming
    results: list[ArmResult] = []

    if "base" in arms_wanted:
        log.info("Arm 1/3: base (no retrieval)")
        results.append(run_base(questions, client, streaming))

    if "rag" in arms_wanted:
        log.info("Arm 2/3: StandaloneRAG (dense top-%d)", args.top_k)
        rag = StandaloneRAG(top_k=args.top_k, llm_client=client)
        rag.add_documents([RAGDocument(d.doc_id, d.text, d.metadata) for d in docs])
        rag.build_index()
        results.append(run_rag(questions, rag, client, streaming, args.top_k,
                               args.doc_chars, args.context_chars))

    graph_stats: dict[str, int] = {}
    if "tahi_l1" in arms_wanted:
        log.info("Arm 3/3: TAHI Level 1 (graph + vector)")
        wm, graph_stats = build_world_model(docs)
        for w in graph_health(graph_stats):
            log.warning(w)
        runtime = TahiRuntime(world_model=wm, top_k=args.top_k)
        results.append(run_tahi_l1(questions, runtime, client, streaming,
                                  args.doc_chars, args.context_chars))

    # Cost is apportioned per arm by share of calls -- approximate but honest,
    # and flagged as such rather than presented as exact.
    usage = client.usage_summary()
    per_arm_cost = usage["est_cost_usd"] / max(len(results), 1)

    arm_summaries = []
    for arm in results:
        n_correct = sum(1 for i in arm.items if i.exact_match == 1.0)
        arm_summaries.append(arm.summary(per_arm_cost, n_correct))

    # Significance: every pairwise comparison, on F1 and on EM.
    comparisons = []
    by_name = {a.name: a for a in results}
    for a, b in (("base", "rag"), ("rag", "tahi_l1"), ("base", "tahi_l1")):
        if a in by_name and b in by_name:
            comparisons.append(
                bootstrap_paired_delta(
                    by_name[a].f1_scores(), by_name[b].f1_scores(),
                    arm_a=a, arm_b=b, seed=args.seed,
                ).to_dict()
            )
            comparisons.append(
                bootstrap_paired_delta(
                    by_name[a].coverage_scores(), by_name[b].coverage_scores(),
                    arm_a=f"{a}[fact_coverage]", arm_b=f"{b}[fact_coverage]", seed=args.seed,
                ).to_dict()
            )
            # Pooled structure-sensitive subset: the pre-registered primary test.
            idx = [i for i, q in enumerate(questions) if q.category in STRUCTURE_SENSITIVE]
            if len(idx) >= 30:
                c = bootstrap_paired_delta(
                    [by_name[a].f1_scores()[i] for i in idx],
                    [by_name[b].f1_scores()[i] for i in idx],
                    arm_a=f"{a}[structural]", arm_b=f"{b}[structural]", seed=args.seed,
                ).to_dict()
                comparisons.append(c)

    manifest = RunManifest(
        benchmark="EnterpriseRAG-Bench",
        dataset=str(args.questions),
        dataset_sha256=sha256_of_obj([q.id for q in questions]),
        n_items=len(questions),
        seed=args.seed,
        provider=client.provider,
        model=client.model,
        encoder=env.encoder_name,
        encoder_is_fallback=False,
        strict_mode=True,
        wall_clock_s=time.perf_counter() - started,
        llm_usage=usage,
        notes=(
            f"Corpus: {len(docs)} documents"
            + (f" (CAPPED at --max-docs={args.max_docs})" if args.max_docs else "")
            + f". Graph: {sum(v for k,v in graph_stats.items() if k.startswith('edge::'))} edges. "
            f"Context budget: {args.context_chars} chars total / {args.doc_chars} per doc "
            f"(identical across arms). Streaming TTFT: {streaming}. "
            f"Per-arm cost is total/{len(results)} (approximate apportionment). "
            f"Underpowered categories: {stats_q['underpowered_categories']}."
        ),
    )

    out = write_artifact(
        args.output, manifest,
        {
            "arms": arm_summaries,
            "comparisons": comparisons,
            "question_stats": stats_q,
            "graph_stats": graph_stats,
            "per_item": [
                {"arm": a.name, **vars(i)} for a in results for i in a.items
            ],
        },
    )
    report = write_report(out)
    log.info("Wrote %s and %s", out, report)

    print()
    for c in comparisons:
        print("  " + c["verdict"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
