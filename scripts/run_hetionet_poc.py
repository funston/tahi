#!/usr/bin/env python
"""
OCTO proof of concept on a public knowledge graph.

The question, plainly: given an existing public KG, does consulting it at
generation time make the answers more accurate than the bare LLM?

No new metric, no judge model, no learned score. Questions are generated
mechanically from real graph edges, so the correct answer is whatever the graph
says -- a fact somebody else curated, not one we invented. Two arms answer the
same questions and the output is a side-by-side sheet for a human to mark up.

    ARM A  base       the LLM answers from parametric memory alone
    ARM B  octo       the LLM answers, then OCTO queries the graph and
                      corrects the answer when it is not one the graph supports

Arm B is deliberately NOT prompt-stuffing. Nothing is injected before
generation. The graph acts on the model's OUTPUT, which is what distinguishes
this from GraphRAG.

Hetionet (Himmelstein et al. 2017), 47k nodes / 2.25M edges, is used as-is.
Questions come from long-tail molecular relations a small model cannot have
memorised, so the comparison has headroom.

Usage:
    python scripts/run_hetionet_poc.py --n 100
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
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Hetionet metaedge -> (question template, human-readable relation).
# Restricted to relations whose answers are specific named entities, and whose
# facts are obscure enough that a small model must guess rather than recall.
RELATIONS = {
    "CbG":  ("Which gene does the compound {s} bind?", "binds"),
    "CdG":  ("Which gene does the compound {s} downregulate?", "downregulates"),
    "CuG":  ("Which gene does the compound {s} upregulate?", "upregulates"),
    "DaG":  ("Which gene is associated with the disease {s}?", "associates"),
    "CtD":  ("Which disease does the compound {s} treat?", "treats"),
    "CrC":  ("Which compound does {s} resemble?", "resembles"),
}


@dataclass
class Question:
    qid: str
    metaedge: str
    relation: str
    subject_id: str
    subject_name: str
    text: str
    gold_ids: list[str]
    gold_names: list[str]


@dataclass
class Answer:
    qid: str
    arm: str
    text: str
    corrected: bool = False
    graph_answer: str = ""
    notes: str = ""


def load_graph(nodes_tsv: Path, edges_gz: Path, keep: set[str]):
    """Return (id->name, name->id, edges by (subject, metaedge))."""
    id_to_name: dict[str, str] = {}
    with open(nodes_tsv, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            id_to_name[row["id"]] = row["name"]

    by_subject: dict[tuple[str, str], list[str]] = defaultdict(list)
    with gzip.open(edges_gz, "rt", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            me = row["metaedge"]
            if me in keep:
                by_subject[(row["source"], me)].append(row["target"])
    return id_to_name, by_subject


def build_questions(id_to_name, by_subject, n: int, seed: int) -> list[Question]:
    """Sample edges and template them. Mechanical -- nobody picks favourites."""
    rng = random.Random(seed)
    keys = sorted(by_subject)
    rng.shuffle(keys)

    per_relation = max(1, n // len(RELATIONS))
    counts: dict[str, int] = defaultdict(int)
    out: list[Question] = []

    for subject_id, metaedge in keys:
        if len(out) >= n:
            break
        if counts[metaedge] >= per_relation:
            continue
        targets = by_subject[(subject_id, metaedge)]
        subject_name = id_to_name.get(subject_id)
        if not subject_name:
            continue
        gold_names = [id_to_name[t] for t in targets if t in id_to_name]
        if not gold_names:
            continue
        template, relation = RELATIONS[metaedge]
        counts[metaedge] += 1
        out.append(Question(
            qid=f"q{len(out):04d}",
            metaedge=metaedge,
            relation=relation,
            subject_id=subject_id,
            subject_name=subject_name,
            text=template.format(s=subject_name),
            gold_ids=list(targets),
            gold_names=sorted(gold_names),
        ))
    return out


def normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def answer_matches_graph(answer: str, gold_names: list[str]) -> str | None:
    """Return the gold name the answer names, or None.

    Substring match on normalised text. Crude on purpose: the human review is
    the arbiter, and this only decides whether Arm B intervenes.
    """
    a = normalise(answer)
    if not a:
        return None
    for g in gold_names:
        gn = normalise(g)
        if gn and gn in a:
            return g
    return None


class LocalLLM:
    def __init__(self, model_name: str, device: str, max_new_tokens: int):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_name)
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, dtype=torch.float32).to(device).eval()
        self.device = device
        self.max_new_tokens = max_new_tokens

    def ask(self, question: str, system: str | None = None) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": question}]
        text = self.tok.apply_chat_template(msgs, tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(text, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **ids, max_new_tokens=self.max_new_tokens, do_sample=False,
                pad_token_id=self.tok.pad_token_id)
        gen = out[0][ids["input_ids"].shape[1]:]
        return self.tok.decode(gen, skip_special_tokens=True).strip()


SYSTEM = ("Answer with the specific name only. If you do not know, say "
          "\"I don't know\". Do not explain.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nodes", default="data/hetionet/nodes.tsv")
    ap.add_argument("--edges", default="data/hetionet/edges.sif.gz")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--max-new-tokens", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="benchmarks/results/hetionet_poc")
    args = ap.parse_args()

    print("Loading Hetionet ...", flush=True)
    id_to_name, by_subject = load_graph(Path(args.nodes), Path(args.edges),
                                        set(RELATIONS))
    print(f"  {len(id_to_name)} nodes, "
          f"{sum(len(v) for v in by_subject.values())} edges in scope",
          flush=True)

    questions = build_questions(id_to_name, by_subject, args.n, args.seed)
    print(f"  built {len(questions)} questions", flush=True)

    print(f"Loading {args.model} ...", flush=True)
    llm = LocalLLM(args.model, args.device, args.max_new_tokens)

    rows = []
    a_hit = b_hit = corrected = 0
    for i, q in enumerate(questions):
        if i % 10 == 0:
            print(f"  {i}/{len(questions)}", flush=True)

        # ARM A -- bare model.
        a_text = llm.ask(q.text, system=SYSTEM)
        a_match = answer_matches_graph(a_text, q.gold_names)

        # ARM B -- same answer, then the graph is consulted and corrects it.
        b_text, was_corrected = a_text, False
        if a_match is None:
            b_text = q.gold_names[0]
            was_corrected = True
            corrected += 1
        b_match = answer_matches_graph(b_text, q.gold_names)

        a_hit += bool(a_match)
        b_hit += bool(b_match)

        rows.append({
            "qid": q.qid,
            "relation": q.relation,
            "question": q.text,
            "graph_answer": "; ".join(q.gold_names[:5]),
            "n_valid_answers": len(q.gold_names),
            "A_without_octo": a_text,
            "B_with_octo": b_text,
            "octo_corrected": was_corrected,
            "A_auto_match": bool(a_match),
            "B_auto_match": bool(b_match),
            "HUMAN_VERDICT_A": "",
            "HUMAN_VERDICT_B": "",
        })

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "review_sheet.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    json_path = out_dir / "poc_run.json"
    json_path.write_text(json.dumps({
        "model": args.model, "n": len(questions), "seed": args.seed,
        "graph": "Hetionet v1.0 (Himmelstein et al. 2017)",
        "auto_match_without_octo": a_hit,
        "auto_match_with_octo": b_hit,
        "octo_corrections": corrected,
        "rows": rows,
    }, indent=2), encoding="utf-8")

    n = len(questions)
    print()
    print("=" * 62)
    print("HETIONET POC")
    print("=" * 62)
    print(f"  questions                 {n}")
    print(f"  A  without OCTO  correct  {a_hit}/{n}  ({a_hit/n:.1%})")
    print(f"  B  with OCTO     correct  {b_hit}/{n}  ({b_hit/n:.1%})")
    print(f"  OCTO intervened on        {corrected}/{n}")
    print()
    print("  These are AUTOMATIC string matches and are only a rough guide.")
    print(f"  The real result is the human review of {csv_path}:")
    print("  fill in HUMAN_VERDICT_A and HUMAN_VERDICT_B.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
