# Gate 1 Spec — Does TAHI's graph beat plain text search?

**Status:** spec, not implemented.
**Author:** Claude, from sources cited inline. Approved by: _(pending Rich)_
**Rule this document exists to satisfy:** research → sources → written spec → implementation.
Every parameter below is either quoted from a source or explicitly flagged as a choice
with the person who made it.

---

## 0. Sources

| # | Source | Used for |
|---|---|---|
| S1 | [GraphRAG-Bench paper, arXiv:2506.02404](https://arxiv.org/html/2506.02404v1) (v1 Jun 3 2025, v3 Jun 20 2025 latest) | standardised model + chunk size, baseline scores |
| S2 | [GraphRAG-Bench repo](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark) — `Evaluation/`, `Examples/` | eval harness, output format, run commands |
| S3 | `Examples/run_lightrag.py` (vendored to scratchpad) | exact output record schema, retrieval params |
| S4 | [LightRAG paper, arXiv:2410.05779](https://arxiv.org/html/2410.05779v1) + [DeepWiki pipeline](https://deepwiki.com/HKUDS/LightRAG/2.2-document-processing-pipeline) + [Neo4j teardown](https://neo4j.com/blog/developer/under-the-covers-with-lightrag-extraction/) | how graph construction is actually done |
| S5 | `Evaluation/README.md` (vendored) | which metric applies to which question type |

Vendored copy: `third_party/graphrag_bench_eval/`. Now complete — the earlier vendoring
was **missing** `indexing_eval.py`, `metrics/evidence_recall.py`, `metrics/utils.py`,
`metrics/context_relevance_v2.py`, and `llm/ollama_client.py`. All now present.

---

## 1. The dataset (verified locally, not from memory)

`data/graphrag_bench/medical_questions.json` — **2,062 questions**, all `source: "Medical"`.

| question_type | n | share |
|---|---:|---:|
| Fact Retrieval | 1,098 | 53.2% |
| Complex Reasoning | 509 | 24.7% |
| Contextual Summarize | 289 | 14.0% |
| Creative Generation | 166 | 8.1% |

Per-question fields: `id, source, question, answer, question_type, evidence, evidence_relations`.

`evidence` and `evidence_relations` are the answer key for **Step 2** — they state the facts
required to answer, so graph quality is measurable without any judgement from me.

---

## 2. Which LLM, and why not the DGX

S1 §experimental setup: *"To ensure a fair comparison across all methods, we adopted the
same GPT-4o-mini as the default large language model."* Chunk size *"consistently set to
1200 tokens."*

An LLM appears in four places. They do **not** all have the same answer:

| Role | Model | Why |
|---|---|---|
| Graph construction | `gpt-4o-mini` | S1 standardises it. A bigger extractor would confound "TAHI is better" with "our extractor is better". |
| Generation (all 3 arms) | `gpt-4o-mini` | same, and it is also the `base` arm's published score |
| Judge | `gpt-4o-mini` | S1 uses it as judge; ~43k calls makes local infeasible on a GB10 |
| Embeddings | `BAAI/bge-large-en-v1.5`, dim 1024 | **local already** — S2/S3 never use OpenAI embeddings |

**The DGX is supported and is not wasted.** S2 ships `Evaluation/llm/ollama_client.py` and
every runner takes `--mode ollama --llm_base_url http://localhost:11434` (default model
`qwen2.5:72b`). Use it for **iteration** — rebuilding the graph while fixing extraction is
free locally and would otherwise be paid API calls each pass. The *reported* run uses
`gpt-4o-mini` for comparability. Nothing local is currently loaded except `nomic-embed-text`.

**Cost of the reported run:** graph ~$0.12; generation 3 arms × 2,062 q; judging ~43k calls.
Estimate **$15–25 total**.

---

## 3. What we are actually up against

S1 Table 4, accuracy on the CS/textbook split:

- vanilla `gpt-4o-mini`, no retrieval: **70.68%**
- RAPTOR (best method): **73.58%**

**The whole effect is ~3 points.** This is the single most important number in this document.
It sets the bar for what counts as a result and means noise control matters more than
headline chasing. S1's own finding is only that *"most GraphRAG methods still outperform
traditional RAG baselines"* — not that they do so dramatically.

---

## STEP 1 — Build the graph

### 1.1 How LightRAG actually does it (S4)

1. Chunk the corpus.
2. One LLM call per chunk. Extract **entities** (`entity_name`, `entity_type`,
   `entity_description`) and **relations**. The prompt carries a "Knowledge Graph Specialist"
   system persona, configurable entity types, and few-shot examples.
3. **Gleaning** — call the LLM again, *more aggressively*, asking what it missed. Default
   `DEFAULT_MAX_GLEANING = 1` extra pass. New findings are appended. Stops if input exceeds
   `DEFAULT_MAX_EXTRACT_INPUT_TOKENS = 20480`.
4. **Merge** — the same entity from different chunks becomes one node. Descriptions are
   combined by map-reduce summarisation.

Critically (S4): entity types are *"a default set of categories … to guide the LLM"* —
**guidance, not a filter.** LightRAG does not reject an extraction for having an
unlisted type.

### 1.2 What `scripts/build_corpus_graph.py` does today, and why it is wrong

| | current | required | source |
|---|---|---|---|
| Chunking | 700 words / 80 overlap | **1200 tokens** | S1 |
| Gleaning | none | **1 extra aggressive pass** | S4 |
| Schema | hand-typed, `:183` hard-rejects non-conforming triples | **guide only, never reject** | S4 |
| Entity merge | none | merge by name across chunks | S4 |

The schema rejection is the worst of the four. The hand-typed `SCHEMA` at `:49-60`
**omits `metastasizes_to`**, which `data/graphrag_bench/derived_schema.json` shows is the
**most frequent relation in the dataset (109 sentences)**. As written, the build silently
discards every metastasis fact. This is an author-chosen constraint, not a data property —
same failure class as the MetaQA `node_cap` (see `TAHI_ENDGAME_PLAN.md` §0.2).

### 1.3 Spec

- Chunk at **1200 tokens** with overlap; tokeniser must be recorded in the manifest.
- Prompt seeded with `derived_schema.json` kinds/relations **as suggestions**. Model may
  emit others. **No conformance rejection anywhere.**
- One gleaning pass, aggressive re-ask, append new findings only.
- Merge nodes by normalised entity name; keep a merge count.
- **Log** every non-schema relation emitted, with counts. If the model invents relations
  in volume, that is a finding to report, not something to suppress.

### 1.4 Output artifacts

- `graph.graphml` — **required**, because `indexing_eval.py --framework graphml` reads it
  and gives us their structural metrics for free.
- `graph.json` — nodes/edges with `source_chunk_id` provenance on every edge.
- `manifest.json` — model, chunk size, tokeniser, prompt hash, counts, cost, timestamp.

---

## STEP 2 — Test the graph, before TAHI touches it

**This step was missing from the earlier plan. It was added at Rich's instruction and it
gates Step 3.** A bad graph makes Step 3 uninterpretable, and nothing in Step 3 would
distinguish a bad graph from a bad retriever.

### 2.1 Their metric, not mine

`Evaluation/metrics/evidence_recall.py` (S2) — `compute_evidence_recall(question, contexts,
reference_evidence, llm)`. Feeds gold `evidence` and the retrieved context to an LLM and asks,
per evidence item, whether it is attributable. Returns attributed/total.

Run it with **the graph's facts as `contexts`** to ask directly: *are the required facts in
the graph at all?* This is the ceiling on Step 3 — no retriever can exceed it.

### 2.2 Structural metrics, also theirs

```shell
python -m Evaluation.indexing_eval --framework graphml \
  --base_path <graph dir> --output results/indexing_metrics.txt
```
Gives density, connectivity, clustering, component sizes. Comparable to published graphs.

### 2.3 Cheap non-LLM check, run first

String/alias match of gold `evidence_relations` entities against graph node names. Costs
nothing, catches a catastrophically bad build before spending anything on 2.1.

### 2.4 GATE

**Report evidence recall before running Step 3. If the required facts are not in the graph,
stop and fix Step 1.** No threshold is set here — I am not choosing another undisclosed
number. The value gets reported, and Rich decides whether it clears.

---

## STEP 3 — Test TAHI and score

### 3.1 Arms

| arm | retrieval | role |
|---|---|---|
| `base` | none | S1 reports 70.68% for this; a sanity check on our harness |
| `vector_rag` | BGE dense over the same chunks | **the thing to beat** |
| `tahi_graph` | TAHI over the Step 1 graph | the claim |

Identical model, questions, prompt, and `top_k` across all three. Only retrieval varies.

### 3.2 Retrieval params (S3 `run_lightrag.py`)

`retrieve_topk=5`, `max_token_for_text_unit=4000`, `max_token_for_local_context=4000`,
`max_token_for_global_context=4000`.

### 3.3 Output format — exact, from S3 `run_lightrag.py:222-231`

```json
{
  "id": "...", "question": "...", "source": "Medical",
  "context": "...", "evidence": "...", "question_type": "...",
  "generated_answer": "...", "ground_truth": "..."
}
```

⚠️ **Inconsistency in their own code, flagged not silently patched:** `retrieval_eval.py:165`
reads `item['gold_answer']` and expects the file **grouped by question_type**, while
`run_lightrag.py` writes a flat list with `ground_truth`. Emit both keys and provide a
grouped variant. Record this in the manifest as a compatibility shim.

### 3.4 Metrics per question type (S5, verbatim)

| question_type | metrics |
|---|---|
| Fact Retrieval | ROUGE-L, Answer Correctness |
| Complex Reasoning | ROUGE-L, Answer Correctness |
| Contextual Summarize | Answer Correctness, Coverage |
| Creative Generation | Answer Correctness, Coverage, Faithfulness |

Do not average across types. **Per-type is the result**; the aggregate hides everything,
and with a ~3 point total effect (§3) it would hide the effect too.

### 3.5 Commands (S5, verbatim)

```shell
export LLM_API_KEY=...
python -m Evaluation.generation_eval --mode API --model gpt-4o-mini \
  --base_url https://api.openai.com/v1 --embedding_model BAAI/bge-large-en-v1.5 \
  --data_file ./results/tahi.json --output_file ./results/eval_tahi.json

python -m Evaluation.retrieval_eval  --mode API --model gpt-4o-mini \
  --base_url https://api.openai.com/v1 --embedding_model BAAI/bge-large-en-v1.5 \
  --data_file ./results/tahi.json --output_file ./results/eval_tahi_retrieval.json
```

Note `LLM_API_KEY`, not `OPENAI_API_KEY`.

---

## 4. Deliverable

One table: three arms × four question types × their metrics, plus the S1 published numbers
alongside. Plus Step 2's evidence recall, which says whether the table means anything.

## 5. Rules for this run

1. Every metric comes from `third_party/graphrag_bench_eval/`. **No metric written by me.**
2. Every threshold, cap, or filter is named in this doc with who chose it.
3. Nothing is rejected silently — extractor output that fails a schema gets **logged**.
4. Step 2's number is reported before Step 3 runs.
5. All three arms share one generation path; retrieval is the only difference.

## 6. Open, not decided by me

- Does Step 2's evidence recall clear? (report, then Rich rules)
- Does `vector_rag` chunk identically to the graph build? *Recommend yes* — otherwise a
  difference could be chunking rather than structure.
- Sample size for a pilot before the full 2,062.

---

## 7. ReasonEmbed Integration & Future Extensions (`arXiv:2510.08252v2`)

Based on our analysis of *ReasonEmbed: Enhanced Text Embeddings for Reasoning-Intensive Document Retrieval* (BAAI / USTC, Oct 2025 / Feb 2026), the following 4 technical enhancements are incorporated into TAHI's roadmap:

### 7.1 Upgrading Base Vector Retriever to ReasonEmbed
- **Current Baseline**: `BAAI/bge-large-en-v1.5` or `all-MiniLM-L6-v2` in `src/tahi/retrieval/ann.py`.
- **Planned Upgrade**: Upgrade the dense text encoder to `ReasonEmbed-Qwen3-4B` / `ReasonEmbed-Qwen3-8B` (`github.com/VectorSpaceLab/agentic-search`), which yields a published +10.95 nDCG@10 lift over standard BGE on reasoning-intensive medical retrieval (R2MED).

### 7.2 ReMixer Non-Source Candidate Mining (Eliminating Triviality Shortcuts)
- **Finding**: Training GCCA or text embeddings where positive targets are direct source chunks creates a trivial ROUGE keyword-matching shortcut, causing performance to drop from $37.1 \rightarrow 16.1$ nDCG.
- **Protocol**: When building GCCA training data (`scripts/build_gcca_training_data.py`), explicitly **exclude direct source text chunks** and use 2-hop graph neighbor subgraphs as positive targets to force true topological reasoning.

### 7.3 Reasoning Intensity (RI) Weighting for GCCA Training
- **Protocol**: Implement Redapter self-adaptive loss weighting in `scripts/train_gcca.py`:
  $$\text{RI} = \mathcal{L}(q, \text{Memory}) - \mathcal{L}(q_{\text{graph\_reasoning}}, \text{Memory})$$
  Queries where graph-expanded reasoning significantly lowers loss receive higher gradient weights, preventing adapter saturation on simple lookups.

### 7.4 Benchmark Target Alignment
- Use BRIGHT and R2MED medical benchmarks alongside GraphRAG-Bench as primary published reference targets for TAHI's Property Graph retrieval.


---

# APPENDIX A — Leakage measurement (measured 2026-08-05)

## A.1 The finding

How much of each gold answer is already present, verbatim, in that question's own gold
`evidence`. Token-level, measured on all 2,062 questions:

| question_type | n | answer tokens present in evidence | ≥90% overlap |
|---|---:|---:|---:|
| Fact Retrieval | 1,098 | **92.5%** | **69%** |
| Complex Reasoning | 509 | 86.4% | 37% |
| Contextual Summarize | 289 | 54.1% | 19% |
| Creative Generation | 166 | 63.2% | 5% |

**Fact Retrieval is 53% of the benchmark and is essentially copy-paste.** For 69% of those
questions the answer is ≥90% contained in a single evidence passage. Find the paragraph,
echo it, score.

## A.2 Prediction, recorded before the run

Written down in advance so it cannot be rationalised after the fact:

> **Plain vector search will be strong on Fact Retrieval, and the graph will gain little or
> nothing there.** If TAHI earns anything, it will be on Complex Reasoning and Contextual
> Summarize, where the answer is not sitting in one passage.

If TAHI *does* show a large Fact Retrieval gain, that is a signal to look for a bug or a
leak, not a cause for celebration.

## A.3 Consequence for reporting

A single averaged score would be dominated by the half of the benchmark where structure
cannot help — 53% of questions pulling the mean toward "no difference." Per-question-type
reporting (§3.4) is therefore **required, not preferred**.

## A.4 Leakage checks still to run

- **`base` arm memorisation** — gpt-4o-mini scores ~70% with no retrieval on S1's split.
  Some of this corpus may be in its pretraining. The `base` arm partly measures this.
- **Graph-build leakage** — if the extractor writes whole evidence sentences into node or
  edge `description` fields, the graph becomes a paraphrase of the corpus and "graph
  retrieval" is text retrieval with extra steps. Check description length against source
  sentence length; report the distribution.

Background on why this matters: RETRO's authors concede *"Retro models exploit leakage more
strongly than baseline models"*; Norlund et al. (Findings of EACL 2023) argue the effect is
larger than RETRO's own leakage-aware evaluation allows. Contested, which is exactly why we
measure our own rather than trusting a convention.

---

# APPENDIX B — ReasonEmbed amendment (proposed, not approved)

**Source:** [ReasonEmbed, arXiv:2510.08252v2](https://arxiv.org/html/2510.08252v2)
**Status: PARKED. Not in scope for Gate 1.** Decided by Rich, 2026-08-05: run Gate 1 with the
three arms in §3.1 first, then revisit. Nothing in this appendix changes the Gate 1 build,
the Gate 1 arms, or the Gate 1 numbers. It is recorded here so the reasoning survives; it is
not a work item.

## B.0 What it is

An embedding model for **reasoning-intensive retrieval** — cases where relevance requires
reasoning rather than surface or semantic matching. Two components:

- **ReMixer** (data synthesis): identifies *"triviality as the key bottleneck"* in synthetic
  training data. Mitigates it with **source-excluded candidate mining** — the original source
  document is excluded when mining positives, forcing relevance beyond surface pattern match.
  82K samples, mean query length 221 tokens.
- **Redapter** (self-adaptive training): defines **reasoning intensity (RI)** as the ratio of
  loss with and without a reasoning-augmented query, then weights training by it
  (`RI-InfoNCE`).

Results: BRIGHT nDCG@10 **38.1** (Qwen3-8B), ~10 points over prior SOTA. **R2MED healthcare,
out-of-domain: 43.18.**

Note that SOTA on BRIGHT being 38.1 means **reasoning-intensive retrieval is largely unsolved
by anyone.** That is both the headroom and the warning.

## B.1 A fourth arm — because ReasonEmbed competes with the graph thesis

ReasonEmbed claims reasoning-intensive retrieval is solvable with **a better encoder alone** —
no graph, no traversal, no structure. Its strongest out-of-domain result is on a **healthcare**
benchmark. That is our corpus.

Therefore:

| arm | retrieval |
|---|---|
| `base` | none |
| `vector_rag` | BGE-large-en-v1.5 (benchmark standard, S1) |
| **`vector_rag_reasonembed`** | **ReasonEmbed — the honest opponent** |
| `tahi_graph` | TAHI |

Rationale: BGE is a 2023 general-purpose encoder being asked to do reasoning retrieval it was
not built for. **Beating BGE would measure the encoder, not the graph.** If TAHI cannot beat
ReasonEmbed-powered dense retrieval on Complex Reasoning, the graph is adding nothing a better
encoder does not already provide — and that is a genuine result worth publishing.

⚠️ **Hard constraint:** ReasonEmbed must never be used in the `tahi_graph` arm alone. That
would be "graph + strong encoder vs text + weak encoder" — exactly the confound this document
exists to prevent. Either every arm gets it or only its own arm does.

**Cost:** none to the API budget. Qwen3-4B / Qwen3-8B variants run on the DGX. This is a
well-motivated local workload.

## B.2 Borrow reasoning intensity as a measurement instrument (recommended, low risk)

RI gives a **per-question score for how much reasoning a question actually requires**,
computed rather than labelled.

Currently we rely on the benchmark's own `question_type` labels. RI lets us stratify by
measurement and ask the sharper hypothesis:

> **Does TAHI's advantage grow with reasoning intensity?**

A flat line across RI means the graph is not doing what it claims, whatever the headline
number says. A rising line is a **dose-response curve**, which is substantially harder to
produce by accident than a single delta — and would be the strongest form this result could
take.

It also independently cross-checks the benchmark's labelling, which §1 currently treats as
ground truth.

## B.3 Adopt source-excluded mining as leakage control (recommended, low risk)

ReMixer's source-exclusion is a **published** technique for exactly the disease measured in
Appendix A. Use it when constructing any non-leaky evaluation subset, rather than inventing a
filter here. Consistent with Rule 1: prefer someone else's instrument.

## B.4 Rejected: ReasonEmbed for encoding graph paths

Plausible — TAHI must embed nodes and paths — but ReasonEmbed is trained on ~221-token
natural-language queries paired with documents, not on triples. **Transfer is unknown and
unmeasured.** Do not build on it.

## B.5 Open, for Rich

- Approve B.1 (fourth arm)? It makes Gate 1 materially harder to pass. That is the point,
  but it is a real choice, and it is Rich's, not mine.
- B.2 and B.3 are methodology-only. Recommend adopting both regardless of B.1.
