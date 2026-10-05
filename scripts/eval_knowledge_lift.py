#!/usr/bin/env python
"""Does supplied graph knowledge lift the model's answers?

Criteria: `benchmarks/PREREGISTRATION_knowledge_lift.md`, written before this ran.

Retrieval is not under test here. The facts a perfect graph lookup *would* have
returned are handed to the model directly, and the only question is whether its
answers get better. That separates two failures which every previous result in
this project confounded: retrieval not finding the fact, and the model not using
a fact it was given.

    PYTHONPATH=src .venv/bin/python scripts/eval_knowledge_lift.py --limit 400
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
import re
import string
import sys
from collections import defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.build_metaqa_corpus import ATTRIBUTE_TAILS, load_triples  # noqa: E402
from scripts.eval_continuation import (  # noqa: E402
    build_adjacency,
    find_path,
    verbalise,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tahi.knowledge_lift")

CONDITIONS = ("closed", "random", "gold", "gold+noise")

# Conditions that put *retrieved* facts in the same slot the correct facts go in.
# The corpus is one triple per passage, written by the same templates that write
# the correct facts, so format, length and vocabulary are held constant and the
# only thing that differs between these rows is which facts got selected.
RETRIEVAL_CONDITIONS = ("dense", "hybrid", "graph", "graph|hybrid")

# Words a MetaQA question uses for each KB relation. The questions are templated
# and always name the relation they need, so this is a lookup rather than a
# guess -- and it is the piece a partner would replace with real text-to-query.
RELATION_WORDS = {
    "direct": "directed_by", "director": "directed_by",
    "star": "starred_actors", "actor": "starred_actors", "acted": "starred_actors",
    "wrote": "written_by", "writer": "written_by", "written": "written_by",
    "screenwriter": "written_by",
    "language": "in_language",
    "genre": "has_genre", "type": "has_genre",
    "release": "release_year", "year": "release_year",
    "rating": "has_imdb_rating", "rated": "has_imdb_rating",
    "votes": "has_imdb_votes", "popular": "has_imdb_votes",
    "tag": "has_tags", "topic": "has_tags",
}

LABELS = {
    "closed": "no facts supplied",
    "random": "wrong facts supplied",
    "gold": "correct facts supplied (perfect lookup)",
    "gold+noise": "correct facts mixed with wrong ones",
    "dense": "retrieved: vector search",
    "hybrid": "retrieved: vector + keyword (MAAILMA's method)",
    "graph": "retrieved: graph traversal (Tahi)",
    "graph|hybrid": "retrieved: graph + vector + keyword",
}

SYSTEM = ("You answer questions about films. Answer with the answer only, "
          "no explanation, no full sentence.")


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #

def normalise(s: str) -> str:
    """SQuAD-style normalisation: lowercase, strip articles and punctuation."""
    s = s.lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    return " ".join(s.split())


def parse_answers(pred: str) -> list[str]:
    """Split a free-text answer into the answer *set* the model gave.

    MetaQA answers are sets ("English, French"), and the standard metrics are
    defined over sets, so the prediction has to be parsed into one rather than
    compared as a string.
    """
    parts = re.split(r",|\band\b|\n|;|/", pred)
    out, seen = [], set()
    for part in parts:
        n = normalise(part)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def hits_at_1(pred: str, golds: list[str]) -> float:
    """MetaQA's headline metric: is the model's FIRST answer in the gold set?

    Equality after normalisation, not containment. The containment rule this
    replaces scored "drama and crime" as correct for gold "Crime", which
    flattered every condition and the closed-book baseline most.
    """
    parsed = parse_answers(pred)
    if not parsed:
        return 0.0
    gold_set = {normalise(g) for g in golds}
    return 1.0 if parsed[0] in gold_set else 0.0


def full_match(pred: str, golds: list[str]) -> float:
    """The whole predicted set equals the whole gold set. The strict metric."""
    return 1.0 if set(parse_answers(pred)) == {normalise(g) for g in golds} else 0.0


def answer_set_f1(pred: str, golds: list[str]) -> float:
    """F1 over answer sets — partial credit when the gold set has several members
    and the model names some of them. Token F1 rewards overlapping *words*, which
    for entity names is not the same question."""
    p = set(parse_answers(pred))
    g = {normalise(x) for x in golds}
    if not p or not g:
        return 0.0
    tp = len(p & g)
    if tp == 0:
        return 0.0
    precision, recall = tp / len(p), tp / len(g)
    return 2 * precision * recall / (precision + recall)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Correct near 0 and 1, where the normal
    approximation produces bounds outside [0, 1]."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar(a: list[float], b: list[float]) -> dict:
    """Paired test for two conditions scored on the SAME items.

    Every condition here answers the same questions, so the observations are
    paired and only the disagreements carry information. Comparing two
    independent proportions -- which is what the first version of this script
    did -- discards that pairing and is both the wrong test and a weaker one.

    Exact binomial when the disagreement count is small, chi-square with
    continuity correction otherwise, per standard practice.
    """
    b_only = sum(1 for x, y in zip(a, b, strict=True) if y > x)   # b right, a wrong
    a_only = sum(1 for x, y in zip(a, b, strict=True) if x > y)   # a right, b wrong
    n_disagree = a_only + b_only
    if n_disagree == 0:
        return {"gained": 0, "lost": 0, "p_value": 1.0, "test": "none"}
    if n_disagree < 25:
        k = min(a_only, b_only)
        total = sum(math.comb(n_disagree, i) for i in range(k + 1))
        p = min(1.0, 2.0 * total / (2 ** n_disagree))
        test = "exact binomial"
    else:
        chi2 = (abs(b_only - a_only) - 1) ** 2 / n_disagree
        p = math.erfc(math.sqrt(chi2 / 2.0))
        test = "chi-square, continuity-corrected"
    return {"gained": b_only, "lost": a_only, "p_value": p, "test": test}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni. Four comparisons are made against one baseline; without
    correction the chance of one crossing 0.05 by luck is far above 0.05."""
    order = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(order)
    adjusted, running = {}, 0.0
    for i, (name, p) in enumerate(order):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[name] = running
    return adjusted


def se(p: float, n: int) -> float:
    return math.sqrt(max(p * (1 - p), 0.0) / n) if n else 0.0


# --------------------------------------------------------------------------- #
# items
# --------------------------------------------------------------------------- #

def build_items(questions, adj, subjects, attr_values, limit, rng):
    """One item per question, carrying the facts on its own 3-hop path."""
    pool = list(questions)
    rng.shuffle(pool)
    items = []
    for q in pool:
        if len(items) >= limit:
            break
        seeds = q.get("q_entity") or []
        answers = q.get("answers") or []
        if not seeds or not answers:
            continue
        path = find_path(seeds[0], set(answers), adj, subjects, attr_values)
        if path is None:
            continue
        facts = [verbalise(src, rel, dst, fwd) for src, rel, dst, fwd in path]
        # The answer the supplied facts actually support. MetaQA answer sets hold
        # several correct answers and `find_path` reaches whichever one its walk
        # arrives at, so scoring `answers[0]` teacher-forced can measure the
        # probability of an answer the facts argue *against*. That inverted the
        # log-probability column: `gold` read worse than `closed` while its exact
        # match was 1.000.
        joined = " ".join(facts).lower()
        supported = next((a for a in answers if a.lower() in joined), answers[0])
        items.append({
            "id": q["id"],
            "question": q["question"],
            "answers": answers,
            "supported_answer": supported,
            "facts": facts,
        })
    log.info("built %d items", len(items))
    return items


def noise_facts(items, i, k, rng):
    """Facts from other questions' paths. Same shape, same vocabulary, wrong content.

    Drawn from the item pool rather than generated so that a difference between
    `gold` and `random` cannot be explained by the two looking different."""
    out = []
    while len(out) < k:
        j = rng.randrange(len(items))
        if j == i:
            continue
        out.extend(items[j]["facts"])
    return out[:k]


def build_prompt(tok, item, condition, items, i, rng):
    facts: list[str] = []
    if condition == "random":
        facts = noise_facts(items, i, 3, rng)
    elif condition == "gold":
        facts = list(item["facts"])
    elif condition == "gold+noise":
        facts = list(item["facts"]) + noise_facts(items, i, 7, rng)
        rng.shuffle(facts)
    elif condition in RETRIEVAL_CONDITIONS:
        facts = item["retrieved"][condition]

    if facts:
        body = "Facts:\n" + "\n".join(f"- {f}" for f in facts) + \
               f"\n\nQuestion: {item['question']}\nAnswer:"
    else:
        body = f"Question: {item['question']}\nAnswer:"
    return tok.apply_chat_template(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}],
        tokenize=False, add_generation_prompt=True)


# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #

@torch.no_grad()
def generate(model, tok, prompts, max_new_tokens, batch_size):
    out = []
    for s in range(0, len(prompts), batch_size):
        batch = prompts[s: s + batch_size]
        enc = tok(batch, return_tensors="pt", padding=True,
                  padding_side="left").to(model.device)
        gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                             pad_token_id=tok.pad_token_id)
        for j in range(len(batch)):
            new = gen[j, enc["input_ids"].shape[1]:]
            out.append(tok.decode(new, skip_special_tokens=True).strip())
        if s % (batch_size * 8) == 0:
            log.info("  generated %d/%d", s + len(batch), len(prompts))
    return out


@torch.no_grad()
def gold_logprob(model, tok, prompt, answer):
    """Mean log-probability of the gold answer, teacher-forced.

    Exact match reads 0.000 whether the model is missing the fact or merely
    ranking it second. This does not: it is continuous, and it moves before the
    decoded string does.
    """
    p_ids = tok(prompt, return_tensors="pt").input_ids.to(model.device)
    a_ids = tok(answer, add_special_tokens=False, return_tensors="pt").input_ids.to(model.device)
    ids = torch.cat([p_ids, a_ids], dim=1)
    logits = model(ids).logits[:, :-1]
    targets = ids[:, 1:]
    logprobs = torch.log_softmax(logits.float(), dim=-1)
    picked = logprobs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
    answer_span = picked[:, p_ids.shape[1] - 1:]
    return float(answer_span.mean())


def attach_retrieval(items, args, triples, adj, attr_values):
    """Fill `item["retrieved"][arm]` with the top-k facts each retriever returns.

    Retrieval runs over `corpus_fact.jsonl` -- one triple per passage, written by
    the templates that also write the correct facts. Holding the unit and the
    wording constant is the point: any difference between these conditions and
    the correct-facts condition is a difference in *which* facts were selected,
    not in how they read.
    """
    import numpy as np

    from scripts.eval_continuation import load_corpus
    from scripts.eval_graph_vs_ann import BM25, minmax, topk

    rows = load_corpus(Path(args.fact_corpus))
    texts = [r["text"] for r in rows]
    log.info("fact corpus: %d passages", len(rows))

    from tahi.retrieval.ann import get_encoder
    enc = get_encoder()
    cache = Path(args.fact_cache)
    if cache.exists():
        emb = np.load(cache)
    else:
        emb = np.asarray(enc.encode(texts), dtype="float32")
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, emb)
    emb = emb / np.linalg.norm(emb, axis=1, keepdims=True).clip(min=1e-12)
    bm25 = BM25(texts)

    # Facts incident to each entity, so a traversal result can be turned into the
    # same unit the other arms return.
    incident: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        for e in r["entities"]:
            incident[e].append(i)

    from tahi.graph.entity_linker import EntityLinker
    linker = EntityLinker({e for r in rows for e in r["entities"]})
    degree = {e: len(v) for e, v in adj.items()}

    def graph_facts(question: str, k: int, max_hops: int) -> list[int]:
        """Walk the graph along the relations the question names.

        Two earlier versions of this were strawmen and both flattered the vector
        arm. The first walked one hop, so on a three-hop question the fact
        carrying the answer was unreachable. The second walked three hops but
        ranked facts nearest-first, and the entity named in the question has a
        median of 12 facts hanging off it -- so all five slots went to facts
        about the movie the asker already knew about.

        MetaQA questions state their own relations in words: "the *director* of",
        "who *starred*", "what *language*". Matching those words to the nine KB
        relations turns the walk from a flood into a query, and ranking the
        result deepest-first puts the end of the chain -- where the answer lives
        -- in the budget. No embedding is read anywhere in here.
        """
        allowed = {rel for word, rel in RELATION_WORDS.items() if word in question.lower()}
        linked = linker.link(question, max_hits=4)
        ranked: list[tuple[int, int, int]] = []       # (-hop, degree, fact index)
        seen_facts: set[int] = set()
        frontier, visited = list(linked), set(linked)

        for hop in range(max_hops):
            nxt: list[str] = []
            for e in frontier:
                for _rel, nb, _fwd in adj.get(e, ()):
                    if nb in visited or (nb in attr_values and nb not in adj):
                        continue
                    visited.add(nb)
                    nxt.append(nb)
                for fi in incident.get(e, ()):
                    if fi in seen_facts:
                        continue
                    # Only facts using a relation the question asked about. With
                    # no relation word matched, everything is admitted and this
                    # degrades to the flood -- which is the honest behaviour when
                    # the question gives the graph nothing to go on.
                    if allowed and rows[fi]["triple"][1] not in allowed:
                        continue
                    seen_facts.add(fi)
                    other = [x for x in rows[fi]["entities"] if x != e]
                    ranked.append((-hop, degree.get(other[0], 0) if other else 0, fi))
            frontier = nxt
            if not frontier:
                break

        ranked.sort()
        return [fi for _h, _d, fi in ranked[:k]]

    k = args.retrieval_k
    queries = [it["question"] for it in items]
    q_emb = np.asarray(enc.encode(queries), dtype="float32")
    q_emb /= np.linalg.norm(q_emb, axis=1, keepdims=True).clip(min=1e-12)

    for i, it in enumerate(items):
        d = emb @ q_emb[i]
        lx = bm25.scores(it["question"])
        hy = minmax(d) + minmax(lx)
        d_idx, h_idx = topk(d, k), topk(hy, k)
        g_idx = graph_facts(it["question"], k, args.graph_hops)
        inter: list[int] = []
        for a, b in zip(g_idx, h_idx, strict=False):
            inter += [a, b]
        inter += g_idx[len(h_idx):] + h_idx[len(g_idx):]
        it["retrieved"] = {
            "dense": [texts[j] for j in d_idx],
            "hybrid": [texts[j] for j in h_idx],
            "graph": [texts[j] for j in g_idx],
            "graph|hybrid": [texts[j] for j in list(dict.fromkeys(inter))[:k]],
        }
        if i % 100 == 0:
            log.info("  retrieval %d/%d", i, len(items))
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--max-new-tokens", type=int, default=32)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--logprob-sample", type=int, default=100,
                    help="items to score teacher-forced; one forward pass each")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--with-retrieval", action="store_true",
                    help="add the conditions that put *retrieved* facts in the "
                         "same slot, so 'can we find them' is separated from "
                         "'do they help'")
    ap.add_argument("--retrieval-k", type=int, default=5)
    ap.add_argument("--graph-hops", type=int, default=3,
                    help="traversal depth. MetaQA 3-hop questions need 3; a "
                         "shallower walk cannot reach the answer at all.")
    ap.add_argument("--fact-corpus", default="data/metaqa/corpus_fact.jsonl")
    ap.add_argument("--fact-cache", default="data/metaqa/corpus_fact_emb.npy")
    ap.add_argument("--out", default="benchmarks/results/knowledge_lift.json")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    triples = load_triples(Path(args.kb))
    adj, subjects = build_adjacency(triples)
    attr_values = {o for _, r, o in triples if r in ATTRIBUTE_TAILS}
    questions = json.loads(Path(args.questions).read_text())
    items = build_items(questions, adj, subjects, attr_values, args.limit, rng)
    if not items:
        log.error("no items built")
        return 1

    conditions = list(CONDITIONS)
    if args.with_retrieval:
        items = attach_retrieval(items, args, triples, adj, attr_values)
        conditions += list(RETRIEVAL_CONDITIONS)

    from transformers import AutoModelForCausalLM, AutoTokenizer
    log.info("loading %s", args.model)
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16).to("cuda:0")
    model.eval()

    results: dict[str, dict] = {}
    per_condition_preds: dict[str, list[str]] = {}
    for condition in conditions:
        prompt_rng = random.Random(args.seed)     # same noise draw across conditions
        prompts = [build_prompt(tok, it, condition, items, i, prompt_rng)
                   for i, it in enumerate(items)]
        log.info("condition %s", condition)
        preds = generate(model, tok, prompts, args.max_new_tokens, args.batch_size)
        per_condition_preds[condition] = preds

        h1 = [hits_at_1(p, it["answers"]) for p, it in zip(preds, items, strict=True)]
        fu = [full_match(p, it["answers"]) for p, it in zip(preds, items, strict=True)]
        sf = [answer_set_f1(p, it["answers"]) for p, it in zip(preds, items, strict=True)]

        lp_rng = random.Random(args.seed)
        sample = list(range(min(args.logprob_sample, len(items))))
        lps = []
        for i in sample:
            prompt = build_prompt(tok, items[i], condition, items, i,
                                  random.Random(args.seed))
            lps.append(gold_logprob(model, tok, prompt,
                                    " " + items[i]["supported_answer"]))
        del lp_rng

        lo, hi = wilson(int(sum(h1)), len(h1))
        results[condition] = {
            "hits_at_1": sum(h1) / len(h1),
            "hits_at_1_ci": [lo, hi],
            "full": sum(fu) / len(fu),
            "answer_set_f1": sum(sf) / len(sf),
            "answer_logprob": sum(lps) / len(lps),
            "n": len(h1),
            "n_logprob": len(lps),
            "_per_item_hits": h1,
        }
        log.info("  hits@1=%.3f full=%.3f", results[condition]["hits_at_1"],
                 results[condition]["full"])

    report = {"model": args.model, "n_items": len(items), "conditions": results,
              "examples": [
                  {"question": items[i]["question"],
                   "answers": items[i]["answers"][:3],
                   "facts": items[i]["facts"],
                   **{c: per_condition_preds[c][i] for c in conditions}}
                  for i in range(min(5, len(items)))]}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    n = len(items)
    baseline = "no facts supplied"
    label = LABELS

    comparisons = {}
    for c in conditions:
        if c == "closed":
            continue
        comparisons[label[c]] = mcnemar(results["closed"]["_per_item_hits"],
                                        results[c]["_per_item_hits"])
    adjusted = holm({k: v["p_value"] for k, v in comparisons.items()})
    for k in comparisons:
        comparisons[k]["p_value_holm"] = adjusted[k]

    for c in conditions:
        results[c].pop("_per_item_hits", None)

    report = {"model": args.model, "n_items": len(items),
              "conventions": "docs/EVAL_CONVENTIONS.md",
              "conditions": results, "comparisons": comparisons,
              "examples": [
                  {"question": items[i]["question"],
                   "answers": items[i]["answers"][:3],
                   "facts": items[i]["facts"],
                   **{c: per_condition_preds[c][i] for c in conditions}}
                  for i in range(min(5, len(items)))]}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    print()
    print(f"{args.model}   {n} questions, MetaQA 3-hop, retrieval k={args.retrieval_k}")
    print("metrics: docs/EVAL_CONVENTIONS.md")
    print("=" * 82)
    print(f"{'condition':<44}{'Hits@1':>9}{'95% CI':>16}{'Full':>9}")
    print("-" * 82)
    for c in conditions:
        r = results[c]
        ci = f"{r['hits_at_1_ci'][0]:.3f}-{r['hits_at_1_ci'][1]:.3f}"
        print(f"{label[c]:<44}{r['hits_at_1']:>9.3f}{ci:>16}{r['full']:>9.3f}")
    print("=" * 82)
    print()
    print(f"Against '{baseline}' -- McNemar, Holm-Bonferroni corrected")
    print("-" * 82)
    print(f"{'condition':<44}{'change':>9}{'gained':>8}{'lost':>7}{'p':>10}")
    for c in conditions:
        if c == "closed":
            continue
        cmp = comparisons[label[c]]
        d = results[c]["hits_at_1"] - results["closed"]["hits_at_1"]
        print(f"{label[c]:<44}{d:>+9.3f}{cmp['gained']:>8}{cmp['lost']:>7}"
              f"{cmp['p_value_holm']:>10.2e}")
    print()
    print("diagnostic -- answer log-probability (higher is better, not a headline)")
    for c in conditions:
        print(f"  {label[c]:<44}{results[c]['answer_logprob']:>8.2f}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
