# OCTO Endgame — Plan of Action

**Updated:** 2026-08-04 — GCCA deferred; GraphRAG-Bench adopted as the primary
benchmark. Previous revision 2026-08-03 (reordered after the train/eval
asymmetry was found).
**Objective:** Take OCTO to a definitive verdict — validated success or validated
failure. Every gate has a failure branch that ends the project *with a
publishable result* rather than another round of remediation.

**Standing rule:** the pre-registration for a gate is committed before that gate
is run.

**Standing rule (added 2026-08-04):** any threshold, cap, or filter that can
change a reported number is named in this document with the person who chose it.
The §0.2 audit exists because unnamed defaults were reported as findings.

---

## 0.1 Decision log

| Date | Decision | Decided by |
|---|---|---|
| 2026-08-04 | **GCCA is deferred.** The core claim is tested with retrieved facts in context, as KiRAG/BDTR/IRCOT do. GCCA returns afterwards as an *efficiency* claim — equal accuracy at lower context cost — not an accuracy claim | Rich |
| 2026-08-04 | GraphRAG-Bench Medical is the primary benchmark; its shipped evaluation harness is the instrument | Rich |
| 2026-08-04 | Extraction schema is derived from the benchmark, not authored here | Rich |

### Why GCCA moved

Every OCTO result that survived audit is retrieval- or prompt-side; GCCA
contributed to none of them. It is also the most expensive and least
interpretable component, its adapter needs retraining after the memory-symmetry
fix, and it is currently *unjudged* — the "gate never opened" verdict rested on
an `α > 0.10` threshold this author invented and presented as pre-registration.

Positioning it as an accuracy mechanism was the error. Its real advantage is
cost: graph retrieval returns hundreds of facts, stuffing them burns context
linearly per query forever, and a memory tensor is fixed-width regardless. That
claim needs the context-injection arm to exist first, as the baseline to beat.

## 0.2 Author-chosen knobs that were reported as findings

Measured 2026-08-04, `scripts/ablate_metaqa_retrieval.py`, n=300 MetaQA 3-hop:

| Knob | Chosen by | Effect |
|---|---|---|
| `node_cap = 200_000` in `MetaQAGraph.walk` | this author, undisclosed | Sole cause of the "16.6% of gold is unreachable — a hard ceiling" claim. With it off, recall is **100.0%**. It truncates silently and returns partial results |
| `target_kind` hard filter | this author, undisclosed | Gold spans more than one node kind on **129/300** questions, so a single-kind filter cannot be correct regardless of value |
| `allowed_relations` hard filter | this author, undisclosed | Transplanted from the Hetionet planner, where discarding is correct because the task is disambiguation. On multi-relation path queries it is a pruner driven by a lossy cue matcher. Every paper in the reading list says rank, then cut |
| `seen_pairs` dedup by `(node, hop)` | this author, undisclosed | `walk` records one path per endpoint, so the ranker's max-over-paths was a no-op — it scored arbitrary path evidence |
| `α > 0.10` GCCA pass threshold | this author, presented as pre-registration | α is in the spec; the threshold is not. GCCA is unjudged, not failed |

**Voided by the above:** all MetaQA filter-vs-rank numbers from 2026-08-04
(filter 48.8/30.7, rank@5 44.7/46.1, blind 83.4).

---

## 0. Current state — what is real

Verified by running code, not asserted:

| Status | Item |
|---|---|
| ✅ | Identity control: α=0 reproduces base token-for-token, 0 mismatches, n=500 |
| ✅ | Length-matched decoding: 10.4 output tokens across base / α=0 / trained |
| ✅ | `rag_prompt` > `base`: +0.0528 token-F1, CI [+0.0378, +0.0675] |
| ✅ | 4-arm harness, paired bootstrap CIs, fail-loud manifests |
| ✅ | Relation-index determinism (md5); duplicate `build_memory_tensor` removed |
| ✅ | 722/722 gold documents resolve; 466 questions survive the base-failure filter |
| ❌ | The 2026-08-03 L3 result is **VOID** — see §1 |
| ❌ | RGAT: untrained, no training script, never validated against any baseline |
| ❌ | NLI instrument: no window overlap, no batching, max-pool inflates false positives |
| ⬜ | Gate B (Tier 0 multi-hop): only 8K sample files exist |

## 1. Why the 2026-08-03 run is void

`train_gcca.py` encoded `memory_texts` with SentenceTransformer directly.
`run_l3_native.py` built memory via `build_memory_tensor` and — once the RGAT
landed — passed it through a **randomly-initialised** `SubgraphRGATEncoder`
(no checkpoint; no GNN training script exists). The adapter was trained on one
representation and scored on a random projection of it.

The reported `-0.0117` token-F1 delta therefore describes that mismatch, not the
architecture. It is not evidence about salient span masking, and the "α grew to
0.0426 and injected noise" story is untested and confounded.

**Fixed structurally, not by convention:** `src/octo/native/memory_store.py`
computes memory vectors once, writes them with a content hash, and both sides
read the same bytes. `tests/test_memory_symmetry.py` asserts bit-identity.

---

## 2. GATE 1 — Does the graph help generation? *(primary; pre-registration pending)*

The claim, stated so it can fail: *retrieved graph facts placed in context make
the model assert more true things and fewer false ones than vanilla RAG on the
same corpus.* No architecture change. This is what KiRAG (arXiv 2502.18397),
BDTR and IRCOT do, and it is why their numbers are comparable to each other.

**Benchmark:** GraphRAG-Bench Medical (arXiv 2506.02404, ICLR'26) — NCCN
oncology guidelines, 174,610 words of prose, 2,062 questions with gold answers.

**Instrument: the benchmark's own harness**, vendored at
`third_party/graphrag_bench_eval/`. `coverage.py`, `faithfulness.py`,
`answer_accuracy.py`, `context_recall.py`, `context_relevance.py`.

Adopting it rather than writing one is the point. Every previous OCTO cycle died
on a self-authored metric — `fact_coverage` moved 0.0000 under negation, the NLI
judge scored +0.826 whether or not the evidence supported the claim. These
metrics are LLM judges and carry that family's known weakness, demonstrated here
already (LLM claim extraction: 9/9 on real entities, 3/9 on invented ones). The
mitigation is not that the instrument is good; it is that it is **shared** —
LightRAG, HippoRAG2 and fast-graphrag are scored by this exact code, the bias
falls identically on every arm, and this author cannot tune it or replace it
when a number disappoints.

`coverage` — "what percentage of reference facts are covered in the response" —
is the completeness claim (pharma, national security, enterprise) as the
benchmark's own metric rather than an OCTO invention.

**The differential is the result, not the headline number.** `question_type` is
labelled: Fact Retrieval 1,098 / Complex Reasoning 509 / Contextual Summarize
289 / Creative Generation 166. If OCTO is real, it should gain materially on
Complex Reasoning and little on Fact Retrieval. A uniform lift across all four
is a leak, not a win, and must be investigated before reporting.

**Prior to beat:** the benchmark's own finding is that GraphRAG *frequently
underperforms vanilla RAG*. The null is well supported and the authors built the
dataset to expose it.

### 2.1 Schema — derived, not authored

`scripts/derive_graphrag_schema.py` mines `evidence_relations`; 174 of 2,062
questions name "the ontology" outright, and the paper describes a schema layer
of `(head type, relation, tail type)` — the same shape as Hetionet's metagraph
and what `QueryPlanner` already consumes.

The hand-authored schema in `scripts/build_corpus_graph.py` is **not to be
used**: it omits `metastasizes_to`, which is the most frequent relation in the
benchmark's evidence (109 sentences), and schema conformance at line 183 would
have silently dropped every metastasis fact into `schema_rejected`. It also
misses `Biomarker`, `Prognostic Factor`, `Tumor Characteristic`, `Supportive
Care` and `Surveillance`.

### 2.2 Arms

| Arm | Retrieval | Purpose |
|---|---|---|
| `base` | none | Parametric floor |
| `vector_rag` | dense chunks over the same corpus | The thing to beat; the benchmark says it usually wins |
| `octo_graph` | plan → link → typed graph retrieval → facts in context | The claim |

Same generator, same decoding parameters, same instruction template across arms.
The C-vs-E prompt confound (one arm "Answer using only…", the other "List
every…") already invalidated one comparison; templates are shared code, not
copied strings.

### 2.3 Retrieval settings — open, and to be decided jointly

Per §0.2 these are not this author's to pick silently: whether the type filter
survives at all (129/300 says no), what replaces `node_cap`, and whether the
ranker sees every path per endpoint or one.

---

## 3. GATE 2 — GCCA as an efficiency claim *(deferred; runs only after Gate 1)*

Reframed per §0.1. The question is **not** "does GCCA improve accuracy" but
"does a fixed-width memory tensor hold Gate 1's accuracy at materially lower
context cost." That needs Gate 1's `octo_graph` arm as its baseline, and it is
uninterpretable without it.

The oracle-memory pre-registration below is preserved for when that happens.
Its `α > 0.10` band is **withdrawn** — see §0.2. A replacement threshold must be
justified from the spec or from measurement, not asserted.

### 3.1 (preserved) Can GCCA use a *perfect* memory? *(pre-registration)*

The decisive architecture test. The prior null is uninterpretable because three
explanations were live at once: (a) GCCA cannot exploit memory, (b) the memory
held nothing (`doc_recall` 0.0395), (c) train and eval saw different
representations. §1 removed (c); oracle memory removes (b); (a) is what remains
to be measured.

### 3.2 Conditions

| Setting | Value | Why |
|---|---|---|
| Memory source | **oracle** — `expected_doc_ids` | Zero noise; the answer is in memory by construction |
| Distractors | **0.0** | Gate A asks whether the gate opens under ideal input |
| Graph encoder | **off** | The RGAT is untrained; "on" injects a random projection and re-creates the §1 confound |
| Base-failure filter | `token_f1 < 0.5` on `base` | Removes items answerable from parametric memory, where a shut gate is the correct optimum |
| Encoder | `all-MiniLM-L6-v2` (d=384) | Must match the store; the loader refuses a mismatch |
| Decoding | `--max-new-tokens 35`, length-matched | The +0.1398 → −0.0016 collapse was a pure verbosity confound |
| Split | stratified, seed 0, `test_frac=0.3` | Evaluate **only** on `test.jsonl` ids |
| Statistics | paired bootstrap, 10,000 resamples, seed 0 | |

Measured in advance: 466 questions qualify → ~326 train / ~139 test.

Recorded in advance: the base-failure filter keeps 466 of 470. It is nearly a
no-op because the base model already fails almost everything (F1 = 0.075). The
lever here is **oracle memory**, not the filter — do not report the filter as a
cause of any outcome.

### 3.3 Primary readout

**`max |tanh(α)|` over the 7 GCCA gates at the final epoch**, logged every epoch.

α is the mechanism. If it does not move, nothing downstream can be attributed to
memory whatever the accuracy does. Baselines from the void run: 0.0199 (epoch 2),
0.0426 (epoch 14).

### 3.4 Secondary readout

`l3_trained` vs `base` on token_f1 and exact_match, held-out ids, paired
bootstrap CI. Deliberately **not** `nli_fact_coverage` — that instrument is not
yet trustworthy enough to carry a gate (§4).

### 3.5 Decision bands — **the α band is WITHDRAWN, see §0.2**

| Verdict | Criterion | Consequence |
|---|---|---|
| **PASS** | `max abs(tanh(α))` > **0.10** AND `l3_trained` > `base` on token_f1, CI excludes zero | The bridge works; memory quality is the bottleneck. Fixing retrieval becomes the priority |
| **INCONCLUSIVE** | α in **[0.05, 0.10]**, or α > 0.10 with an accuracy CI including zero | The gate moves but does not pay. Do **not** retune and rerun without a new pre-registration |
| **FAIL** | `max abs(tanh(α))` < **0.05** | GCCA cannot exploit even ideal noise-free memory. **OCTO L3 is dead, and RETRO-v2's Claim A is damaged with it.** Publish the negative |

### 3.6 Validity gates — the run is VOID, not negative, if any hold

A void run is discarded and rerun; a negative run is published. Confusing the
two is how this project accumulated retractions.

1. `identity_control_passed` false, or mismatches > 0
2. Memory-store sha256 in the checkpoint ≠ the one in the benchmark manifest
3. `encoder_is_fallback` true, or `strict_mode` false
4. Mean memory slots = 0, or `memory_is_informative` fails on any item
5. Output-token means differ > 10% across base / α=0 / trained
6. Any test question id appears in `train.jsonl`

### 3.7 Run

```bash
.venv/bin/python scripts/build_gcca_training_data.py \
    --results benchmarks/results/l3_native_run.json \
    --questions data/enterprise_rag/questions.jsonl \
    --corpus data/enterprise_rag/sources \
    --memory-source oracle --require-base-failure \
    --out-dir data/gcca_oracle

.venv/bin/python scripts/train_gcca.py \
    --data data/gcca_oracle/train.jsonl \
    --memory-store data/gcca_oracle/memory_vectors.npz --epochs 15

.venv/bin/python benchmarks/run_l3_native.py \
    --checkpoint checkpoints/gcca/gcca_epoch14.pt \
    --memory-store data/gcca_oracle/memory_vectors.npz \
    --question-ids-from data/gcca_oracle/test.jsonl \
    --gnn off --output benchmarks/results/gate_a_oracle.json
```

---

## 4. GATE 3 — Tier 0 multi-hop (was Gate B)

Only if Gate A passes. `docs/archive/retro-v2-review.md` §6 named this as step
one; the project jumped to Tier 2 instead.

Four arms on HotpotQA / MuSiQue / 2WikiMultiHopQA: `base`, `single_shot_rag`,
`iterative_rag`, `octo_graph`. n ≥ 200 per dataset. The repo has scaffolding in
`implementations/{hotpotqa,musique,frames}/` but only 8K sample files.

These datasets carry **sentence-level supporting-fact labels** — a faithfulness
ground truth OCTO has never had, and one that does not need an NLI judge.

| Outcome | Action |
|---|---|
| **PASS** — iterative or graph beats single-shot, CI excludes zero | Continuous retrieval validated. Proceed |
| **FAIL** — neither beats single-shot | Re-retrieval does not help this task class. **Both OCTO and RETRO-v2 lose their foundation.** Publish |

Secondary read: if `octo_graph` matches `iterative_rag`, structured retrieval is
validated *and* the chunk representation is shown unnecessary — the ablation
`retro-v2-review.md` §3.5 asked for.

---

## 5. Instrument repair — superseded for Gate 1 by the vendored harness

`src/octo/eval/nli_evaluator.py` now windows at 200 words and max-pools, which
fixed the measured support-invariance (gap 0.000 → 0.485). Remaining defects:

- Windows do not overlap (`range(0, len(words), max_words)`), so a fact split
  across a boundary is lost from both
- `score_batch` is a Python loop over `score_pair` — no real batching
- No `instrument_spec()`, so window size and stride are not pinned in manifests
- Max-pooling inflates false positives with window count: unsupported evidence
  at ~1900 tokens still scores +0.490

This was Phase 0 and blocked everything. It does not: Gate A reads α and
token-F1, neither of which touches NLI. Do it before Gate D.

---

## 6. GATE 4 / GATE 5 (were Gate C / Gate D)

Only if A and B pass.

**Gate C — can a truth layer be built?** Typed extraction with entity resolution
over ~30–50k documents (gold docs + dense top-50 + distractors), not the full
511,962. Single criterion: `supporting_fact_recall` rises from **0.0395 to
> 0.30**. Failure means the thesis fails on *economics*, not architecture — a
different and still publishable finding.

**Gate D — the full thesis.** Pre-registered separately. `nli_fact_coverage`,
`l3_trained` vs `rag_prompt`, n ≥ 200, length-matched, paired bootstrap.
SUCCESS ≥ +0.05 CI excluding zero; NULL if CI includes zero; FAILURE ≤ −0.05.
Publish regardless.

---

## 7. Do NOT do these before Gate 1 reports

| Item | Why |
|---|---|
| Train the RGAT | Pointless until the gate is shown to open at all |
| Adopt a biomedical KG (Hetionet/PrimeKG) | Genuinely promising, but it fixes *retrieval* — only relevant if Gate A passes |
| Cora / CiteSeer / PubMed | Verified: Planetoid ships **no text and no entity names**, only bag-of-words vectors and integer node ids. Usable as an RGAT correctness check against published baselines (GCN ≈81.5%, GAT ≈83.0% on Cora), not as a RAG comparison |
| Scale to 511,962 documents | `doc_recall` is the bottleneck, not corpus size |
| Move to a larger base model | It will not open a gate a 1.5B keeps shut for the same reason |
| Rewrite the investor narrative | Gate A changes the story in either direction |

---

## 8. The methods paper — parallel, no GPU

Independent of every gate, roughly 80% earned already:

- Identity control protocol (0 mismatches at n=500)
- The length control that killed the project's own headline (+0.1398 → −0.0016)
- `fact_coverage` negation delta of exactly 0.0000; ceiling 0.779
- NLI support-invariance past 512 tokens, and its window-count false-positive bias
- Admissibility: expanded candidates won 0/60 slots; required cosine > 1.0 in 45/60
- **Train/eval representation asymmetry (§1)** — a silent confound that produced
  a significant-looking negative result

See `docs/EVAL_METHODOLOGY_PAPER.md`.
