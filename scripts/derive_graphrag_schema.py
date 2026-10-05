#!/usr/bin/env python
"""
Recover GraphRAG-Bench's own schema from the question set.

The medical corpus ships as prose, so any system evaluated on it builds its own
graph -- and whoever builds it chooses a schema. Choosing one by hand means the
benchmark then measures the guess as much as it measures the retriever.

It turns out the guess is avoidable. `evidence_relations` is prose, but it was
generated from an ontology and leaks the ontology's vocabulary in two forms:

    "Risk Factor includes radiation exposure, family history ..."
    "Anatomical Site includes: Pharynx, Nasopharynx"
    "... are listed for cervical cancer in the ontology"

The `<Kind> includes[:]` frame names a node kind outright. Mining those gives a
schema grounded in the benchmark rather than in this author's priors, and the
counts say which kinds carry enough mass to be worth extracting.

Nothing here calls an API.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# "Risk Factor includes ...", "Anatomical Site includes: ..." -- the kind is the
# Title Case run immediately before `includes`. Bounded at four words so a whole
# capitalised sentence cannot masquerade as a type name.
KIND_INCLUDES = re.compile(
    r"(?:^|[;.]\s*)((?:[A-Z][A-Za-z]*\s+){0,3}[A-Z][A-Za-z]*)\s+includes\b\s*:?",
)

# Sentences are joined with "; " -- the generator's separator, not punctuation
# inside a clause.
SPLIT = re.compile(r"\s*;\s*")

# Frames that state a relation between two entities, mined for the edge side of
# the schema. Deliberately few: this is a survey of what the benchmark asserts,
# not an extractor.
REL_FRAMES = [
    (r"\bis a (?:type|subtype|form) of\b", "subtype_of"),
    (r"\bare symptoms of\b|\bis a symptom of\b|\bsymptoms include\b", "has_symptom"),
    (r"\bincreases? (?:the )?risk of\b", "increases_risk_of"),
    (r"\bis (?:a |the )?(?:primary |main )?treatment for\b|\bis treated (?:with|by)\b",
     "treated_by"),
    (r"\bis diagnosed by\b|\bdiagnostic methods? (?:include|is)\b|"
     r"\bis (?:the )?(?:primary )?diagnostic\b", "diagnosed_by"),
    (r"\bmay metastasi[sz]e to\b|\bspreads? to\b", "metastasizes_to"),
    (r"\bis (?:a |an )?.*\b(?:gene|mutation|alteration)s? (?:in|of|associated)\b|"
     r"\bgenetic alterations? in\b", "associated_with_gene"),
    (r"\boriginates? in\b|\barises? (?:in|from)\b|\baffects? the\b|"
     r"\bis located in\b", "located_in"),
    (r"\bis staged\b|\bstage\b.*\bdescribes\b", "has_stage"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions",
                    default="data/graphrag_bench/medical_questions.json")
    ap.add_argument("--min-count", type=int, default=3,
                    help="Drop kinds seen fewer than this many times.")
    ap.add_argument("--out", default="data/graphrag_bench/derived_schema.json")
    args = ap.parse_args()

    qs = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    print(f"questions: {len(qs)}")

    kinds = Counter()
    kind_examples: dict[str, list[str]] = defaultdict(list)
    rel_counts = Counter()
    n_sent = 0
    mentions_ontology = 0

    for q in qs:
        er = q.get("evidence_relations") or ""
        if "ontolog" in er.lower():
            mentions_ontology += 1
        for sent in SPLIT.split(er):
            sent = sent.strip()
            if not sent:
                continue
            n_sent += 1
            for m in KIND_INCLUDES.finditer(sent):
                k = m.group(1).strip()
                kinds[k] += 1
                if len(kind_examples[k]) < 3:
                    tail = sent[m.end():].strip()
                    kind_examples[k].append(tail[:90])
            for pat, name in REL_FRAMES:
                if re.search(pat, sent, re.I):
                    rel_counts[name] += 1

    print(f"evidence sentences: {n_sent}")
    print(f"questions whose evidence names 'the ontology': {mentions_ontology}\n")

    kept = [(k, c) for k, c in kinds.most_common() if c >= args.min_count]
    header = 'NODE KIND (mined from "<Kind> includes")'
    print(f"{header:<38}{'count':>7}")
    print("-" * 46)
    for k, c in kept:
        print(f"{k:<38}{c:>7}")
        for ex in kind_examples[k][:1]:
            print(f"      e.g. {ex}")
    dropped = sum(c for k, c in kinds.items() if c < args.min_count)
    print(f"\n(dropped {len(kinds)-len(kept)} kinds seen <{args.min_count} times, "
          f"{dropped} occurrences)\n")

    print(f"{'RELATION FRAME':<38}{'sentences':>10}")
    print("-" * 48)
    for r, c in rel_counts.most_common():
        print(f"{r:<38}{c:>10}")

    out = {
        "source": args.questions,
        "method": "mined from evidence_relations; no LLM, no API",
        "node_kinds": [{"kind": k, "count": c, "examples": kind_examples[k]}
                       for k, c in kept],
        "relation_frames": [{"relation": r, "sentences": c}
                            for r, c in rel_counts.most_common()],
        "evidence_sentences": n_sent,
        "questions_naming_ontology": mentions_ontology,
    }
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
