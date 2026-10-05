#!/usr/bin/env python
"""
The trial: does a small local model + TAHI beat a frontier model alone?

Three arms, same questions, same graph:

    A  frontier          Claude Opus 5, parametric memory only
    B  local             Qwen2.5-1.5B, parametric memory only
    C  local + TAHI      Qwen2.5-1.5B, answering from a graph lookup

Arm C is non-circular by construction. TAHI resolves the SUBJECT from the
question text and queries the graph for that subject's relation. It never sees
the gold set, and it can fail -- if the subject does not resolve to a node, C
returns nothing and is scored as such. That failure mode is the point: it is
what makes this a test rather than a demonstration.

Scoring is deliberately incomplete:

    CERTAIN_CORRECT    exact match to a curated graph edge
    MANUAL_CURATION    everything else

Nothing is auto-marked wrong. A model answer that does not match may still be
true -- the graph is incomplete, and we have no standing to call it false.
Only a human decides that, from `TRIAL_REVIEW.csv`.

Relations are restricted to `CbG` (compound binds gene) and `DaG` (disease
associates gene): published, literature-derived, stable ground truth. LINCS
assay relations are excluded because their edge sets depend on cell line, dose,
timepoint, and significance threshold -- there is no stable fact to score
against, so scoring anything against them would be dishonest.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.run_coverage import load, norm, parse_items  # noqa: E402

# Only relations with stable, published ground truth.
TRIAL_RELATIONS = {
    "CbG": ("What genes does the compound {s} bind?", "binds"),
    "DaG": ("What genes are associated with the disease {s}?", "associates"),
}

SYSTEM = ("Answer with gene symbols separated by commas, nothing else. "
          "If you do not know, answer exactly: I don't know")


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

    def ask(self, q, system=SYSTEM):
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": q}]
        text = self.tok.apply_chat_template(msgs, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=self.max_new_tokens,
                                      do_sample=False,
                                      pad_token_id=self.tok.pad_token_id)
        return self.tok.decode(out[0][ids["input_ids"].shape[1]:],
                               skip_special_tokens=True).strip()


class Tahi:
    """Graph lookup driven by the question, never by the answer key.

    Resolution is by exact normalised name, which is how a real integration
    against a customer's own store would work: the query names an entity, the
    store either has it or does not.
    """

    def __init__(self, id_to_name, by_subject):
        self.id_to_name = id_to_name
        self.by_subject = by_subject
        self.name_to_id = defaultdict(list)
        for nid, name in id_to_name.items():
            self.name_to_id[norm(name)].append(nid)

    def lookup(self, subject_name: str, metaedge: str):
        """Return (facts, resolved_node_id_or_None)."""
        ids = self.name_to_id.get(norm(subject_name), [])
        for nid in ids:
            targets = self.by_subject.get((nid, metaedge))
            if targets:
                return sorted({self.id_to_name[t] for t in targets
                               if t in self.id_to_name}), nid
        return [], (ids[0] if ids else None)


def certain_hits(said: list[str], gold: list[str]) -> list[str]:
    """Only exact normalised matches. Everything else is left for a human."""
    gold_norm = {norm(g): g for g in gold}
    out = []
    for item in said:
        k = norm(item)
        if k in gold_norm and gold_norm[k] not in out:
            out.append(gold_norm[k])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default="data/hetionet/nodes.tsv")
    ap.add_argument("--edges", default="data/hetionet/edges.sif.gz")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--min-edges", type=int, default=3)
    ap.add_argument("--max-edges", type=int, default=25)
    ap.add_argument("--max-new-tokens", type=int, default=200)
    ap.add_argument("--seed", type=int, default=21)
    ap.add_argument("--frontier-answers", default=None,
                    help="JSON of Opus answers keyed by qid. Omit on the first "
                         "pass to emit questions only.")
    ap.add_argument("--out-dir", default="benchmarks/results/tahi_trial")
    args = ap.parse_args()

    id_to_name, by_subject = load(Path(args.nodes), Path(args.edges),
                                  set(TRIAL_RELATIONS))
    eligible = [(s, m) for (s, m), t in by_subject.items()
                if args.min_edges <= len(t) <= args.max_edges and s in id_to_name]
    rng = random.Random(args.seed)
    rng.shuffle(eligible)

    per_rel = max(1, args.n // len(TRIAL_RELATIONS))
    counts: dict[str, int] = defaultdict(int)
    chosen = []
    for s, m in eligible:
        if len(chosen) >= args.n:
            break
        if counts[m] >= per_rel:
            continue
        counts[m] += 1
        chosen.append((s, m))

    questions = []
    for i, (sid, me) in enumerate(chosen):
        template, relation = TRIAL_RELATIONS[me]
        questions.append({
            "qid": f"t{i:03d}", "subject_id": sid, "subject": id_to_name[sid],
            "metaedge": me, "relation": relation,
            "question": template.format(s=id_to_name[sid]),
        })

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "questions.json").write_text(json.dumps(questions, indent=2),
                                            encoding="utf-8")

    if not args.frontier_answers:
        print(f"# {len(questions)} questions (seed {args.seed}). "
              "Answers NOT shown.\n")
        for q in questions:
            print(f"{q['qid']}  [{q['metaedge']}]  {q['question']}")
        print(f"\nwrote {out_dir/'questions.json'}")
        print("Answer these, save as JSON {qid: answer}, then rerun with "
              "--frontier-answers.")
        return 0

    frontier = json.loads(Path(args.frontier_answers).read_text(encoding="utf-8"))
    frontier = frontier.get("answers", frontier)

    print(f"Loading {args.model} ...", flush=True)
    llm = LocalLLM(args.model, args.device, args.max_new_tokens)
    tahi = Tahi(id_to_name, by_subject)

    rows = []
    for i, q in enumerate(questions):
        print(f"  {i+1}/{len(questions)}", flush=True)
        gold = sorted({id_to_name[t] for t in
                       by_subject[(q["subject_id"], q["metaedge"])]
                       if t in id_to_name})

        # ARM A -- frontier, parametric only
        a_raw = frontier.get(q["qid"], "")
        a_said = [] if "don't know" in a_raw.lower() else parse_items(a_raw)

        # ARM B -- local, parametric only
        b_raw = llm.ask(q["question"])
        b_said = [] if "don't know" in b_raw.lower() else parse_items(b_raw)

        # ARM C -- local + TAHI. Subject resolved from the question text only.
        facts, resolved = tahi.lookup(q["subject"], q["metaedge"])
        if facts:
            grounded = (
                f"{q['question']}\n\n"
                f"Knowledge base entry for {q['subject']} "
                f"({q['relation']}): {', '.join(facts)}\n\n"
                "Answer using only the knowledge base entry above."
            )
            c_raw = llm.ask(grounded)
        else:
            c_raw = "I don't know"
        c_said = [] if "don't know" in c_raw.lower() else parse_items(c_raw)

        rec = {**q, "gold": gold, "n_gold": len(gold),
               "tahi_resolved": resolved, "tahi_facts": facts,
               "A_frontier_raw": a_raw, "B_local_raw": b_raw, "C_tahi_raw": c_raw}
        for arm, said in (("A", a_said), ("B", b_said), ("C", c_said)):
            hits = certain_hits(said, gold)
            rec[f"{arm}_said"] = said
            rec[f"{arm}_certain_correct"] = hits
            rec[f"{arm}_n_correct"] = len(hits)
            rec[f"{arm}_manual"] = [s for s in said
                                    if norm(s) not in {norm(h) for h in hits}]
        rows.append(rec)

    tot_gold = sum(r["n_gold"] for r in rows)
    summary = {}
    for arm, label in (("A", "frontier (Opus)"), ("B", "local (Qwen 1.5B)"),
                       ("C", "local + TAHI")):
        c = sum(r[f"{arm}_n_correct"] for r in rows)
        s = sum(len(r[f"{arm}_said"]) for r in rows)
        m = sum(len(r[f"{arm}_manual"]) for r in rows)
        z = sum(1 for r in rows if r[f"{arm}_n_correct"] == 0)
        summary[arm] = {"label": label, "certain_correct": c, "stated": s,
                        "needs_manual": m, "zero_subjects": z,
                        "coverage": c / tot_gold if tot_gold else 0.0}

    review = out_dir / "TRIAL_REVIEW.csv"
    with open(review, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "subject", "relation", "n_graph_facts", "graph_facts",
                    "A_frontier_answer", "A_certain_correct", "A_manual",
                    "B_local_answer", "B_certain_correct", "B_manual",
                    "C_tahi_answer", "C_certain_correct", "C_manual",
                    "tahi_resolved_subject", "YOUR_VERDICT", "NOTES"])
        for r in rows:
            w.writerow([
                r["qid"], r["subject"], r["relation"], r["n_gold"],
                "; ".join(r["gold"]),
                r["A_frontier_raw"][:400], "; ".join(r["A_certain_correct"]),
                "; ".join(r["A_manual"][:20]),
                r["B_local_raw"][:400].replace("\n", " "),
                "; ".join(r["B_certain_correct"]), "; ".join(r["B_manual"][:20]),
                r["C_tahi_raw"][:400].replace("\n", " "),
                "; ".join(r["C_certain_correct"]), "; ".join(r["C_manual"][:20]),
                r["tahi_resolved"] or "NOT RESOLVED", "", "",
            ])

    (out_dir / "trial.json").write_text(json.dumps(
        {"model": args.model, "n": len(rows), "seed": args.seed,
         "total_graph_facts": tot_gold, "summary": summary, "rows": rows},
        indent=2), encoding="utf-8")

    print()
    print("=" * 68)
    print(f"TAHI TRIAL — {len(rows)} questions, {tot_gold} graph facts")
    print("=" * 68)
    print(f"  {'arm':22s} {'certain':>8s} {'stated':>7s} {'manual':>7s} "
          f"{'zero':>5s} {'coverage':>9s}")
    for arm in ("A", "B", "C"):
        s = summary[arm]
        print(f"  {s['label']:22s} {s['certain_correct']:8d} {s['stated']:7d} "
              f"{s['needs_manual']:7d} {s['zero_subjects']:5d} "
              f"{s['coverage']:8.1%}")
    print()
    print("  'certain' = exact match to a curated edge. 'manual' = everything")
    print("  else, NOT scored wrong -- a human decides, in:")
    print(f"    {review}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
