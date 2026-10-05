#!/usr/bin/env python
"""
Four arms, same questions: does constraining the decoder to graph entities work?

    A  frontier            Claude Opus 5, parametric memory only
    B  local               Qwen2.5-1.5B, parametric memory only
    C  local + prompt      graph facts pasted into the prompt   (this is RAG)
    D  local + CONSTRAINED graph masks the sampler               (the mechanism)

C and D receive identical facts from an identical lookup. The ONLY difference is
where the graph acts: in the prompt, or in the token loop. That isolates the
thing being claimed.

The readout that matters is `intervention_rate` on arm D -- the share of decode
steps where the unconstrained model wanted a token the graph forbade. If that is
near zero, the constraint never bound and D's score says nothing about
constrained decoding.

Subjects are resolved by character-trigram matching, not exact string equality,
so the lookup survives the messy-query problem measured in
`scripts/probe_linker.py` (95.8% correct on degraded names).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tahi.validate.constrained import generate_constrained  # noqa: E402
from scripts.run_coverage import load, norm, parse_items  # noqa: E402

TRIAL_RELATIONS = {
    "CbG": ("What genes does the compound {s} bind?", "binds"),
    "DaG": ("What genes are associated with the disease {s}?", "associates"),
}
SYSTEM = ("Answer with gene symbols separated by commas, nothing else. "
          "If you do not know, answer exactly: I don't know")

# Shared verbatim by arms C and E. The C-vs-E delta is only attributable to the
# sampler mask if every other input byte is identical.
GROUNDED_INSTRUCTION = "List every gene from the knowledge base above."


def trigrams(s: str) -> set[str]:
    s = f"  {re.sub(r'[^a-z0-9]+', '', s.lower())}  "
    return {s[i:i + 3] for i in range(len(s) - 2)}


class TrigramLinker:
    """Character-trigram nearest match. Beats embeddings on surface forms.

    Kind filtering is not optional. Hetionet contains "dental caries" as BOTH a
    Disease and a Side Effect; without it the linker matched the Side Effect
    node at score 1.0, which has no disease-gene edges, and the question
    silently returned nothing.
    """

    def __init__(self, id_to_name, kinds=None):
        self.id_to_name = id_to_name
        self.kinds = kinds or {}
        self.grams = {n: trigrams(v) for n, v in id_to_name.items()}
        self.index = defaultdict(set)
        for nid, g in self.grams.items():
            for t in g:
                self.index[t].add(nid)

    def resolve(self, q: str, min_jaccard: float = 0.45, kind: str | None = None):
        gq = trigrams(q)
        cand = defaultdict(int)
        for t in gq:
            for nid in self.index.get(t, ()):
                cand[nid] += 1
        best, bs = None, 0.0
        for nid, c in cand.items():
            if kind is not None and self.kinds.get(nid) != kind:
                continue
            j = c / len(gq | self.grams[nid])
            if j > bs:
                best, bs = nid, j
        return (best, bs) if bs >= min_jaccard else (None, bs)


def certain_hits(said, gold):
    gn = {norm(g): g for g in gold}
    out = []
    for s in said:
        k = norm(s)
        if k in gn and gn[k] not in out:
            out.append(gn[k])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default="data/hetionet/nodes.tsv")
    ap.add_argument("--edges", default="data/hetionet/edges.sif.gz")
    ap.add_argument("--questions",
                    default="benchmarks/results/tahi_trial/questions.json")
    ap.add_argument("--frontier-answers",
                    default="benchmarks/results/tahi_trial/frontier_answers.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-new-tokens", type=int, default=200)
    ap.add_argument("--out-dir", default="benchmarks/results/constrained_trial")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    frontier = json.loads(Path(args.frontier_answers).read_text(encoding="utf-8"))
    frontier = frontier.get("answers", frontier)

    id_to_name, by_subject = load(Path(args.nodes), Path(args.edges),
                                  set(TRIAL_RELATIONS))
    node_kinds = {}
    with open(args.nodes, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            node_kinds[row["id"]] = row["kind"]
    linker = TrigramLinker(id_to_name, kinds=node_kinds)

    print(f"Loading {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.float32).to(args.device).eval()

    def ask(q, system=SYSTEM):
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": q}]
        text = tok.apply_chat_template(msgs, tokenize=False,
                                       add_generation_prompt=True)
        ids = tok(text, return_tensors="pt").to(args.device)
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=args.max_new_tokens,
                                 do_sample=False, pad_token_id=tok.pad_token_id)
        return tok.decode(out[0][ids["input_ids"].shape[1]:],
                          skip_special_tokens=True).strip()

    rows = []
    for i, q in enumerate(questions):
        print(f"  {i+1}/{len(questions)}", flush=True)
        gold = sorted({id_to_name[t] for t in
                       by_subject[(q["subject_id"], q["metaedge"])]
                       if t in id_to_name})

        want_kind = "Compound" if q["metaedge"] == "CbG" else "Disease"
        nid, score = linker.resolve(q["subject"], kind=want_kind)
        facts = sorted({id_to_name[t] for t in
                        by_subject.get((nid, q["metaedge"]), [])
                        if t in id_to_name}) if nid else []

        a_raw = frontier.get(q["qid"], "")
        a_said = [] if "don't know" in a_raw.lower() else parse_items(a_raw)
        b_raw = ask(q["question"])
        b_said = [] if "don't know" in b_raw.lower() else parse_items(b_raw)

        # C -- facts in the prompt. This is RAG.
        # The instruction MUST be byte-identical to arm E's, or the C-vs-E delta
        # measures prompt wording rather than the sampler mask. An earlier
        # version used "Answer using only the knowledge base above" here and
        # "List every gene from the knowledge base above" in E, which silently
        # confounded the comparison the trial exists to make.
        if facts:
            c_raw = ask(f"{q['question']}\n\nKnowledge base: {', '.join(facts)}\n\n"
                        f"{GROUNDED_INSTRUCTION}")
        else:
            c_raw = "I don't know"
        c_said = [] if "don't know" in c_raw.lower() else parse_items(c_raw)

        # D -- graph masks the sampler. Same facts, no facts in the prompt.
        stats = {}
        if facts:
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": q["question"]}]
            prompt = tok.apply_chat_template(msgs, tokenize=False,
                                             add_generation_prompt=True)
            d_raw, stats = generate_constrained(
                model, tok, prompt, facts, device=args.device,
                max_new_tokens=args.max_new_tokens)
        else:
            d_raw = "I don't know"
        d_said = [] if "don't know" in d_raw.lower() else parse_items(d_raw)

        # E -- BOTH: facts in the prompt (so the model knows what exists) AND
        # the sampler constrained (so it cannot emit anything else). C supplies
        # recall, D supplies the precision guarantee.
        e_stats = {}
        if facts:
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content":
                     f"{q['question']}\n\nKnowledge base: {', '.join(facts)}\n\n"
                     f"{GROUNDED_INSTRUCTION}"}]
            prompt = tok.apply_chat_template(msgs, tokenize=False,
                                             add_generation_prompt=True)
            e_raw, e_stats = generate_constrained(
                model, tok, prompt, facts, device=args.device,
                max_new_tokens=args.max_new_tokens)
        else:
            e_raw = "I don't know"
        e_said = [] if "don't know" in e_raw.lower() else parse_items(e_raw)

        # F -- GATELESS and O(1). Prompt holds NO facts, exactly like D, but the
        # decoder may not emit EOS until it has covered the graph's answer set.
        # D's only weakness was that it stopped early while blind to how many
        # facts existed; "how many" is a decoder rule, not something a model has
        # to be taught. No adapters, no alpha, no context cost.
        f_stats = {}
        if facts:
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": q["question"]}]
            prompt = tok.apply_chat_template(msgs, tokenize=False,
                                             add_generation_prompt=True)
            f_raw, f_stats = generate_constrained(
                model, tok, prompt, facts, device=args.device,
                max_new_tokens=max(args.max_new_tokens, 12 * len(facts)),
                min_items=len(facts))
        else:
            f_raw = "I don't know"
        f_said = [] if "don't know" in f_raw.lower() else parse_items(f_raw)

        rec = {**q, "gold": gold, "n_gold": len(gold),
               "linked_node": nid, "link_score": round(score, 3),
               "facts_from_graph": facts, "constrain_stats": stats,
               "constrain_stats_e": e_stats, "constrain_stats_f": f_stats,
               "A_raw": a_raw, "B_raw": b_raw, "C_raw": c_raw,
               "D_raw": d_raw, "E_raw": e_raw, "F_raw": f_raw}
        for arm, said in (("A", a_said), ("B", b_said), ("C", c_said),
                          ("D", d_said), ("E", e_said), ("F", f_said)):
            hits = certain_hits(said, gold)
            rec[f"{arm}_said"] = said
            rec[f"{arm}_correct"] = hits
            rec[f"{arm}_n"] = len(hits)
            rec[f"{arm}_manual"] = [s for s in said
                                    if norm(s) not in {norm(h) for h in hits}]
        rows.append(rec)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tot = sum(r["n_gold"] for r in rows)
    labels = {"A": "frontier (Opus)", "B": "local 1.5B",
              "C": "local + prompt (RAG)", "D": "local + CONSTRAINED",
              "E": "local + prompt + CONSTRAINED",
              "F": "local + CONSTRAINED (gateless, O(1))"}
    summary = {}
    for arm, label in labels.items():
        c = sum(r[f"{arm}_n"] for r in rows)
        summary[arm] = {
            "label": label, "correct": c, "coverage": c / tot if tot else 0.0,
            "stated": sum(len(r[f"{arm}_said"]) for r in rows),
            "manual": sum(len(r[f"{arm}_manual"]) for r in rows),
            "zero": sum(1 for r in rows if r[f"{arm}_n"] == 0),
        }
    irates = [r["constrain_stats"].get("intervention_rate", 0.0)
              for r in rows if r["constrain_stats"]]
    mean_ir = sum(irates) / len(irates) if irates else 0.0

    with open(out_dir / "REVIEW.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "subject", "n_graph_facts", "graph_facts",
                    "A_frontier", "A_correct", "B_local", "B_correct",
                    "C_prompt", "C_correct", "D_constrained", "D_correct",
                    "E_both", "E_correct", "F_gateless", "F_correct",
                    "D_intervention_rate",
                    "YOUR_VERDICT", "NOTES"])
        for r in rows:
            w.writerow([r["qid"], r["subject"], r["n_gold"], "; ".join(r["gold"]),
                        r["A_raw"][:300], len(r["A_correct"]),
                        r["B_raw"][:300].replace("\n", " "), len(r["B_correct"]),
                        r["C_raw"][:300].replace("\n", " "), len(r["C_correct"]),
                        r["D_raw"][:300].replace("\n", " "), len(r["D_correct"]),
                        r["E_raw"][:300].replace("\n", " "), len(r["E_correct"]),
                        r["F_raw"][:300].replace("\n", " "), len(r["F_correct"]),
                        round(r["constrain_stats"].get("intervention_rate", 0), 3),
                        "", ""])
    (out_dir / "trial.json").write_text(json.dumps(
        {"model": args.model, "n": len(rows), "total_graph_facts": tot,
         "summary": summary, "mean_intervention_rate": mean_ir, "rows": rows},
        indent=2), encoding="utf-8")

    print()
    print("=" * 70)
    print(f"CONSTRAINED DECODING TRIAL — {len(rows)} questions, {tot} graph facts")
    print("=" * 70)
    print(f"  {'arm':24s} {'correct':>8s} {'stated':>7s} {'manual':>7s} "
          f"{'zero':>5s} {'coverage':>9s}")
    for arm in "ABCDEF":
        s = summary[arm]
        print(f"  {s['label']:24s} {s['correct']:8d} {s['stated']:7d} "
              f"{s['manual']:7d} {s['zero']:5d} {s['coverage']:8.1%}")
    print()
    print(f"  mean intervention rate (arm D): {mean_ir:.1%}")
    print("    share of decode steps where the model wanted a token the graph")
    print("    forbade. Near zero => the constraint never bound.")
    print(f"\n  review: {out_dir/'REVIEW.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
