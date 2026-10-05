#!/usr/bin/env python3
"""
Text to Legend: can a model name the right properties, w/o and with TAHI?

The eval set is not invented. Every item is a real Legend Service checked into
`finos/legend-engine` -- a query written by Legend's own engineers, with the
column labels they wrote. From each Service we take:

    class        the class the query starts from, e.g. model::Firm
    columns      the human-written column labels, e.g. 'Legal Name'
    gold         the property paths the real query uses, e.g. legalName

The task: given the class and the column labels, name the property paths.
Scoring is exact set comparison against the real query. No judge.

    w/o TAHI   the model answers on its own
    with TAHI  same model, same prompt, but the decoder can only emit property
               names the class actually declares, looked up from the parsed
               model. That set is 5-15 names -- the analogue of MetaQA's
               traversal candidates, not the answer.

The class is given, exactly as MetaQA gives the seed entity. Two disclosures
that matter:

  * `--drop-trivial` removes items whose column label is identical to the
    property name, because there the label leaks the answer. Reported both ways.
  * n is small. There are only ~20 Services in the public repo carrying both a
    start class and property paths. This is a probe, not a benchmark, and the
    confidence interval is wide.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessorList

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tahi.graph.legend_model import LegendModel  # noqa: E402
from tahi.validate.constrained import GraphConstrainedLogits  # noqa: E402

_SERVICE = re.compile(r"^Service\s+([\w:]+)\s*\{", re.M)

PROMPT = """A Legend (Pure) query starts from class {cls}.

It must produce these columns:
{cols}

Name the property of {short} that supplies each column, in the same order.
Reply with ONLY a comma-separated list of property names.

Properties:"""


def _block(text: str, open_brace: int) -> str | None:
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1:i]
    return None


def load_services(pure_dir: Path) -> list[dict]:
    """Every Service with a start class, property paths, and column labels."""
    out: dict[str, dict] = {}
    for f in sorted(pure_dir.glob("*.pure")):
        txt = f.read_text(errors="replace")
        for m in _SERVICE.finditer(txt):
            body = _block(txt, m.end() - 1)
            if body is None:
                continue
            q = re.search(r"query:\s*\|([^;]+);", body, re.S)
            if not q:
                continue
            query = " ".join(q.group(1).split())
            cm = re.match(r"([\w:]+)\.all\(\)", query)
            if not cm:
                continue
            paths = re.findall(r"\$\w+\.([\w.]+)", query)
            # column labels: `['A', 'B']` after a project(...) list, or the
            # `~['Label': x|$x.p]` form.
            labels = re.findall(r"~?\[\s*'([^']+)'\s*:", query)
            if not labels:
                tail = re.findall(r"\],\s*\[([^\]]*)\]", query)
                if tail:
                    labels = [s.strip().strip("'") for s in tail[0].split(",")]
            if not labels:
                labels = re.findall(r"~\[\s*(\w+)\s*:", query)
            if not paths or len(labels) != len(paths):
                continue
            out[query] = {"service": m.group(1), "class": cm.group(1),
                          "columns": labels, "gold": paths, "query": query}
    return list(out.values())


def main() -> int:
    ap = argparse.ArgumentParser(description="Text to Legend, w/o and with TAHI")
    ap.add_argument("--pure-dir", default="data/legend/pure")
    ap.add_argument("--out", default="data/legend/results/legend_text2query.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-1.5B-Instruct")
    ap.add_argument("--max-new", type=int, default=96)
    ap.add_argument("--drop-trivial", action="store_true",
                    help="skip items whose column label equals the property name")
    args = ap.parse_args()

    pure = Path(args.pure_dir)
    print("parsing Legend model ...", flush=True)
    lm = LegendModel(sorted(pure.glob("*.pure")))
    print(f"  {len(lm)} classes, {len(lm.edges())} edges", flush=True)

    items = load_services(pure)
    print(f"  {len(items)} Services with a class, property paths and column labels",
          flush=True)

    # keep only those whose class we can resolve and whose gold is reachable
    keep = []
    for it in items:
        cls = lm.resolve(it["class"])
        if cls is None:
            continue
        declared = set(lm.properties_of(cls.name))
        # gold paths may be dotted; the first hop must be on this class
        first = [p.split(".")[0] for p in it["gold"]]
        if not set(first) <= declared:
            continue
        trivial = all(re.sub(r"\W", "", c).lower() == g.split(".")[0].lower()
                      for c, g in zip(it["columns"], it["gold"], strict=False))
        it["trivial"] = trivial
        it["resolved_class"] = cls.name
        it["allowed"] = sorted(declared)
        keep.append(it)
    dropped = len(items) - len(keep)
    if args.drop_trivial:
        n_triv = sum(1 for i in keep if i["trivial"])
        keep = [i for i in keep if not i["trivial"]]
        print(f"  dropped {n_triv} trivial items (label == property name)", flush=True)
    print(f"  {len(keep)} usable  ({dropped} unresolvable against the parsed model)",
          flush=True)
    if not keep:
        print("nothing to evaluate", file=sys.stderr)
        return 1

    print(f"loading {args.model} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16)
    model = model.to("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    eos = tok.eos_token_id

    def gen(prompt: str, allowed: list[str] | None = None):
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = enc.input_ids.shape[1]
        procs = None
        if allowed:
            proc = GraphConstrainedLogits(tok, allowed, prompt_len=plen,
                                          eos_token_id=eos, min_items=1)
            procs = LogitsProcessorList([proc])
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=args.max_new, do_sample=False,
                                 pad_token_id=eos, logits_processor=procs)
        new = out[0, plen:]
        truncated = len(new) >= args.max_new and int(new[-1]) != eos
        return (tok.decode(new, skip_special_tokens=True).strip(), truncated,
                proc.intervention_rate if allowed else None)

    def parse(text: str, truncated: bool) -> list[str]:
        names = [re.sub(r"\s+", "", x) for x in text.strip().split("\n")[0].split(",")]
        names = [n for n in names if n]
        return names[:-1] if truncated and names else names

    rows = []
    started = time.perf_counter()
    for i, it in enumerate(keep):
        cls = it["resolved_class"]
        short = cls.split("::")[-1]
        gold = {p.split(".")[0] for p in it["gold"]}
        cols = "\n".join(f"  - {c}" for c in it["columns"])
        prompt = PROMPT.format(cls=cls, short=short, cols=cols)

        raw_a, tr_a, _ = gen(prompt)
        a = parse(raw_a, tr_a)
        raw_b, tr_b, ir = gen(prompt, allowed=it["allowed"])
        b = parse(raw_b, tr_b)

        declared = set(it["allowed"])
        rows.append({
            "service": it["service"], "class": cls, "columns": it["columns"],
            "gold": sorted(gold), "trivial": it["trivial"],
            "n_allowed": len(declared),
            "without_tahi": a, "without_tahi_right": set(a) == gold,
            "without_tahi_invalid": [x for x in a if x not in declared],
            "with_tahi": b, "with_tahi_right": set(b) == gold,
            "with_tahi_invalid": [x for x in b if x not in declared],
            "intervention_rate": ir,
        })
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{len(keep)}", flush=True)

    n = len(rows)

    def acc(k):
        return sum(r[k + "_right"] for r in rows) / n

    def invalid_rate(k):
        tot = sum(len(r[k]) for r in rows)
        bad = sum(len(r[k + "_invalid"]) for r in rows)
        return bad / tot if tot else 0.0

    t = Counter((r["without_tahi_right"], r["with_tahi_right"]) for r in rows)
    fixed, broke = t[(False, True)], t[(True, False)]
    irs = [r["intervention_rate"] for r in rows if r["intervention_rate"] is not None]

    print(f"\n{'='*68}\nTEXT TO LEGEND — real Services from finos/legend-engine  n={n}\n{'='*68}")
    print(f"{'':40s}{'w/o TAHI':>10s}{'with TAHI':>12s}")
    print(f"  {'exact property set':38s}{acc('without_tahi'):>10.3f}{acc('with_tahi'):>12.3f}")
    print(f"  {'named a property the class lacks':38s}"
          f"{invalid_rate('without_tahi'):>10.3f}{invalid_rate('with_tahi'):>12.3f}")
    print(f"\n  fixed {fixed}   broken {broke}   net {fixed-broke:+d}")
    if irs:
        print(f"  mean intervention rate  {sum(irs)/len(irs):.3f}")
    nn = fixed + broke
    if nn:
        from math import comb
        k = min(fixed, broke)
        p = min(1.0, 2 * sum(comb(nn, j) for j in range(k + 1)) / 2 ** nn)
        print(f"  McNemar exact p = {p:.4f}   (n={n}, treat as indicative only)")
    print(f"  mean allowed-set size {sum(r['n_allowed'] for r in rows)/n:.1f}")
    print(f"  wall clock {time.perf_counter()-started:.0f}s")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "model": args.model, "drop_trivial": args.drop_trivial,
        "source": "Service definitions in finos/legend-engine",
        "accuracy": {"without_tahi": acc("without_tahi"), "with_tahi": acc("with_tahi")},
        "invalid_property_rate": {"without_tahi": invalid_rate("without_tahi"),
                                  "with_tahi": invalid_rate("with_tahi")},
        "fixed": fixed, "broken": broke, "rows": rows}, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
