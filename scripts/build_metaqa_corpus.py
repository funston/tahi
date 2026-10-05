#!/usr/bin/env python
"""Verbalise the MetaQA KB into text passages, two ways.

The text arm of the continuation eval needs passages to embed; the KB holds
triples. How those triples are grouped into passages decides how much of the
graph's traversal advantage is pre-baked into the text index, so the grouping is
an experimental condition rather than a formatting detail. Two are built:

  A  fact    one passage per triple. Strict information parity -- every fact is
             reachable by both arms and neither holds more. A 3-hop question
             needs three separate passages, which is the mechanism under test.

  B  entity  one passage per entity, carrying every fact it participates in, in
             both directions. The natural "document about this thing", and the
             conservative condition: retrieving the seed entity's document hands
             the text arm its first hop for free, so the graph must win from a
             worse starting position.

Templates are fixed strings, never model-generated. An LLM verbaliser could
smuggle in inferences present in neither the KB nor any real article, and it
would not be reproducible. Following evalgen's principle: make the property
structural rather than something a generator has to achieve.

    PYTHONPATH=src .venv/bin/python scripts/build_metaqa_corpus.py
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

# subject-side and object-side phrasing per relation. Both are needed: scheme B
# gives a person a document listing the films they worked on, which only exists
# in the inverse direction.
FORWARD = {
    "directed_by":     "{s} was directed by {o}.",
    "written_by":      "{s} was written by {o}.",
    "starred_actors":  "{s} starred {o}.",
    "release_year":    "{s} was released in {o}.",
    "has_genre":       "{s} is a {o} film.",
    "in_language":     "{s} is in {o}.",
    "has_tags":        "{s} is tagged {o}.",
    "has_imdb_rating": "{s} has an IMDb rating of {o}.",
    "has_imdb_votes":  "{s} has {o} IMDb votes.",
}

INVERSE = {
    "directed_by":     "{o} directed {s}.",
    "written_by":      "{o} wrote {s}.",
    "starred_actors":  "{o} starred in {s}.",
    "release_year":    "{o} is the release year of {s}.",
    "has_genre":       "{o} is a genre of {s}.",
    "in_language":     "{o} is the language of {s}.",
    "has_tags":        "{o} is a tag of {s}.",
    "has_imdb_rating": "{o} is the IMDb rating of {s}.",
    "has_imdb_votes":  "{o} is the IMDb vote count of {s}.",
}

# Relations whose object is an attribute rather than a thing worth its own
# document. A "1955" document listing every film from 1955 is not a document
# anyone would write, and it would give the text arm a free year-index.
ATTRIBUTE_TAILS = {"release_year", "has_genre", "in_language", "has_tags",
                   "has_imdb_rating", "has_imdb_votes"}


def load_triples(path: Path) -> list[tuple[str, str, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != 3:
            continue
        out.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return out


def build_fact_corpus(triples) -> list[dict]:
    """Scheme A: one passage per triple."""
    rows = []
    for i, (s, r, o) in enumerate(triples):
        tmpl = FORWARD.get(r)
        if tmpl is None:
            continue
        rows.append({
            "passage_id": f"fact::{i:06d}",
            "text": tmpl.format(s=s, o=o),
            "entities": [s, o],
            "triple": [s, r, o],
        })
    return rows


def build_entity_corpus(triples) -> list[dict]:
    """Scheme B: one passage per entity, both directions."""
    forward: dict[str, list[tuple[str, str]]] = defaultdict(list)
    inverse: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for s, r, o in triples:
        forward[s].append((r, o))
        if r not in ATTRIBUTE_TAILS:
            inverse[o].append((r, s))

    rows = []
    for ent in sorted(set(forward) | set(inverse)):
        lines = [f"{ent}."]
        neighbours = {ent}
        for r, o in forward.get(ent, []):
            tmpl = FORWARD.get(r)
            if tmpl:
                lines.append(tmpl.format(s=ent, o=o))
                neighbours.add(o)
        for r, s in inverse.get(ent, []):
            tmpl = INVERSE.get(r)
            if tmpl:
                lines.append(tmpl.format(s=s, o=ent))
                neighbours.add(s)
        rows.append({
            "passage_id": f"entity::{ent}",
            "text": " ".join(lines),
            "entities": sorted(neighbours),
            "subject": ent,
        })
    return rows


def write(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", default="data/metaqa/kb.txt")
    ap.add_argument("--out-dir", default="data/metaqa")
    args = ap.parse_args()

    triples = load_triples(Path(args.kb))
    out = Path(args.out_dir)

    fact = build_fact_corpus(triples)
    entity = build_entity_corpus(triples)
    write(fact, out / "corpus_fact.jsonl")
    write(entity, out / "corpus_entity.jsonl")

    fw = sum(len(r["text"].split()) for r in fact) / max(len(fact), 1)
    ew = sum(len(r["text"].split()) for r in entity) / max(len(entity), 1)
    print(f"triples           {len(triples):,}")
    print(f"A fact passages   {len(fact):,}   mean {fw:5.1f} words")
    print(f"B entity passages {len(entity):,}   mean {ew:5.1f} words")
    print()
    print("A sample:", fact[0]["text"])
    print("B sample:", entity[0]["text"][:220], "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
