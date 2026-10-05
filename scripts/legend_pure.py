#!/usr/bin/env python3
"""
Text to Pure: generate a real Legend query, w/o and with TAHI.

The task is the actual one, not a proxy. Given a request in English, write the
Pure query::

    model::Firm.all()->project([x|$x.employees.firstName], ['First Name'])

Gold queries are real Legend Services checked into `finos/legend-engine` --
written by Legend's own engineers, not by us. The English request is built from
the column labels those engineers wrote.

Two arms, same model, same prompt:

    w/o TAHI   generate the query, done. This is text-to-query as normally
               shipped, and the class's properties are pasted into the prompt,
               which is the generous version of the baseline.

    with TAHI  generate, then walk every property path in the generated query
               against the parsed Legend model. Hand back only the paths that do
               not exist, with what the class does declare, and ask again. Same
               correction loop as MetaQA; the difference is that Legend's own
               model supplies the ground truth for free.

Scored two ways, both by exact comparison against the real query:

    paths valid    does every property path in the query exist in the model
    paths correct  are they exactly the paths the real query uses

Nothing is judged by another language model.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from legend_text2query import load_services  # noqa: E402

from tahi.graph.legend_model import LegendModel  # noqa: E402

ASK = """Write a Legend Pure query.

Class: {cls}
Its properties: {props}

The query must return these columns:
{cols}

Pure syntax:
  {cls}.all()->project([x|$x.someProperty], ['Column Label'])

A property whose type is another class is followed with a dot:
  x|$x.someRelation.somePropertyOnThatClass

Reply with ONLY the query, one line, no explanation."""

FIX = """This Legend Pure query is wrong:

{query}

The Legend model was checked. Findings:
{findings}

Write the corrected query. Reply with ONLY the query, one line."""

# `$x.a.b.c` inside a lambda
_PATH = re.compile(r"\$\w+\.([A-Za-z_][\w.]*)")


def paths_in(query: str) -> list[str]:
    """Property paths a Pure query dereferences, e.g. `employees.firstName`."""
    out, seen = [], set()
    for m in _PATH.finditer(query):
        p = m.group(1).rstrip(".")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def check(lm: LegendModel, cls: str, query: str) -> tuple[list[str], str | None]:
    """Which paths do not exist, and the note to hand back. None if all valid."""
    bad, notes = [], []
    for p in paths_in(query):
        ok, why = lm.validate_path(cls, p.split("."))
        if not ok:
            bad.append(p)
            notes.append(f"- $x.{p} is not valid. {why}")
    return bad, ("\n".join(notes) if notes else None)


def main() -> int:
    ap = argparse.ArgumentParser(description="Text to Pure, w/o and with TAHI")
    ap.add_argument("--pure-dir", default="data/legend/pure")
    ap.add_argument("--out", default="data/legend/results/legend_pure.json")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--max-rounds", type=int, default=3)
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
            txt = (r.choices[0].message.content or "").strip()
            txt = re.sub(r"^```[a-z]*\n?|```$", "", txt, flags=re.M).strip()
            return txt.split("\n")[0].strip()
        except Exception as e:  # noqa: BLE001
            print(f"  LLM ERROR {type(e).__name__}", file=sys.stderr)
            return ""

    pure = Path(args.pure_dir)
    lm = LegendModel(sorted(pure.glob("*.pure")))
    print(f"parsed {len(lm)} classes, {len(lm.edges())} edges", flush=True)

    seen_svc: dict[str, dict] = {}
    for it in load_services(pure):
        cls = lm.resolve(it["class"])
        if cls is None:
            continue
        first = [p.split(".")[0] for p in it["gold"]]
        if not set(first) <= set(lm.properties_of(cls.name)):
            continue
        it["resolved"] = cls.name
        seen_svc.setdefault(it["service"], it)      # one row per Service
    items = list(seen_svc.values())
    print(f"{len(items)} distinct Services usable as gold queries\n", flush=True)
    if not items:
        return 1

    rows = []
    started = time.perf_counter()
    for i, it in enumerate(items):
        cls = it["resolved"]
        props = ", ".join(lm.properties_of(cls))
        cols = "\n".join(f"  - {c}" for c in it["columns"])
        gold = set(it["gold"])

        q0 = llm(ASK.format(cls=cls, props=props, cols=cols))
        bad0, note = check(lm, cls, q0)

        q, history = q0, []
        for _rnd in range(args.max_rounds):
            bad, note = check(lm, cls, q)
            if note is None:
                break
            nxt = llm(FIX.format(query=q, findings=note))
            history.append({"findings": note, "query": nxt})
            if not nxt or nxt == q:
                break
            q = nxt
        bad1, _ = check(lm, cls, q)

        rows.append({
            "service": it["service"], "class": cls, "columns": it["columns"],
            "gold_query": it["query"], "gold_paths": sorted(gold),
            "without_tahi": q0, "without_tahi_paths": paths_in(q0),
            "without_tahi_invalid": bad0,
            "without_tahi_all_valid": not bad0,
            "without_tahi_paths_correct": set(paths_in(q0)) == gold,
            "with_tahi": q, "with_tahi_paths": paths_in(q),
            "with_tahi_invalid": bad1,
            "with_tahi_all_valid": not bad1,
            "with_tahi_paths_correct": set(paths_in(q)) == gold,
            "rounds": len(history), "history": history,
        })
        print(f"  {i+1}/{len(items)}  {it['service'].split('::')[-1]}", flush=True)

    n = len(rows)

    def rate(k):
        return sum(r[k] for r in rows) / n

    t = Counter((r["without_tahi_paths_correct"], r["with_tahi_paths_correct"])
                for r in rows)
    fixed, broke = t[(False, True)], t[(True, False)]
    tv = Counter((r["without_tahi_all_valid"], r["with_tahi_all_valid"]) for r in rows)

    print(f"\n{'='*66}\nTEXT TO PURE — real Legend Services  n={n}  {args.model}\n{'='*66}")
    print(f"{'':44s}{'w/o TAHI':>10s}{'with TAHI':>12s}")
    print(f"  {'every property path exists in the model':42s}"
          f"{rate('without_tahi_all_valid'):>10.3f}{rate('with_tahi_all_valid'):>12.3f}")
    print(f"  {'paths match the real query exactly':42s}"
          f"{rate('without_tahi_paths_correct'):>10.3f}{rate('with_tahi_paths_correct'):>12.3f}")
    print(f"\n  queries made valid   {tv[(False, True)]}"
          f"   made invalid {tv[(True, False)]}")
    print(f"  answers fixed        {fixed}   broken {broke}   net {fixed-broke:+d}")
    print(f"  correction rounds used: {dict(sorted(Counter(r['rounds'] for r in rows).items()))}")
    print(f"  llm calls {calls['n']}   wall clock {time.perf_counter()-started:.0f}s")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "model": args.model,
        "source": "Service definitions in finos/legend-engine",
        "all_paths_valid": {"without_tahi": rate("without_tahi_all_valid"),
                            "with_tahi": rate("with_tahi_all_valid")},
        "paths_correct": {"without_tahi": rate("without_tahi_paths_correct"),
                          "with_tahi": rate("with_tahi_paths_correct")},
        "fixed": fixed, "broken": broke, "rows": rows}, indent=2))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
