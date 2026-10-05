#!/usr/bin/env python3
"""
Post-generation graph correction on MetaQA 3-hop, using src/tahi.

    prompt -> LLM -> answer
      -> derive a 3-relation chain from the question
      -> tahi.graph.metaqa_graph.MetaQAGraph.walk() for the supported set
      -> diff the answer against it
      -> hand back only what is provably wrong, ask again
      -> repeat until stable or max rounds

Arms, same questions, same model, one run:
    plain    no retrieval at all -- the model answers from what it knows
    rag      dense retrieval over the KB written out as text, answer once
    tahi     rag, then the graph checks the answer and corrects it

Two things are scored for every arm:
    right          the answer set matches the gold set exactly
    made-up names  entities named that appear nowhere in the knowledge base.
                   This is the same measurement the Legend test reports, so the
                   two are directly comparable.

Chain derivation, both measured:
    few-shot     schema + 3 worked examples
    --enumerate  traverse all 9^3 chains with no LLM, model picks a result set

Scoring is exact set equality against the gold entity list. No judge.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metaqa_verify import BGE_QUERY, CHAIN, norm, parse_entities, score  # noqa: E402

from tahi.graph.entity_linker import EntityLinker  # noqa: E402
from tahi.graph.metaqa_graph import MetaQAGraph  # noqa: E402

RELS = ["starred_actors", "directed_by", "written_by", "has_genre", "has_tags",
        "in_language", "release_year", "has_imdb_rating", "has_imdb_votes"]

ASK = """Answer the question. Reply with ONLY a comma-separated list of entity names.
If you cannot answer, reply exactly: INSUFFICIENT

{context}Question: {q}

Answer:"""

CORRECT = """Question: {q}
Your answer: {ans}

A knowledge graph was checked. Findings:
{findings}

Give a corrected answer. Reply with ONLY a comma-separated list of entity names,
or exactly INSUFFICIENT.

Answer:"""

PICK = """Question: {q}

Each option below is the result of following a different path through a knowledge
graph from the entity in the question. Pick the ONE whose results answer the question.

{opts}

Reply with ONLY the option number."""


def chain_endpoints(g: MetaQAGraph, seeds, chain, cap=100000) -> list[str]:
    """Endpoints of paths whose relation sequence is exactly `chain`.

    MetaQAGraph.walk filters by relation set; the ordered chain is enforced by
    comparing each path's relation sequence.
    """
    want = tuple(chain)
    seedset = set(seeds)
    out, seen = [], set()
    for s in seeds:
        for p in g.walk(s, len(chain), allowed_relations=set(chain)):
            if p.hops != len(chain) or tuple(r for r, _n, _b in p.steps) != want:
                continue
            if p.endpoint in seen or p.endpoint in seedset:
                continue
            seen.add(p.endpoint)
            out.append(p.endpoint)
    return sorted(out)[:cap]


def lm_entities(kb_path: str) -> set[str]:
    """Every entity name appearing in the knowledge base, either side of a triple."""
    out: set[str] = set()
    for line in Path(kb_path).read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            out.add(parts[0].strip())
            out.add(parts[2].strip())
    return out


def diff(ans: set[str], supported: set[str], *, blind: bool = False) -> str | None:
    """What is provably wrong with `ans`, given the graph supports `supported`.

    `blind=True` withholds the names of the entities that were missed, stating
    only how many there are. This exists to answer a specific criticism: when
    the traversal is correct, `supported` IS the gold answer set, so naming the
    omissions hands the answer key to the model in plain text and the loop
    measures copying rather than anything else. Running both ways separates
    "the graph found the answer" from "the model was told the answer".
    """
    bad = sorted(ans - supported)
    miss = sorted(supported - ans)
    if not bad and not miss:
        return None
    out = []
    if bad:
        out.append(f"- NOT in the graph, remove: {', '.join(bad)}")
    if miss:
        if blind:
            out.append(f"- the graph supports {len(miss)} entities you did not "
                       f"name. Their names are not given to you.")
        else:
            out.append(f"- IN the graph, you omitted: {', '.join(miss)}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Post-generation graph correction, src/tahi")
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--questions", default="data/metaqa/qa_3hop_test.json")
    ap.add_argument("--out", default="data/metaqa/results/loop_tahi_results.json")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--encoder", default="BAAI/bge-large-en-v1.5")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--enumerate", action="store_true")
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--blind-diff", action="store_true",
                    help="do not name the omitted entities in the correction, "
                         "only how many there are. Separates the graph finding "
                         "the answer from the model being handed it.")
    ap.add_argument("--given-entity", action="store_true",
                    help="take the starting entity from the dataset instead of "
                         "finding it in the question. Off by default: handing it "
                         "over is not something a deployed system can do, and it "
                         "gave TAHI help the retrieval baseline never had.")
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("OPENAI_API_KEY not set.", file=sys.stderr)
        return 2
    from openai import OpenAI
    client = OpenAI(api_key=key, timeout=120.0, max_retries=3)
    calls = {"n": 0}

    def llm(prompt: str) -> str:
        try:
            r = client.chat.completions.create(
                model=args.model, temperature=0,
                messages=[{"role": "user", "content": prompt}])
            calls["n"] += 1
            return (r.choices[0].message.content or "").strip()
        except Exception as e:  # noqa: BLE001
            print(f"  LLM ERROR {type(e).__name__}", file=sys.stderr)
            return ""

    print("loading kb via tahi.graph.metaqa_graph.MetaQAGraph ...", flush=True)
    g = MetaQAGraph(args.kb)
    print(f"  {len(list(g.entities))} entities, {len(g.relations)} relations", flush=True)

    # RAG corpus: the same KB as sentences, one doc per subject entity.
    facts: dict[str, list[str]] = {}
    for line in Path(args.kb).read_text(encoding="utf-8").splitlines():
        p = line.split("|")
        if len(p) == 3:
            s, r, o = (x.strip() for x in p)
            facts.setdefault(s, []).append(f"{s} {r.replace('_', ' ')} {o}.")
    docs = [" ".join(facts[d]) for d in sorted(facts)]

    # every entity the knowledge base knows about, for the made-up-name count
    kb_entities = lm_entities(args.kb)
    entity_set = {norm(e) for e in kb_entities}
    print(f"  {len(entity_set)} distinct entities in the knowledge base", flush=True)

    linker = EntityLinker(kb_entities)
    print(f"  entity linker: {len(linker)} surface forms"
          f"{'  [DISABLED, using dataset q_entity]' if args.given_entity else ''}",
          flush=True)

    def start_entities(q) -> list[str]:
        """Where the traversal begins. Found in the question unless told otherwise."""
        if args.given_entity:
            return q["q_entity"]
        return linker.link(q["question"])

    from sentence_transformers import SentenceTransformer
    print(f"embedding {len(docs)} docs ...", flush=True)
    st = SentenceTransformer(args.encoder)
    demb = st.encode(docs, normalize_embeddings=True, batch_size=256,
                     show_progress_bar=False).astype(np.float32)

    qs = json.loads(Path(args.questions).read_text())
    qs = random.Random(args.seed).sample(qs, min(args.n, len(qs)))
    qemb = st.encode([BGE_QUERY + q["question"] for q in qs],
                     normalize_embeddings=True, batch_size=64,
                     show_progress_bar=False).astype(np.float32)

    all_chains = list(itertools.product(RELS, repeat=3)) if args.enumerate else None

    def supported_set(q) -> set[str]:
        seeds = start_entities(q)
        if not seeds:
            return set()                      # linker found nothing to start from
        if args.enumerate:
            cands = []
            for ch in all_chains:
                res = chain_endpoints(g, seeds, list(ch))
                if res:
                    cands.append((ch, res))
            cands.sort(key=lambda x: len(x[1]))
            cands = cands[:40]
            if not cands:
                return set()
            opts = "\n".join(
                f"{i+1}. {' -> '.join(ch)} ({len(r)}): {', '.join(r[:8])}"
                f"{' ...' if len(r) > 8 else ''}" for i, (ch, r) in enumerate(cands))
            txt = llm(PICK.format(q=q["question"], opts=opts))
            digits = "".join(c for c in txt if c.isdigit())[:2]
            try:
                pick = int(digits) - 1
            except ValueError:
                return set()
            return {norm(x) for x in cands[pick][1]} if 0 <= pick < len(cands) else set()
        chain = [c.strip().lower() for c in llm(CHAIN.format(q=q["question"])).split(",")][:3]
        chain = [c for c in chain if c in RELS]
        if len(chain) != 3:
            return set()
        return {norm(x) for x in chain_endpoints(g, seeds, chain)}

    def run(q_qe):
        q, qe = q_qe
        gold = {norm(a) for a in q["answers"]}

        # arm 0: no retrieval at all
        plain = parse_entities(llm(ASK.format(context="", q=q["question"])))

        top = np.argsort(demb @ qe)[::-1][: args.top_k]
        ctx = "Context:\n" + "\n".join(docs[j][:600] for j in top) + "\n\n"
        ans = parse_entities(llm(ASK.format(context=ctx, q=q["question"])))
        rag_ans = set(ans)

        sup = supported_set(q)
        history, round1 = [], None
        if sup:
            for rnd in range(args.max_rounds):
                d = diff(ans, sup, blind=args.blind_diff)
                if d is None:
                    break
                new = parse_entities(llm(CORRECT.format(
                    q=q["question"], ans=", ".join(sorted(ans)) or "(none)", findings=d)))
                history.append({"round": rnd + 1, "findings": d, "answer": sorted(new)})
                if rnd == 0:
                    round1 = set(new)
                if new == ans:
                    break
                ans = new
        if round1 is None:
            round1 = set(rag_ans)

        def invented(s):
            return sorted(x for x in s if x not in entity_set)

        linked = start_entities(q)

        return {"id": q["id"], "question": q["question"], "gold": sorted(gold),
                "n_supported": len(sup), "rounds": len(history),
                "linked_entity": linked, "gold_entity": q["q_entity"],
                "link_ok": {x.lower() for x in q["q_entity"]} <= {x.lower() for x in linked},
                "plain": sorted(plain), "plain_status": score(plain, gold),
                "plain_invented": invented(plain),
                "rag": sorted(rag_ans), "rag_status": score(rag_ans, gold),
                "rag_invented": invented(rag_ans),
                "round1": sorted(round1), "round1_status": score(round1, gold),
                "loop": sorted(ans), "loop_status": score(ans, gold),
                "loop_invented": invented(ans),
                "history": history}

    started = time.perf_counter()
    rows = [None] * len(qs)
    with ThreadPoolExecutor(args.concurrency) as ex:
        futs = {ex.submit(run, (q, qe)): i for i, (q, qe) in enumerate(zip(qs, qemb, strict=False))}
        done = 0
        for fut in as_completed(futs):
            rows[futs[fut]] = fut.result()
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(qs)}", flush=True)
    rows = [r for r in rows if r]

    def acc(k):
        return sum(1 for r in rows if r[k] == "RIGHT") / len(rows)

    n = len(rows)
    print(f"\n{'='*62}\nMETAQA 3-HOP POST-GENERATION LOOP — src/tahi  n={n}  seed={args.seed}"
          f"{'  [enumerate]' if args.enumerate else '  [few-shot]'}\n{'='*62}")
    def made_up(key):
        tot = sum(len(r[key]) for r in rows)
        bad = sum(len(r[key + "_invented"]) for r in rows)
        return bad / tot if tot else 0.0

    link_ok = sum(r["link_ok"] for r in rows) / len(rows)
    print(f"\n  starting entity found in the question: {link_ok:.3f}"
          f"{'   [linker bypassed]' if args.given_entity else ''}")
    print(f"{'':32s}{'plain LLM':>11s}{'RAG':>9s}{'TAHI':>9s}")
    print(f"  {'answered exactly right':30s}{acc('plain_status'):>11.3f}"
          f"{acc('rag_status'):>9.3f}{acc('loop_status'):>9.3f}")
    print(f"  {'made-up names written down':30s}{made_up('plain'):>11.3f}"
          f"{made_up('rag'):>9.3f}{made_up('loop'):>9.3f}")
    print(f"\n  TAHI, one pass only         {acc('round1_status'):.3f}")
    for label, k in (("w/o TAHI -> one pass", "round1_status"),
                     ("w/o TAHI -> repeat to stable", "loop_status")):
        t = Counter((r["rag_status"], r[k]) for r in rows)
        fixed = t[("WRONG", "RIGHT")] + t[("MISSING", "RIGHT")]
        broke = t[("RIGHT", "WRONG")] + t[("RIGHT", "MISSING")]
        print(f"\n  {label}:  fixed {fixed}  broken {broke}  net {fixed-broke:+d}")
        nn = fixed + broke
        if nn:
            from math import comb
            kk = min(fixed, broke)
            p = min(1.0, 2 * sum(comb(nn, j) for j in range(kk + 1)) / 2 ** nn)
            print(f"    McNemar exact p = {p:.4f}")
    print(f"\n  rounds used: {dict(sorted(Counter(r['rounds'] for r in rows).items()))}")
    print(f"  llm calls {calls['n']}   wall clock {time.perf_counter()-started:.0f}s")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "seed": args.seed, "model": args.model,
        "implementation": "src/tahi -- MetaQAGraph.walk",
        "chain_source": "enumerate" if args.enumerate else "few_shot_examples",
        "accuracy": {"plain_llm": acc("plain_status"), "rag": acc("rag_status"),
                     "tahi_one_pass": acc("round1_status"), "tahi": acc("loop_status")},
        "made_up_name_rate": {"plain_llm": made_up("plain"), "rag": made_up("rag"),
                              "tahi": made_up("loop")},
        "entity_given": args.given_entity, "blind_diff": args.blind_diff,
        "entity_link_recall": link_ok,
        "llm_calls": calls["n"], "rows": rows}, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
