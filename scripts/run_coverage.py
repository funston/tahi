#!/usr/bin/env python
"""
Coverage: how much of what the graph knows does the model actually say?

Standard RAG evaluation asks whether what a model said is supported. This asks
the other question -- what did it leave out? A knowledge graph supplies the
denominator that an embedding index cannot: you can count edges, so you can
count omissions.

Per subject:

    ask     "List every gene that compound X binds."
    model   names some set M
    graph   holds the true set G

    coverage  = |M ∩ G| / |G|      how much of the graph's knowledge surfaced
    precision = |M ∩ G| / |M|      how much of what it said was real

Both are counts over a public curated graph. No judge model, no entailment
score, no learned metric, and no opinion from whoever writes this up.

Everything needed to check a row by hand is written into the report: the
question, the model's verbatim answer, the graph's full answer set, which items
matched, and the shell command that reproduces the graph's side independently.

Usage:
    python scripts/run_coverage.py --n 20
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Hetionet metaedge -> (plural question, relation phrase)
RELATIONS = {
    "CbG": ("List every gene that the compound {s} binds. "
            "Answer with gene symbols separated by commas, nothing else.",
            "binds"),
    "CdG": ("List every gene that the compound {s} downregulates. "
            "Answer with gene symbols separated by commas, nothing else.",
            "downregulates"),
    "CuG": ("List every gene that the compound {s} upregulates. "
            "Answer with gene symbols separated by commas, nothing else.",
            "upregulates"),
    "DaG": ("List every gene associated with the disease {s}. "
            "Answer with gene symbols separated by commas, nothing else.",
            "associates"),
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def load(nodes_tsv: Path, edges_gz: Path, keep: set[str]):
    id_to_name: dict[str, str] = {}
    with open(nodes_tsv, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            id_to_name[row["id"]] = row["name"]
    by_subject: dict[tuple[str, str], list[str]] = defaultdict(list)
    with gzip.open(edges_gz, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["metaedge"] in keep:
                by_subject[(row["source"], row["metaedge"])].append(row["target"])
    return id_to_name, by_subject


class LocalLLM:
    def __init__(self, model_name, device, max_new_tokens):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_name)
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, dtype=torch.float32).to(device).eval()
        self.device, self.max_new_tokens = device, max_new_tokens

    def ask(self, q):
        msgs = [{"role": "user", "content": q}]
        text = self.tok.apply_chat_template(msgs, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=self.max_new_tokens,
                                      do_sample=False,
                                      pad_token_id=self.tok.pad_token_id)
        return self.tok.decode(out[0][ids["input_ids"].shape[1]:],
                               skip_special_tokens=True).strip()


def classify(said: list[str], gold: list[str], *, near: float = 0.82):
    """Split answers into clearly-right, clearly-wrong, and needs-a-human.

    Exact normalised match is a HIT. Anything close enough to a gold symbol to
    be a plausible variant, abbreviation, or off-by-one is a NEAR and is
    surfaced for review rather than silently scored either way -- `SLC19A2` vs
    `SLC19A3` are different genes, but `IL-1B` vs `IL1B` are the same one, and
    only a human should decide which case is in front of them.

    NEAR items are counted as neither correct nor incorrect. They bound the
    error: true coverage lies between the HIT rate and (HIT + NEAR) rate.
    """
    from difflib import SequenceMatcher

    gold_norm = {norm(g): g for g in gold}
    hits: list[str] = []
    nears: list[tuple[str, str, float]] = []
    misses: list[str] = []

    for item in said:
        key = norm(item)
        if not key:
            continue
        if key in gold_norm:
            if gold_norm[key] not in hits:
                hits.append(gold_norm[key])
            continue
        best, ratio = None, 0.0
        for gk, gname in gold_norm.items():
            r = SequenceMatcher(None, key, gk).ratio()
            if r > ratio:
                best, ratio = gname, r
        if best is not None and ratio >= near:
            nears.append((item, best, round(ratio, 3)))
        else:
            misses.append(item)
    return hits, nears, misses


def parse_items(answer: str) -> list[str]:
    """Split a model answer into candidate entity names.

    Deliberately permissive -- splitting on punctuation and newlines. Being
    generous here can only INFLATE the model's apparent coverage, so it biases
    against the finding rather than toward it.
    """
    parts = re.split(r"[,\n;]+", answer)
    out = []
    for p in parts:
        p = re.sub(r"^\s*[-*\d.)\]]+\s*", "", p).strip()
        p = re.sub(r"\(.*?\)", "", p).strip()
        if p and len(p) < 60:
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default="data/hetionet/nodes.tsv")
    ap.add_argument("--edges", default="data/hetionet/edges.sif.gz")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--min-edges", type=int, default=5)
    ap.add_argument("--max-edges", type=int, default=60,
                    help="Cap so the task stays answerable in a short reply.")
    ap.add_argument("--max-new-tokens", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="benchmarks/results/COVERAGE_REPORT.md")
    args = ap.parse_args()

    print("Loading Hetionet ...", flush=True)
    id_to_name, by_subject = load(Path(args.nodes), Path(args.edges),
                                  set(RELATIONS))

    eligible = [(s, m) for (s, m), t in by_subject.items()
                if args.min_edges <= len(t) <= args.max_edges
                and s in id_to_name]
    rng = random.Random(args.seed)
    rng.shuffle(eligible)

    per_rel = max(1, args.n // len(RELATIONS))
    counts: dict[str, int] = defaultdict(int)
    chosen = []
    for s, m in eligible:
        if len(chosen) >= args.n:
            break
        if counts[m] >= per_rel:
            continue
        counts[m] += 1
        chosen.append((s, m))

    print(f"  {len(chosen)} subjects selected", flush=True)
    print(f"Loading {args.model} ...", flush=True)
    llm = LocalLLM(args.model, args.device, args.max_new_tokens)

    rows = []
    for i, (subject_id, metaedge) in enumerate(chosen):
        print(f"  {i + 1}/{len(chosen)}", flush=True)
        template, relation = RELATIONS[metaedge]
        subject = id_to_name[subject_id]
        gold_ids = by_subject[(subject_id, metaedge)]
        gold = sorted({id_to_name[g] for g in gold_ids if g in id_to_name})
        {norm(g): g for g in gold}

        question = template.format(s=subject)
        answer = llm.ask(question)
        said = parse_items(answer)

        matched, nears, spurious = classify(said, gold)

        missed = [g for g in gold if g not in matched]
        coverage = len(matched) / len(gold) if gold else 0.0
        precision = len(matched) / len(said) if said else 0.0

        rows.append({
            "subject_id": subject_id, "subject": subject,
            "metaedge": metaedge, "relation": relation,
            "question": question, "answer": answer,
            "said": said, "gold": gold, "matched": matched,
            "missed": missed, "spurious": spurious,
            "nears": nears,
            "n_said": len(said), "n_gold": len(gold),
            "n_matched": len(matched), "n_near": len(nears),
            "coverage": coverage, "precision": precision,
        })

    n = len(rows)
    tot_gold = sum(r["n_gold"] for r in rows)
    tot_said = sum(r["n_said"] for r in rows)
    tot_match = sum(r["n_matched"] for r in rows)
    micro_cov = tot_match / tot_gold if tot_gold else 0.0
    micro_prec = tot_match / tot_said if tot_said else 0.0
    zero_cov = sum(1 for r in rows if r["n_matched"] == 0)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    L = []
    L.append("# Coverage report — what the model omits\n")
    L.append(f"**Model:** `{args.model}`  ")
    L.append("**Graph:** Hetionet v1.0 (Himmelstein et al. 2017), used as-is  ")
    L.append(f"**Subjects:** {n}, sampled with seed {args.seed} from edges with "
             f"{args.min_edges}–{args.max_edges} targets\n")
    L.append("Every number below is a count over graph edges. No judge model, "
             "no entailment score, no learned metric.\n")
    L.append("## Headline\n")
    L.append("| Measure | Value |")
    L.append("| --- | ---: |")
    L.append(f"| Facts the graph holds | {tot_gold} |")
    L.append(f"| Facts the model stated | {tot_said} |")
    L.append(f"| Correct (in graph) | {tot_match} |")
    L.append(f"| **Coverage** (of graph knowledge surfaced) | **{micro_cov:.1%}** |")
    L.append(f"| **Precision** (of statements that were real) | **{micro_prec:.1%}** |")
    L.append(f"| Subjects with ZERO correct facts | {zero_cov}/{n} |")
    L.append("")
    L.append("## How to verify any row yourself\n")
    L.append("The graph side of every row is reproducible without this script "
             "and without trusting anything an LLM said:\n")
    L.append("```bash")
    L.append("# all true targets for one subject (substitute the subject id)")
    L.append("gunzip -c data/hetionet/edges.sif.gz \\")
    L.append("  | awk -F'\\t' '$1==\"Compound::DB00997\" && $2==\"CbG\"' \\")
    L.append("  | cut -f3 > ids.txt")
    L.append("# map those ids to names")
    L.append("grep -F -f ids.txt data/hetionet/nodes.tsv | cut -f1,2")
    L.append("```\n")
    L.append("## Rows\n")
    for r in rows:
        L.append(f"### {r['subject']} — {r['relation']} "
                 f"(`{r['subject_id']}`, `{r['metaedge']}`)\n")
        L.append(f"**Question:** {r['question']}\n")
        L.append("**Model answered verbatim:**\n")
        L.append("```")
        L.append(r["answer"][:1500] or "(empty)")
        L.append("```\n")
        L.append(f"- Graph holds **{r['n_gold']}** facts; model stated "
                 f"**{r['n_said']}**; **{r['n_matched']}** were correct.")
        L.append(f"- Coverage **{r['coverage']:.1%}**, precision "
                 f"**{r['precision']:.1%}**")
        L.append(f"- Correct: {', '.join(r['matched']) or '(none)'}")
        L.append(f"- Invented (not in graph): "
                 f"{', '.join(r['spurious'][:15]) or '(none)'}")
        L.append(f"- Missed: {', '.join(r['missed'][:25])}"
                 f"{' …' if len(r['missed']) > 25 else ''}")
        L.append("")
    out.write_text("\n".join(L), encoding="utf-8")

    # Manual review sheet. Three buckets so a human only has to adjudicate the
    # ambiguous middle: exact matches and unrelated strings need no judgement,
    # near-matches do. `SLC19A2` vs `SLC19A3` are different genes; `IL-1B` vs
    # `IL1B` are the same one, and only a person should decide which is which.
    review = out.parent / "MANUAL_REVIEW.csv"
    with open(review, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "subject", "relation", "n_graph_facts",
                    "CLEARLY_CORRECT", "NEEDS_YOUR_EYE", "CLEARLY_WRONG",
                    "graph_holds", "model_said_verbatim",
                    "coverage", "YOUR_VERDICT", "NOTES"])
        for i, r in enumerate(rows):
            w.writerow([
                f"r{i:03d}", r["subject"], r["relation"], r["n_gold"],
                "; ".join(r["matched"]),
                "; ".join(f"{s} ~ {g} ({x})" for s, g, x in r["nears"]),
                "; ".join(r["spurious"][:40]),
                "; ".join(r["gold"]),
                r["answer"][:900].replace("\n", " "),
                f"{r['coverage']:.1%}", "", "",
            ])

    tot_near = sum(r["n_near"] for r in rows)
    (out.parent / "coverage_run.json").write_text(
        json.dumps({"model": args.model, "n": n, "seed": args.seed,
                    "micro_coverage": micro_cov, "micro_precision": micro_prec,
                    "total_gold": tot_gold, "total_said": tot_said,
                    "total_matched": tot_match, "zero_coverage_subjects": zero_cov,
                    "rows": rows}, indent=2), encoding="utf-8")

    print()
    print("=" * 62)
    print("COVERAGE")
    print("=" * 62)
    print(f"  subjects                {n}")
    print(f"  graph facts             {tot_gold}")
    print(f"  model statements        {tot_said}")
    print(f"  correct                 {tot_match}")
    print(f"  COVERAGE                {micro_cov:.1%}")
    print(f"  PRECISION               {micro_prec:.1%}")
    print(f"  subjects with 0 correct {zero_cov}/{n}")
    print(f"  flagged NEEDS-YOUR-EYE  {tot_near}")
    print()
    print(f"  report:        {out}")
    print(f"  review sheet:  {review}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
