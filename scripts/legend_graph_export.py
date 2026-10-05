#!/usr/bin/env python3
"""
Export the parsed Legend model as JSON for the graph viewer.

The full parse is 4,868 classes and 4,101 edges, but most of that bulk is the
protocol metamodel shipped once per released version -- ten near-identical
copies of the same graph. Dumping all of it produces a hairball that says
nothing. So this writes a small number of *views*, each a coherent subgraph:

    protocol   one released version of the Legend protocol metamodel, the
               largest genuinely connected structure in the corpus
    demo       the human-authored demo and domain models -- Firm, Person,
               COVIDData -- small enough to read every label

All ten protocol versions together would be 3,483 nodes: a hairball that shows
scale and nothing else. One version shows the same structure legibly.

Isolated classes (no class-typed property in either direction) are dropped from
the graph views: 1,417 of them, and they carry no structure to look at. Their
count is reported so the omission is visible rather than silent.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tahi.graph.legend_model import LegendModel  # noqa: E402

HUMAN_PACKAGES = ("demo", "model", "domain", "test", "simple",
                  "testModelStoreTestSuites", "testM2MOptionalFromList",
                  "testServiceStoreTestSuites")


def build_view(lm: LegendModel, keep) -> dict:
    """Nodes and edges for the classes `keep(name)` accepts."""
    names = [n for n in lm.classes if keep(n)]
    nameset = set(names)
    edges = [(s, p, t) for s, p, t in lm.edges() if s in nameset and t in nameset]

    deg = collections.Counter()
    for s, _p, t in edges:
        deg[s] += 1
        deg[t] += 1
    connected = [n for n in names if deg[n]]

    idx = {n: i for i, n in enumerate(connected)}
    nodes = []
    for n in connected:
        c = lm.classes[n]
        props = lm.properties_of_class(n)
        nodes.append({
            "id": idx[n],
            "name": n,
            "short": c.short_name,
            "pkg": "::".join(n.split("::")[:-1]),
            "root": n.split("::")[0],
            "parent": c.parent,
            "degree": deg[n],
            "props": [{"n": p.name, "t": p.type.split("::")[-1], "m": p.multiplicity,
                       "prim": p.is_primitive} for p in props],
        })
    links = [{"s": idx[s], "t": idx[t], "p": p}
             for s, p, t in edges if s in idx and t in idx]
    return {
        "nodes": nodes,
        "links": links,
        "isolated": len(names) - len(connected),
        "total_classes": len(names),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Export Legend graph views as JSON")
    ap.add_argument("--pure-dir", default="data/legend/pure")
    ap.add_argument("--out", default="data/legend/graph_views.json")
    args = ap.parse_args()

    lm = LegendModel(sorted(Path(args.pure_dir).glob("*.pure")))
    print(f"parsed {len(lm)} classes, {len(lm.edges())} edges", flush=True)

    versions = {m.group(0) for k in lm.classes
                if (m := re.search(r"v\d+_\d+_\d+", k))}
    newest = max(versions, key=lambda v: tuple(int(x) for x in v[1:].split("_")))

    views = {
        "demo": {
            "label": "Human-authored models",
            "note": "The demo and domain models: Firm, Person, COVIDData. Small "
                    "enough to read every label.",
            "data": build_view(lm, lambda n: n.split("::")[0] in HUMAN_PACKAGES),
        },
        "protocol": {
            "label": f"Legend protocol metamodel ({newest})",
            "note": "One released version of the metamodel Legend uses to "
                    "describe itself. The largest connected structure here.",
            "data": build_view(lm, lambda n: newest in n),
        },
    }

    for k, v in views.items():
        d = v["data"]
        print(f"  {k:9s} {len(d['nodes']):5d} nodes  {len(d['links']):5d} edges  "
              f"({d['isolated']} isolated dropped)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(views, separators=(",", ":")))
    print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
