#!/usr/bin/env python
"""
Build GCCA training data -- and the memory store both training and evaluation read.

Two memory sources:

  --memory-source retrieved   Memory slots are the documents OCTO actually
                              surfaced for each question, taken from a completed
                              benchmark run. This is the deployment condition.

  --memory-source oracle      Memory slots are the question's gold documents
                              (`expected_doc_ids`). This is the Gate A condition:
                              a zero-noise memory that contains the answer by
                              construction. If the gate stays shut here, it is not
                              retrieval quality holding it shut.

The script writes `memory_vectors.npz` alongside the JSONL. That file -- not the
text, and not a second encoding pass -- is what `train_gcca.py` and
`run_l3_native.py` both consume. The 2026-08-03 run was voided because those two
encoded memory independently and silently diverged once a graph encoder was
added to one of them. Sharing precomputed bytes makes that class of bug
unrepresentable rather than merely discouraged.

`--require-base-failure` keeps only questions the base model already fails
without memory. On items the 1.5B answers from parametric memory, gradient
descent has no reason to open the gate, so a flat alpha is the *correct*
optimum and the experiment cannot distinguish "cannot use memory" from "did not
need memory". Filtering removes that confound.

Usage (Gate A):
    python scripts/build_gcca_training_data.py \
        --results benchmarks/results/l3_native_run.json \
        --questions data/enterprise_rag/questions.jsonl \
        --corpus data/enterprise_rag/sources \
        --memory-source oracle --require-base-failure \
        --out-dir data/gcca_oracle
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from implementations.enterprise_rag import (  # noqa: E402
    STRUCTURE_SENSITIVE, iter_documents, load_questions,
)
from octo.native.memory_store import encode_texts, save_memory_store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("octo.gcca_data")

MAX_DOC_CHARS = 1200


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=None,
                    help="Completed benchmark JSON. Required for "
                         "--memory-source retrieved and for --require-base-failure.")
    ap.add_argument("--questions", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--arm", default="octo_l1",
                    help="Which arm's retrievals to train on (default: octo_l1)")
    ap.add_argument("--memory-source", choices=("retrieved", "oracle"),
                    default="retrieved")
    ap.add_argument("--require-base-failure", action="store_true",
                    help="Keep only questions the base arm answers poorly, so the "
                         "gate has a reason to open.")
    ap.add_argument("--base-arm", default="base")
    ap.add_argument("--base-failure-metric", default="token_f1",
                    choices=("token_f1", "exact_match", "fact_coverage"))
    ap.add_argument("--base-failure-max", type=float, default=0.5,
                    help="Keep the item when the base arm scores BELOW this.")
    ap.add_argument("--distractor-frac", type=float, default=0.0,
                    help="Fraction of memory slots replaced with documents from "
                         "other questions. Gate A runs at 0.0 -- zero noise.")
    ap.add_argument("--encoder", default="all-MiniLM-L6-v2",
                    help="MUST match the encoder train_gcca.py and run_l3_native.py "
                         "use, or d_model will not line up.")
    ap.add_argument("--out-dir", default="data/gcca")
    ap.add_argument("--test-frac", type=float, default=0.3)
    ap.add_argument("--max-slots", type=int, default=16)
    ap.add_argument("--doc-chars", type=int, default=MAX_DOC_CHARS)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.memory_source == "retrieved" and not args.results:
        log.error("--memory-source retrieved requires --results")
        return 1
    if args.require_base_failure and not args.results:
        log.error("--require-base-failure requires --results")
        return 1

    questions = {q.id: q for q in load_questions(args.questions)}
    log.info("Loaded %d questions", len(questions))

    # ---- Which documents fill each question's memory ------------------------
    if args.memory_source == "oracle":
        memory_ids: dict[str, list[str]] = {
            qid: list(q.gold_document_ids)[: args.max_slots]
            for qid, q in questions.items() if q.gold_document_ids
        }
        log.info("Oracle memory: %d/%d questions have gold documents",
                 len(memory_ids), len(questions))
    else:
        results = json.loads(Path(args.results).read_text(encoding="utf-8"))
        memory_ids = {
            r["question_id"]: r["retrieved_ids"][: args.max_slots]
            for r in results["per_item"] if r["arm"] == args.arm
        }
        if not memory_ids:
            log.error("No items for arm %r in %s", args.arm, args.results)
            return 1
        log.info("Retrieved memory: %d questions from arm %r",
                 len(memory_ids), args.arm)

    # ---- Memory-dependency filter ------------------------------------------
    base_scores: dict[str, float] = {}
    if args.require_base_failure:
        results = json.loads(Path(args.results).read_text(encoding="utf-8"))
        base_scores = {
            r["question_id"]: float(r[args.base_failure_metric])
            for r in results["per_item"] if r["arm"] == args.base_arm
        }
        if not base_scores:
            log.error("No items for base arm %r in %s", args.base_arm, args.results)
            return 1
        keep = {qid for qid, s in base_scores.items() if s < args.base_failure_max}
        before = len(memory_ids)
        memory_ids = {q: d for q, d in memory_ids.items() if q in keep}
        log.info("Base-failure filter (%s < %.2f on arm %r): %d -> %d questions",
                 args.base_failure_metric, args.base_failure_max, args.base_arm,
                 before, len(memory_ids))
        if not memory_ids:
            log.error("Filter removed every question; nothing to train on.")
            return 1

    # ---- Resolve document text ---------------------------------------------
    wanted: set[str] = {d for ids in memory_ids.values() for d in ids}
    log.info("Resolving text for %d referenced documents ...", len(wanted))
    texts: dict[str, str] = {}
    for doc in iter_documents(args.corpus):
        if doc.doc_id in wanted:
            texts[doc.doc_id] = doc.text[: args.doc_chars]
            if len(texts) == len(wanted):
                break
    log.info("Resolved %d/%d", len(texts), len(wanted))
    if len(texts) < len(wanted):
        log.warning("%d referenced documents were not found in the corpus; their "
                    "slots are dropped.", len(wanted) - len(texts))

    # ---- Build records ------------------------------------------------------
    records = []
    skipped_no_answer = skipped_no_memory = 0
    for qid, doc_ids in sorted(memory_ids.items()):
        q = questions.get(qid)
        if q is None:
            continue
        if not q.gold_answer.strip():
            skipped_no_answer += 1
            continue
        # info_not_found items have no answer to ground -- the correct behaviour
        # is abstention, which is a different objective. Train the abstention
        # target explicitly rather than dropping the signal.
        answer = q.gold_answer.strip() if not q.is_unanswerable else "I don't know"
        mem = [texts[d] for d in doc_ids if d in texts]
        if not mem:
            skipped_no_memory += 1
            continue
        records.append({
            "question_id": qid,
            "category": q.category,
            "query": q.text,
            "answer": answer,
            "memory_texts": mem,
            "memory_doc_ids": [d for d in doc_ids if d in texts],
        })

    log.info("Built %d records (skipped %d no-answer, %d no-memory)",
             len(records), skipped_no_answer, skipped_no_memory)
    if not records:
        log.error("No records built.")
        return 1

    # ---- Optional hard-negative distractors --------------------------------
    n_distracted = 0
    if args.distractor_frac > 0:
        rng_d = random.Random(args.seed + 1)
        pool = sorted(texts)
        for r in records:
            own = set(r["memory_doc_ids"])
            k = int(round(len(r["memory_texts"]) * args.distractor_frac))
            for _ in range(k):
                cand = rng_d.choice(pool)
                if cand in own:
                    continue
                r["memory_texts"][rng_d.randrange(len(r["memory_texts"]))] = texts[cand]
                n_distracted += 1
        log.info("Injected %d distractor slots (frac=%.2f)",
                 n_distracted, args.distractor_frac)

    # ---- Stratified split by category --------------------------------------
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(r)
    rng = random.Random(args.seed)
    train, test = [], []
    for cat in sorted(by_cat):
        items = sorted(by_cat[cat], key=lambda r: r["question_id"])
        rng.shuffle(items)
        n_test = max(1, round(len(items) * args.test_frac)) if len(items) > 1 else 0
        test.extend(items[:n_test])
        train.extend(items[n_test:])

    train_ids = {r["question_id"] for r in train}
    test_ids = {r["question_id"] for r in test}
    overlap = train_ids & test_ids
    if overlap:
        log.error("Split leakage: %d ids in both halves", len(overlap))
        return 1

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("test", test)):
        path = out / f"{name}.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for r in sorted(rows, key=lambda x: x["question_id"]):
                fh.write(json.dumps(r) + "\n")
        struct = sum(1 for r in rows if r["category"] in STRUCTURE_SENSITIVE)
        slots = sum(len(r["memory_texts"]) for r in rows) / max(len(rows), 1)
        log.info("%-5s %3d records (%d structure-sensitive, %.1f mem slots avg) -> %s",
                 name, len(rows), struct, slots, path)

    # ---- The memory store: one encoding pass, read by both sides ------------
    log.info("Encoding memory slots with %r ...", args.encoder)
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(args.encoder)

    class _Enc:
        dimension = st.get_sentence_embedding_dimension()

        @staticmethod
        def encode(texts_):
            return st.encode(texts_, convert_to_numpy=True, show_progress_bar=False)

    vectors = {r["question_id"]: encode_texts(_Enc, r["memory_texts"])
               for r in records}

    store_path = out / "memory_vectors.npz"
    sha = save_memory_store(store_path, vectors, {
        "memory_source": args.memory_source,
        "encoder": args.encoder,
        "max_slots": args.max_slots,
        "doc_chars": args.doc_chars,
        "distractor_frac": args.distractor_frac,
        "require_base_failure": bool(args.require_base_failure),
        "base_failure_metric": args.base_failure_metric if args.require_base_failure else None,
        "base_failure_max": args.base_failure_max if args.require_base_failure else None,
        "source_results": args.results,
        "arm": args.arm if args.memory_source == "retrieved" else None,
        "seed": args.seed,
        # No graph encoder is in this path. When one is trained and added, it is
        # recorded here so a run manifest states what produced its memory.
        "gnn": "off",
    })
    log.info("Wrote %s  (%d questions, d=%d, sha256=%s)",
             store_path, len(vectors), _Enc.dimension, sha[:16])

    (out / "split_manifest.json").write_text(json.dumps({
        "source_results": args.results, "arm": args.arm, "seed": args.seed,
        "memory_source": args.memory_source,
        "require_base_failure": bool(args.require_base_failure),
        "distractor_frac": args.distractor_frac,
        "encoder": args.encoder,
        "memory_store": str(store_path),
        "memory_store_sha256": sha,
        "test_frac": args.test_frac, "n_train": len(train), "n_test": len(test),
        "train_question_ids": sorted(train_ids),
        "test_question_ids": sorted(test_ids),
    }, indent=2), encoding="utf-8")
    log.info("Wrote split manifest. Evaluate ONLY on test.jsonl question ids.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
