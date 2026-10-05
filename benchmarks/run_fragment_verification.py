#!/usr/bin/env python
"""
Fragment verification: can TAHI tell a true claim from a false one?

This isolates the mechanism the end-to-end benchmark could not. There, a null
result had at least four possible causes -- bad retrieval, bad generation, a
weak metric, or a wrong thesis -- and no way to tell them apart. Here the only
thing under test is whether querying the world model separates true fragments
from false ones.

It is also the unit that Level 3 actually operates on. GCCA retrieves memory per
generation chunk; if a lookup cannot distinguish "the limit is 10 MiB" from
"the limit is 50 MiB", no amount of cross-attention over that memory will help.
Fragment verification is the precondition for Level 3 being worth building.

Method
------
1. Take gold atomic facts from EnterpriseRAG-Bench (`answer_facts`). These are
   TRUE by construction -- no LLM judge, no annotation cost.
2. Generate a FALSE counterpart for each by a targeted perturbation:
      numeric   10 MiB -> 50 MiB          (precision)
      entity    Project Atlas -> Project Vega  (binding)
      negation  "is supported" -> "is not supported"  (polarity)
      swap      recombine two unrelated facts   (fabrication)
   Each perturbation stays lexically close to the original, so a system cannot
   pass by noticing that false fragments merely look different.
3. Retrieve evidence for each fragment -- once via TAHI (graph + vector), once
   via vector-only -- and score how well the evidence supports it.
4. Report separation between true and false fragments, per arm.

The headline number is AUC: the probability that a randomly chosen true
fragment scores above a randomly chosen false one. 0.5 is chance. A system that
cannot beat chance here cannot ground generation, whatever its end-to-end score.
"""

from __future__ import annotations

import argparse
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from implementations.enterprise_rag import iter_documents, load_questions  # noqa: E402
from implementations.enterprise_rag.world_model import (  # noqa: E402
    build_world_model,
    graph_health,
)
from tahi.eval.manifest import RunManifest, sha256_of_obj, write_artifact  # noqa: E402
from tahi.eval.nli_evaluator import NLIEvaluator  # noqa: E402
from tahi.eval.stats import bootstrap_paired_delta  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tahi.fragverify")

NUM_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")
CAP_RE = re.compile(r"\b([A-Z][a-zA-Z]{3,})\b")
NEGATABLE = [
    (" is ", " is not "), (" are ", " are not "), (" was ", " was not "),
    (" will ", " will not "), (" can ", " cannot "), (" has ", " has no "),
    (" does ", " does not "), (" must ", " must not "),
]


@dataclass
class Fragment:
    text: str
    label: int              # 1 = true, 0 = false
    perturbation: str       # "none" | numeric | entity | negation | swap
    source_qid: str
    category: str


@dataclass
class ArmScores:
    name: str
    scores: list[float] = field(default_factory=list)
    labels: list[int] = field(default_factory=list)
    retrieved: list[list[str]] = field(default_factory=list)

    def auc(self) -> float:
        """Probability a random true fragment outranks a random false one.

        Computed directly rather than via a threshold, so it does not depend on
        picking a cutoff. Ties count as half, which is what makes a system that
        returns a constant score land at exactly 0.5 instead of looking good.
        """
        pos = [s for s, lab in zip(self.scores, self.labels, strict=False) if lab == 1]
        neg = [s for s, lab in zip(self.scores, self.labels, strict=False) if lab == 0]
        if not pos or not neg:
            return 0.5
        wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
        return wins / (len(pos) * len(neg))

    def separation(self) -> dict[str, float]:
        pos = [s for s, lab in zip(self.scores, self.labels, strict=False) if lab == 1]
        neg = [s for s, lab in zip(self.scores, self.labels, strict=False) if lab == 0]
        mp = sum(pos) / len(pos) if pos else 0.0
        mn = sum(neg) / len(neg) if neg else 0.0
        return {"mean_true": mp, "mean_false": mn, "gap": mp - mn}

    def paired_deltas(self) -> list[float]:
        """Per-pair (true - false) margins, for a paired significance test.

        Fragments are generated in true/false pairs from the same source fact,
        so pairing removes the between-fact difficulty variance that would
        otherwise swamp the effect.
        """
        out = []
        for i in range(0, len(self.scores) - 1, 2):
            if self.labels[i] == 1 and self.labels[i + 1] == 0:
                out.append(self.scores[i] - self.scores[i + 1])
        return out


def perturb(fact: str, other_facts: list[str], rng: random.Random) -> tuple[str, str] | None:
    """Return (false_variant, perturbation_kind), or None if not perturbable."""
    kinds = rng.sample(["numeric", "entity", "negation", "swap"], 4)
    for kind in kinds:
        if kind == "numeric":
            nums = NUM_RE.findall(fact)
            if nums:
                target = rng.choice(nums)
                val = float(target)
                # A materially different magnitude, not a rounding difference --
                # otherwise "false" is arguably just imprecise.
                new = str(int(val * 5) + 7) if val == int(val) else f"{val * 5 + 7:.1f}"
                return fact.replace(target, new, 1), "numeric"
        elif kind == "entity":
            caps = [c for c in CAP_RE.findall(fact) if c.lower() not in
                    ("the", "this", "that", "these", "there", "when", "what")]
            if caps:
                target = rng.choice(caps)
                pool = [c for f in other_facts for c in CAP_RE.findall(f)
                        if c != target and len(c) > 3]
                if pool:
                    return fact.replace(target, rng.choice(pool), 1), "entity"
        elif kind == "negation":
            for pos, neg in NEGATABLE:
                if pos in fact:
                    return fact.replace(pos, neg, 1), "negation"
        elif kind == "swap":
            if other_facts:
                other = rng.choice(other_facts)
                a = fact.split()
                b = other.split()
                if len(a) > 6 and len(b) > 6:
                    # Graft the tail of an unrelated fact onto this one's head.
                    return " ".join(a[: len(a) // 2] + b[len(b) // 2:]), "swap"
    return None


def build_fragments(questions, limit: int, seed: int) -> list[Fragment]:
    rng = random.Random(seed)
    pool = [(q, f) for q in questions for f in q.atomic_facts if len(f.split()) >= 6]
    rng.shuffle(pool)
    all_facts = [f for _, f in pool]

    frags: list[Fragment] = []
    for q, fact in pool:
        others = rng.sample(all_facts, min(8, len(all_facts)))
        p = perturb(fact, [o for o in others if o != fact], rng)
        if p is None:
            continue
        false_text, kind = p
        if false_text.strip() == fact.strip():
            continue
        # Emitted adjacently so `paired_deltas` can pair them.
        frags.append(Fragment(fact, 1, "none", q.id, q.category))
        frags.append(Fragment(false_text, 0, kind, q.id, q.category))
        if len(frags) >= limit * 2:
            break
    return frags


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--n-fragments", type=int, default=150,
                    help="True fragments; an equal number of false ones is generated")
    ap.add_argument("--max-docs", type=int, default=60000)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--output", default="benchmarks/results/fragment_verification.json")
    args = ap.parse_args()

    started = time.perf_counter()
    questions = load_questions(args.questions)
    frags = build_fragments(questions, args.n_fragments, args.seed)
    n_true = sum(f.label for f in frags)
    log.info("Built %d fragments (%d true / %d false)", len(frags), n_true, len(frags) - n_true)
    kinds: dict[str, int] = {}
    for f in frags:
        if f.label == 0:
            kinds[f.perturbation] = kinds.get(f.perturbation, 0) + 1
    log.info("Perturbations: %s", kinds)
    if n_true < 20:
        log.error("Too few fragments to measure anything.")
        return 1

    docs = []
    for d in iter_documents(args.corpus):
        docs.append(d)
        if args.max_docs and len(docs) >= args.max_docs:
            break
    log.info("Loaded %d documents", len(docs))

    wm, gstats = build_world_model(docs)
    for w in graph_health(gstats):
        log.warning(w)

    arms = {"vector_only": ArmScores("vector_only"), "tahi_graph": ArmScores("tahi_graph")}
    log.info("Initializing NLI Evaluator for polarity-aware truthfulness scoring...")
    nli = NLIEvaluator()

    for i, frag in enumerate(frags):
        if i % 50 == 0:
            log.info("fragment %d/%d", i, len(frags))
        for name, expand in (("vector_only", False), ("tahi_graph", True)):
            hits = wm.retrieve(frag.text, top_k=args.top_k, expand=expand)
            evidence = " ".join(
                wm.nodes.get(h.node_id, {}).get("text", "")[:1500] for h in hits
            )
            nli_res = nli.score_pair(evidence, frag.text)
            arms[name].scores.append(nli_res["truth_score"])
            arms[name].labels.append(frag.label)
            arms[name].retrieved.append([h.node_id for h in hits])

    summaries = []
    for name, arm in arms.items():
        sep = arm.separation()
        summaries.append({
            "name": name, "n": len(arm.scores), "auc": arm.auc(),
            "mean_true": sep["mean_true"], "mean_false": sep["mean_false"],
            "gap": sep["gap"],
            # Report-schema columns kept uniform across benchmarks.
            "exact_match": None, "token_f1": None, "fact_coverage": None,
            "groundedness": sep["mean_true"], "unsupported_rate": 1 - sep["mean_true"],
            "supporting_fact_recall": None, "abstention_accuracy": None,
            "ttft_ms": None, "output_tokens": None, "cost_per_correct_usd": None,
        })
        log.info("%-12s AUC=%.4f  true=%.4f  false=%.4f  gap=%+.4f",
                 name, arm.auc(), sep["mean_true"], sep["mean_false"], sep["gap"])

    v = arms["vector_only"].paired_deltas()
    o = arms["tahi_graph"].paired_deltas()
    comparisons = []
    if len(v) == len(o) and len(v) >= 20:
        comparisons.append(bootstrap_paired_delta(
            v, o, arm_a="vector_only[margin]", arm_b="tahi_graph[margin]",
            seed=args.seed).to_dict())

    # Per-perturbation AUC: which failure mode can each arm actually catch?
    by_kind: dict[str, dict[str, float]] = {}
    for kind in set(f.perturbation for f in frags if f.label == 0):
        idx = [i for i, f in enumerate(frags)
               if f.perturbation == kind or (f.label == 1)]
        for name, arm in arms.items():
            sub = ArmScores(name)
            for i in idx:
                sub.scores.append(arm.scores[i])
                sub.labels.append(arm.labels[i])
            by_kind.setdefault(kind, {})[name] = sub.auc()

    manifest = RunManifest(
        benchmark="Fragment Verification (KG/vector claim grounding)",
        dataset=str(args.questions),
        dataset_sha256=sha256_of_obj([f.text for f in frags]),
        n_items=len(frags), seed=args.seed,
        provider="retrieval-only", model="none (no generation)",
        encoder=f"sentence-transformers (d={wm._encoder.dimension})",  # noqa: SLF001
        encoder_is_fallback=False, strict_mode=True,
        wall_clock_s=time.perf_counter() - started,
        llm_usage={"total_calls": 0, "est_cost_usd": 0.0, "fallback_calls": 0},
        notes=(
            f"No LLM in the loop -- ground truth is by construction. "
            f"Corpus: {len(docs)} docs"
            + (f" (CAPPED at {args.max_docs})" if args.max_docs else "")
            + f", {sum(x for k, x in gstats.items() if k.startswith('edge::'))} edges. "
            f"top_k={args.top_k}. Perturbations: {kinds}. "
            f"AUC 0.5 = chance."
        ),
    )

    out = write_artifact(args.output, manifest, {
        "arms": summaries, "comparisons": comparisons,
        "auc_by_perturbation": by_kind, "graph_stats": gstats,
        "per_fragment": [
            {"text": f.text, "label": f.label, "perturbation": f.perturbation,
             "category": f.category, "source_qid": f.source_qid,
             "vector_only": arms["vector_only"].scores[i],
             "tahi_graph": arms["tahi_graph"].scores[i]}
            for i, f in enumerate(frags)
        ],
    })
    log.info("Wrote %s", out)

    print("\n=== AUC (0.5 = chance) ===")
    for s in summaries:
        print(f"  {s['name']:<12} AUC={s['auc']:.4f}  "
              f"true={s['mean_true']:.4f} false={s['mean_false']:.4f} "
              f"gap={s['gap']:+.4f}")
    print("\n=== AUC by perturbation ===")
    for kind, d in sorted(by_kind.items()):
        print(f"  {kind:<10} " + "  ".join(f"{k}={x:.4f}" for k, x in d.items()))
    for c in comparisons:
        print("\n  " + c["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
