# MRAG — Prompt-RAG over the Milvus Substrate

**Working title:** MRAG (MAAILMA Retrieval-Augmented Generation)
**Author:** Rich (with Claude)
**Date:** 2026-08-05
**Status:** architecture proposal
**Relationship to MAAILMA:** this is **Arm B/C of the existing ablation matrix**
(`MAAILMA-master.md` §4), specified as a deployable architecture rather than only as a
baseline. It reuses the Stage 3–4 storage engine unchanged.

---

## 0. Why this document exists

`MAAILMA-master.md` §7 states the dependency plainly:

> **Claim A** — "GCCA produces better output than RAG" (the science)
> **Claim B** — "GCCA serves 1 PB at <2ms" (the systems)
> **B only matters if A is true.**

Claim A is tested at Stage 2 and is not yet settled. The out-of-core engine — Starling block
layout, Filtered-DiskANN topology, FreshDiskANN lifecycle — is Claim B work, and it is being
built now.

**This document specifies what that same engine serves if Claim A does not clear.** It is
insurance on the storage investment, not an argument against GCCA. If Claim A clears, MRAG
remains the honest baseline every GCCA result is measured against (Arm C), so the work is not
wasted in either branch.

---

## 1. The load-bearing observation

**The Milvus substrate is representation-agnostic.**

Per `the_machine/MILVUS_STATUS.md`, the vector layer is **Milvus** (MinIO on local NVMe for
object storage, etcd for metadata, Pulsar/Kafka for the write log). The hand-rolled
Starling and DiskANN3 designs are recorded there as **"superseded by Milvus decision."**

It is a sharded, filterable ANN index over 64-token chunks with a text payload. Nothing in
segment layout, index type, or the write path assumes the retrieved vectors are consumed by
cross-attention.

**Milvus already provides three things MAAILMA's master plan schedules as Stage 4
engineering:**

| MAAILMA Stage 4 layer | purpose | Milvus equivalent |
|---|---|---|
| Filtered-DiskANN | label-stitched metadata filtering | scalar filtering + partitions |
| FreshDiskANN | DRAM write buffer, async merge | growing/sealed segments + compaction |
| Starling | sector-aligned block layout | DISKANN index + mmap |

That is a large part of Claim B bought rather than built. The remaining Claim B work is
tuning and throughput at scale, not implementing the lifecycle from scratch.

| consumer | what it reads from the index |
|---|---|
| GCCA (Config 2) | neighbour **embeddings** → `W_K`/`W_V` → cross-attention |
| MRAG (this doc) | neighbour **text payload** → prompt |
| Verification layer (§6) | neighbour **text + chunk id** → claim check |

All three ride the same index. The engineering is shared; only the consumer differs.

---

## 2. What changes when the consumer is a prompt

This is the substantive part. Swapping the consumer relaxes the hardest constraints in the
Stage 4 design.

| requirement | GCCA | MRAG | consequence |
|---|---|---|---|
| Retrieval cadence | 1 query / 64 generated tokens | 1 query per request (Arm B) or 1 / 64 tokens (Arm C) | Arm B is ~8× fewer ops for a 500-token answer |
| Latency budget | **<2 ms**, inside the decode loop | ~50–100 ms, **before** decode starts | retrieval leaves the critical path |
| Blocking behaviour | every retrieval stalls token production | one prefetch, then generation runs uninterrupted | no async prefetch machinery required for Arm B |
| Payload read | embeddings (PQ codes / raw vectors) | **chunk text** (256 B/chunk) | text payload becomes load-bearing — see §5 |
| KV footprint | O(1), fixed 2m×k | O(L) — retrieved text occupies context | the one place GCCA is genuinely better |
| Model requirement | custom decode loop, trained adapters, frozen base | **any instruction-tuned model, unmodified** | serve on stock vLLM |
| Training cost | 1B–5B alignment tokens, adapter alignment per embedder change | **zero** | embedder swaps become a re-index, not a retrain |
| Citation | none — dense vectors leave no span | chunk id travels with the text | see §6 |

**The two that matter most operationally:**

1. **Latency moves off the critical path.** The `<2 ms` target is what forces io_uring, sector-
   aligned block shuffling, and speculative prefetch to all work perfectly at once. A single
   pre-generation lookup tolerates ordinary ANN latency. The Starling work still pays off — it
   raises QPS per node and cuts cost per query — but it stops being a correctness requirement
   and becomes an efficiency one.

2. **No adapter alignment.** `MAAILMA-master.md` §3.E: *"W_K and W_V must be re-initialised and
   re-aligned whenever the embedder changes."* Under MRAG an embedder upgrade is a re-index.
   That removes the coupling between retriever choice and model training entirely.

**Where GCCA genuinely wins, stated fairly:** O(1) KV footprint. MRAG pays context tokens for
every retrieved passage, and at high top-k on long generations that cost is real. If Claim A
clears, that is the reason.

---

## 3. Architecture

```
                        ┌────────────────────────────────────────┐
   ingestion            │  documents → late chunking (256/64)    │
                        │  → Nomic v2-MoE embed (d=768)          │
                        │  → composite key assembly              │
                        └────────────────┬───────────────────────┘
                                         │
  ═════════════════════════ SHARED SUBSTRATE — MILVUS ════════════════════════════════
                                         │
        ┌────────────────────────────────┴─────────────────────────────┐
        │  Index      DISKANN (cold/large) · HNSW or GPU CAGRA (hot)   │
        │  Storage    MinIO on local NVMe (S3-compatible)              │
        │  Metadata   etcd — segments, schema, cluster state           │
        │  Write log  Pulsar / Kafka — durable inserts and updates     │
        │  Filtering  scalar fields + partitions                       │
        │  Payload    PQ codes · raw vectors · CHUNK TEXT · chunk id   │
        └────────────────────────────────┬─────────────────────────────┘
                                         │
  ═══════════════════════════════════════╪═══════════════════════════════════════════
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                              │                              │
    ┌─────▼──────┐              ┌────────▼────────┐            ┌────────▼────────┐
    │   GCCA     │              │      MRAG       │            │  Verification   │
    │ (Config 2) │              │   (this doc)    │            │     (§6)        │
    │ embeddings │              │  text → prompt  │            │ text + chunk id │
    │ → W_K/W_V  │              │ → stock vLLM    │            │ → claim check   │
    └────────────┘              └────────┬────────┘            └────────▲────────┘
                                         │                              │
                                         └──────── generated answer ────┘
```

### 3.1 Retrieval path

Two-stage, reusing MAAILMA §3.H Strategy B (global MIPS then gist rescoring), which *"cannot
fall below plain global MIPS recall by construction"* — the safer of the two orderings:

1. **Filter scope** (optional) — Milvus scalar-field expression over tenant, source system,
   date range, security label; partitions where the split is static. More valuable to MRAG
   than to GCCA because enterprise queries are usually scoped, and a filter predicate that
   survives into a citation is human-readable.
2. **Candidate generation** — MIPS top-50 over the filtered scope.
3. **Rescore** — cosine against document gist / topic embedding; keep top-k.
4. **Payload fetch** — chunk text + chunk id for the surviving k.
5. **Assembly** — dedupe by parent document, order by score, pack to token budget.

### 3.2 Generation path

- **Arm B (single-shot).** One retrieval before decode. Stock vLLM, no custom loop. Default.
- **Arm C (matched cadence).** Re-retrieve every 64 generated tokens using the previous chunk as
  query, refresh the context block. This is MAAILMA's Config 1b — *"the strongest honest
  baseline; isolates injection mechanism from retrieval schedule."* It captures the "context
  drifts during reasoning" benefit GCCA claims, **without** adapters or a frozen-base
  constraint, at the cost of prompt reprocessing.

Arm C is the architecture that most directly threatens Claim A, which is exactly why
`MAAILMA-master.md` says *"If only one comparison in this document is run properly, it should be
1b vs. 2."*

### 3.3 What is deliberately absent

No graph-expanded retrieval. Measured on the full 511,962-document corpus (§7): graph expansion
**reduced** `doc_recall` by 0.0773, CI excluding zero. Dense retrieval over prose is the
retrieval layer. The graph's role is verification (§6), after generation, not before it.

---

## 4. Composite multi-aspect keys

MAAILMA §1 raises **semantic myopia** — a 64-token chunk has no awareness of its parent
document. This applies identically to MRAG, and the same mitigation works: composite keys
combining the local 64-token embedding, a document gist, and topic/subtopic taxonomy metadata.

Under MRAG the taxonomy component has a second use it does not have under GCCA: **the labels are
also the filter predicate** for Filtered-DiskANN, and they are human-readable in a citation. A
label attached to a retrieved chunk survives into the answer's provenance record. Under GCCA it
is consumed into a projection and disappears.

The Stage 2 Composite Multi-Aspect Key Evaluation therefore serves both architectures and should
be run regardless of how Claim A resolves.

---

## 5. Why the payload must stay prose — and the limits of that claim

**Scope note, stated first.** MAAILMA already budgets **chunk text payload at 256 B/chunk —
2.6 TB at 10¹⁰** (`MAAILMA-master.md` line 293). It does **not** propose replacing prose with
extracted triples anywhere. This section is therefore **not** a correction to their storage
design and should not be presented as one. It is recorded here for one reason: MRAG's
verification layer (§6) depends on prose payload being retained, and this is the evidence that a
triples-only representation would not substitute for it.

The measurement below is a property of **our extraction pipeline** (gpt-4o-mini, 1200-token
chunks, one gleaning pass, generic enterprise schema) on 403 documents. It is not a general
result about structured representations, and it does not generalise to 10¹⁰ chunks untested.

Oracle ceiling test, enterprise corpus, n=150 multi-document questions, both arms handed the
*identical* gold documents so retrieval quality is eliminated as a variable:

```
prose payload    token_f1 = 0.5142
triple payload   token_f1 = 0.3944
delta            −0.1198   95% CI [−0.1394, −0.1011]   excludes zero
```

Losing on all five question types; triples won on 13/150 questions. Failures are not phrasing —
the triple arm returns *"the context does not provide information"* because extraction discarded
the fact. One concrete case: extraction preserved a trace job ID and **dropped the file path from
the same sentence**.

**Conclusion, scoped:** for MRAG, the retrieved prose is what carries the answer, and the
verification layer in §6 needs that same prose to check claims against. A triples-only
representation of the retrieved material — at least as produced by this extraction pipeline —
does not carry enough to substitute. The 2.6 TB payload MAAILMA already budgets is the right
call; this is corroboration, not a change request.

Source: `data/enterprise_rag/oracle/oracle_results.json`, `scripts/run_oracle_ceiling.py`.

---

## 6. Verification layer — what MRAG can do that GCCA cannot

Under GCCA the retrieved content enters the residual stream as `W_V · e_retrieved`. There is no
text, no span, no chunk id. **"Where did that claim come from?" is unanswerable by
construction** — not unimplemented. `MAAILMA-master.md` contains zero occurrences of
`provenance`, `factcheck`, `grounded`, or `source_id`.

MRAG carries chunk ids end to end, which makes a post-generation verification pass possible:

```
answer ──▶ decompose into atomic claims
             │
             ├──▶ for each claim: locate supporting chunk(s) among those retrieved
             │
             ├──▶ judge sees ONLY the cited chunk + the claim → supported / not supported
             │
             └──▶ emit: answer + per-claim citation + explicit unverified list
```

**Metric — attribution accuracy.** Of the claims the system asserts, what fraction cite a source
that actually contains them. Reported with `unattributed_rate`, since a system can trivially
maximise accuracy by citing almost nothing.

Two properties make this the right enterprise metric:

- **It needs no answer key.** It runs on a customer's own corpus from day one, which no accuracy
  benchmark can do.
- **The comparison is fair.** Plain prompt-RAG can cite its retrieved chunk, so it scores. GCCA
  scoring zero is an architectural fact, not a rigged benchmark.

The graph's role here is narrow and achievable: a high-precision, provenance-carrying index of
checkable facts. **A verifier does not need complete coverage** — it needs to be right when it
speaks and honest when it cannot. That is a materially lower bar than the substitution role the
graph has repeatedly failed, and it is compatible with every measurement to date.

---

## 7. Evidence base

Every figure traceable to a committed artifact. Nulls included.

| finding | value | source |
|---|---|---|
| Prose retrieval beats no-retrieval, enterprise n=150 | **+0.2010** token_f1, CI [+0.1802, +0.2222] | `data/enterprise_rag/oracle/oracle_results.json` |
| Prose payload beats triple payload at matched retrieval | **−0.1198** for triples, CI excludes zero | same |
| Graph expansion vs dense retrieval, full 511,962-doc corpus, pre-registered primary | `fact_coverage` **+0.0235, CI [−0.0009, +0.0506] — includes zero → NULL** | `benchmarks/results/enterprise_rag_full.json` |
| Graph expansion hurt retrieval | `doc_recall` **−0.0773**, CI excludes zero | same |
| Prompt-RAG vs trained GCCA, Qwen2.5-1.5B, n=500, identity control passed | GCCA **−0.0644** token_f1, CI excludes zero | `benchmarks/results/l3_native_run.json` |

The last row is small-scale (1.5B base, 10k-doc corpus) and **must** be read with the caveat that
it likely did not enforce MAAILMA's parametric-null fraction (≥80%) or 4-gram separation (<15%).
`MAAILMA-master.md` §3.F predicts exactly this failure mode when those are absent, so their
mitigations may change the result. It is a prior, not a verdict.

---

## 8. What to measure next

1. **Arm C vs Config 2 at Stage 2** — MAAILMA's own load-bearing comparison, on one GPU and ~1M
   chunks per §7. Settles whether MRAG is the fallback or the baseline.
2. **Arm B vs Arm C** — does matched cadence buy anything over single-shot? If not, the entire
   micro-retrieval cadence premise is unnecessary for prompt-RAG and Arm B is the deployment
   target.
3. **Attribution accuracy, four-way** (base / Arm B / Arm B + verification / GCCA) — establishes
   the differentiator with prompt-RAG scoring, so the result is credible.
4. **Filter-predicate selectivity** — Filtered-DiskANN recall under realistic enterprise scoping
   (tenant + date + source). Applies to both architectures; nobody has measured it.

---

## 9. Position

MRAG is not a competitor to GCCA. It is:

- the **honest baseline** GCCA must beat (Arm B/C), required for Claim A to be interpretable;
- the **fallback payload** if Claim A does not clear, preserving the entire Stage 3–4 storage
  investment;
- the only branch that supports **citation and verification**, which is the enterprise
  requirement neither architecture currently addresses.

The storage engine is the durable asset. It survives either outcome. This document exists so
that the answer to *"what runs on it if GCCA doesn't win?"* is written down **before** the Stage 2
result arrives, rather than improvised afterwards.

---

# PART II — PROJECT PLAN

Written 2026-08-05. Concrete tasks, in dependency order, with the decision gate that ends
each phase. Effort is one person's working days.

## 10. Environment — DGX Spark (verified 2026-08-05)

```
NVIDIA GB10 · aarch64 · 128 GB unified memory
vllm 0.26.0 · torch 2.11.0+cu130 · faiss 1.14.3 · sentence-transformers 5.6.1
ollama :11434 — only nomic-embed-text:latest (0.3 GB) loaded; no vLLM server running
```

**Everything needed is already installed.** The gap is that nothing is served.

### Task 0.1 — stand up a vLLM server *(0.5 day)*
```bash
vllm serve Qwen/Qwen2.5-14B-Instruct \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.85
# verify:
curl -s localhost:8000/v1/models | jq .
```
`Qwen2.5-14B-Instruct` is MAAILMA's Stage 2 base (`MAAILMA-master.md` §5 Stage 2), so
using it keeps MRAG results directly comparable to their GCCA arms. **aarch64 caveat:**
check the wheel actually has CUDA kernels for GB10 before assuming throughput; fall back
to `Qwen2.5-7B-Instruct` if 14B will not fit alongside the embedder.

### Task 0.2 — pin the embedder *(0.5 day)*
`nomic-ai/nomic-embed-text-v2-moe`, d=768 — MAAILMA's Stage 2 choice, Apache 2.0.
Record model name + revision hash in every manifest. **W_K/W_V are not involved in MRAG,
so an embedder swap is a re-index, not a retrain** — this is MRAG's main operational
advantage over GCCA and should be exercised at least once to prove it.

### Task 0.3 — cost/latency baseline *(0.5 day)*
Measure and record before any quality work: tokens/sec, TTFT, GPU memory, cost per 1k
queries. Every later claim about MRAG being cheaper needs this number to exist first.

### Task 0.4 — corpus ladder, index choice, and the RAM wall *(0.5 day)*

Embedding pipeline: **`the_machine`** (`/home/rich/share/work/the_machine`) — GPU
tokenize+embed, sharded, work-queued, Prometheus-instrumented. Already built; use it
rather than writing an ingest path.

**Hardware ceiling (measured 2026-08-05):** GB10, 121 GB RAM (47 GB free), 1.3 TB internal
free + 4 TB external SSD.

| corpus text | chunks | PQ64 **in RAM** | raw vectors d=768 | graph R=64 | payload | total disk | verdict |
|---:|---:|---:|---:|---:|---:|---:|---|
| 256 MB | 1M | 64 MB | 1.5 GB | 0.3 GB | 0.3 GB | 2 GB | **Phase 1 target** |
| 2.5 GB | 10M | 0.6 GB | 15 GB | 2.6 GB | 2.6 GB | 20 GB | Phase 2 |
| 25 GB | 100M | 6.4 GB | 154 GB | 26 GB | 26 GB | 206 GB | = MAAILMA Stage 3 |
| 128 GB | 500M | 32 GB | 768 GB | 128 GB | 128 GB | 1.0 TB | comfortable |
| 256 GB | 1B | 64 GB | 1.5 TB | 256 GB | 256 GB | 2.0 TB | **practical ceiling** |
| 1 TB | 3.9B | **250 GB** | 6.0 TB | 1.0 TB | 1.0 TB | 8.0 TB | **✗ RAM and disk** |

**RAM is the binding constraint, not disk.** DiskANN holds PQ codes resident for graph
navigation, so 1 TB of documents needs ~250 GB of RAM — twice this machine. The 4 TB SSD
raises the disk ceiling, not the navigation ceiling.

Levers if 1B is not enough: PQ32 instead of PQ64 (2× capacity), Matryoshka d=384 (halves
vector storage), or paging the PQ layer from SSD (slower, and it changes what the latency
numbers mean).

**Embedding is not a constraint.** With 10 GPUs available, 1.5B chunks at ~5,000
chunks/sec/GPU is **~8 hours** wall-clock (50,000/sec aggregate); at 10,000/sec/GPU it is
~4 hours. `the_machine` already shards and work-queues across workers, so this is a
scheduling exercise rather than an engineering one.

Two consequences worth planning around:

1. **Re-embedding is affordable.** MRAG's structural advantage over GCCA — *"an embedder
   swap is a re-index, not a retrain"* (§2) — becomes concrete: a Nomic v1.5 → v2-MoE
   change costs one overnight run, versus GCCA's full W_K/W_V re-alignment. Exercise this
   at least once and record the wall-clock, because it is a hard number that argues for
   the architecture.
2. **The corpus ceiling stays RAM-bound, not GPU-bound.** More GPUs do not raise the 1.5B
   limit; only PQ bit-width, embedding dimension, or a bigger serving box does. Do not
   size the corpus off embedding throughput.

**Start Phase 1 at 1M chunks with exact `IndexFlatIP`.** MAAILMA's `src/retriever.py` gives
the reason: *"an exact index costs nothing and removes ANN recall as a variable, so a Gate
failure can only be our code."* Mechanism differences between arms B/C/D/E appear at 1M —
`MAAILMA-master.md` §7 states Claim A is *"provable with: one GPU, ~1M chunks."* Scale
tests systems throughput, which is a different question and a later phase.

**Where the 4 TB drive earns its keep:** a real Milvus DISKANN deployment at ~1.5B chunks
with MinIO on NVMe — Claim B throughput measured on owned hardware, no cluster required.

**Index choice at 1.5B is forced.** HNSW at M=48 (the current `configs/semantic_scholar.toml`
setting for 768-d) needs roughly 384 B/node of graph resident — 576 GB at 1.5B nodes, far
past 121 GB. GPU CAGRA needs vectors in GPU memory, also out. **DISKANN is the only viable
index at this scale on this box**; HNSW stays correct for Phases 1–3 and for hot segments.

**Environment risk to clear first:** `configs/smoke-test-pod.yaml:20` carries a Blackwell
kernel check — *"PyTorch has no kernels for this GPU's arch — need a Blackwell-capable base
image."* The tahi venv works (torch 2.11.0+cu130 on GB10, verified 2026-08-05), so confirm
the Milvus/worker images do too before committing to a long ingest.

**Ingest format already produced by `the_machine`:** `part_<N>.embedding.f` (raw
float32/float16), `part_<N>.ids.i`, `part_<N>.record_size`, merged to `final_embeddings.f`.
`MILVUS_STATUS.md` lists **"Embedding → Milvus Path"** as an open question — resolving it is
Task 0.5 and it blocks every phase beyond 1.

**Gate 0:** vLLM serving, embedder pinned with revision, baseline numbers committed.

---

## 11. Phase 1 — MRAG on the substrate *(4 days)*

### Task 1.1 — ingestion *(1 day)*
Chunk → embed → index. Reuse the patterns in `maailma/scripts/build_rag_index.py`
(`ChunkRecord`, `continuation_id`) so the index is shared with the GCCA arms rather than
forked. Late chunking (256-token parent / 64-token child) per `MAAILMA-master.md` §3.C.

Emit per chunk: `chunk_id`, `doc_id`, `position`, `text`, `continuation_id`.
**`doc_id` must survive to serving** — it is the citation unit for §6 and there is no
attribution without it.

### Task 1.2 — retrieval path *(1 day)*
Two-stage, §3.1: optional Filtered-DiskANN label predicate → MIPS top-50 → gist rescore →
top-k → payload fetch → dedupe by parent doc → pack to token budget.

### Task 1.3 — Arm B, single-shot *(0.5 day)*
One retrieval before decode. Stock vLLM. The deployment default.

### Task 1.4 — Arm C, matched cadence *(1 day)*
Re-retrieve every 64 generated tokens, refresh the context block. This is MAAILMA's
Config 1b — *"the strongest honest baseline"* — and the arm their Stage 1 eval does not
implement (`eval_adapters.py:282-299` runs base / GCCA α=0 / GCCA trained only).

### Task 1.5 — Arm D, **agentic RAG** *(1.5 days)* ← the missing opponent
`MAAILMA-master.md` §7: *"The honest competitor is iterative/agentic RAG, not single-shot
RAG."* It appears in **no** config in their §4 matrix and **nowhere** in `src/` or
`scripts/`. The stated win condition is measured against an opponent that does not exist.

Difference that matters: Arm C re-retrieves mechanically using the **previous generated
chunk** as query — inheriting the unresolved continuation-as-query asymmetry (§3.C).
Agentic RAG lets the model **decide when to retrieve and write its own query**, which is a
question rather than a continuation, and therefore a much stronger query.

Implementation: a tool-call loop over the same index. No training, no adapters.
Report retrieval count and token cost per answer so the efficiency comparison is fair.

**Gate 1:** four arms (A base, B single-shot, C matched-cadence, D agentic) running over
one shared index, one model, one prompt shape, one token budget. Context tokens per arm
logged.

---

## 12. Phase 2 — attribution layer *(3 days)*

Protocol is already fixed in `TAHI_PLAN.md` §6.1 — do not redefine it.

### Task 2.1 — claim decomposition *(1 day)*
Reuse `src/tahi/validate/claim_extractor.py`. **Known defect to fix first:** it emits
sentence fragments with no subject (observed 2026-08-05: `"is Wednesday, April 21, 2027,
from 10:00 to 11:00 PT"`). Prompt fix, then verify on 20 hand-checked answers before use.

### Task 2.2 — citation *(0.5 day)*
Each arm returns, per claim, the `doc_id` it attributes that claim to.
**Candidate-set parity is mandatory** — every arm cites from the same retrieved set. The
2026-08-05 A6 run violated this (prompt-RAG chose from 2.81 docs, the graph from 403) and
the resulting −0.3277 is not interpretable as a mechanism comparison.

### Task 2.3 — judging *(0.5 day)*
Judge sees only the claim and the cited text. Never the gold answer, never the arm label.

### Task 2.4 — metrics *(1 day)*
`attribution_accuracy` and `unattributed_rate`, paired bootstrap CIs, seed recorded. A win
on accuracy with a materially worse `unattributed_rate` is a **null**, not a win.

**Gate 2:** attribution measured for all four arms with candidate-set parity, CIs reported.

---

## 13. Phase 3 — measurement *(3 days)*

### Task 3.1 — power first *(0.5 day)*
Compute minimum detectable effect **before** running. The 2026-08-05 GraphRAG-Bench pilot
had a ±10-point CI against a ~3-point effect — a design that could not have detected its
own hypothesis. Choose n from the effect that must be visible.

### Task 3.2 — the matrix *(1.5 days)*

**This is MAAILMA's ablation matrix (`MAAILMA-master.md` §4), not a parallel one.** MRAG
does not get its own scoreboard. It supplies the arms that matrix is missing and slots
GCCA in as a peer.

| | A base | B single-shot | C matched-cadence | **D agentic** | **E GCCA** |
|---|---|---|---|---|---|
| MAAILMA config | 0 | 1 | **1b** | *(absent)* | **2** |
| in their §4 matrix? | yes | yes | yes | **no** | yes |
| implemented in their code? | yes | no | no | **no** | yes |
| answer quality (token F1 / fact coverage) | | | | | |
| attribution accuracy | | | | | **structurally 0** |
| unattributed rate | | | | | |
| context tokens / answer | | | | | **O(1)** |
| retrievals / answer | | | | | |
| TTFT, tokens/sec | | | | | |
| cost / 1k queries | | | | | |

**Arm E is the point of the exercise.** Without it the matrix measures prompt-RAG variants
against each other and never touches the architecture MRAG exists to insure against.

### Task 3.2a — Arm E dependency *(blocked on MAAILMA Stage 2)*

GCCA needs trained adapters, which needs the parametric-null dataset
(`maailma/scripts/build_train_data.py`, Gate 6: ≥80% parametric-null, <15% 4-gram overlap)
and alignment training (`train_adapters.py`). That is MAAILMA Stage 2 work on their
timeline, not MRAG's.

Sequencing consequence: **A–D run now and do not wait for E.** They are the baselines
Claim A must be measured against, and they do not currently exist in `maailma/scripts/` —
`eval_adapters.py:282-299` runs base / GCCA α=0 / GCCA trained, so GCCA is presently
compared only against itself. Building A–D first means the moment Stage 2 adapters land,
the comparison is a config change rather than a project.

**Do not substitute TAHI's GCCA for Arm E.** `src/tahi/native/gcca_layer.py` is
Flamingo-style *static* gated cross-attention over a fixed memory tensor — no chunking, no
causal offset, no per-chunk re-retrieval. MAAILMA's is RETRO chunked cross-attention. The
Aug 3 result (`l3_trained` −0.0644 vs prompt-RAG) is therefore **not** evidence about
Claim A and must not be cited as such.

Two mandatory reads on Arm E when it runs, both from MAAILMA's own diagnostics
(`maailma/src/diagnostics.py`):
- per-layer `tanh(α)` **and** `contribution` = ‖tanh(α)·CCA(H)‖ / ‖H‖
- `AlphaTracker.collapsed()` — median |α| < 0.02 **and** contribution < 0.01 past 20% of
  training is **gate collapse: a null result, not a negative one**

A GCCA loss without those numbers is uninterpretable. TAHI's GCCA has no contribution
tracking at all, which is why the Aug 3 run cannot be checked for collapse retroactively.

### Task 3.3 — report *(1 day)*
Every cell traces to a committed artifact. Nulls included.

The comparisons that decide things, in order:

1. **C vs E** — MAAILMA's own load-bearing comparison, *"if only one comparison in this
   document is run properly, it should be 1b vs. 2."* Decides Claim A.
2. **D vs E** — the honest competitor from their §7. If GCCA does not reach agentic-RAG
   quality, §7's own kill criterion fires: *"if it only matches single-shot RAG accuracy,
   kill it — iterative RAG is free."*
3. **B vs C** — does cadence buy anything at all? If B ≈ C, the entire micro-retrieval
   premise is unnecessary for prompt-RAG and Arm B is the deployment target.
4. **Attribution, all arms** — the axis GCCA cannot enter, with B/C/D scoring so the
   contest is fair.

**Gate 3:** matrix complete for A–D, artifacts committed, MDE stated, E slotted when
Stage 2 adapters exist.

---

## 14. Engineering guardrails — earned 2026-08-05, all from real failures

1. **BGE is asymmetric.** Queries take `"Represent this sentence for searching relevant
   passages: "`, documents do not. Nomic uses `search_query:` / `search_document:`.
   Two scripts written today omitted it. *(Measured impact here: negligible on short node
   labels — but verify per corpus, never assume.)*
2. **Never let one bad LLM reply kill a run.** Wrap every per-item LLM call in
   try/except, count failures into the manifest. A malformed JSON reply destroyed a run
   that had already paid for 150 generations.
3. **Candidate-set parity or the comparison is void.** See Task 2.2.
4. **Background jobs:** `setsid nohup … & disown`, then watch the *child* PID. `setsid`
   forks, so the captured PID exits immediately and a naive watcher reports a false death.
5. **Never `pkill -f <pattern>`** where the pattern can match your own shell. Kill by PID.
6. **No artifact, no number.** Every reported figure lives in a committed JSON with
   per-item scores, regenerable by someone else. `run_oracle_ceiling.py` was overwritten
   after producing the −0.1198 result, so that number is currently unregenerable.
7. **Decompose before integrating.** Test question→retrieval alone, before generation,
   before claim extraction, before judging. A four-stage pipeline that fails gives four
   confounded suspects; the isolated probe found the real cause (ranking) in minutes.

---

## 15. Timeline and decision points

| phase | days | gate | if it fails |
|---|---:|---|---|
| 0 Environment | 2.0 | vLLM serving, corpus ladder fixed, baseline recorded | fix wheels/model size before proceeding |
| 1 Four arms | 4 | all four running, one index | fix before measuring anything |
| 2 Attribution | 3 | parity enforced, CIs reported | the differentiator is unmeasurable — say so |
| 3 Measurement | 3 | matrix complete for A–D | report what is missing |
| 3b Arm E (GCCA) | — | blocked on MAAILMA Stage 2 adapters | run C vs E the day they land |

**~11.5 working days.**

**The results worth having, in priority order:**

1. **C vs E (Config 1b vs 2).** MAAILMA's own load-bearing comparison. Decides Claim A,
   and therefore decides whether Claim B — the Starling/DiskANN work — has anything to
   support. Blocked only on Stage 2 adapters; the baseline half can be built now.
2. **D vs E.** The honest competitor their §7 names and their matrix omits.
3. **B vs C.** Does cadence matter at all for prompt-RAG?
4. **Attribution across A–D.** The axis GCCA cannot enter.

None of these requires TAHI's graph to work. All of them are useful if it does not — and
items 1 and 2 are useful to MAAILMA regardless of how Claim A resolves, because without
them Claim A cannot be evaluated at all.

---

# PART III — GRAPH EXTRACTION FROM THE EMBEDDING PIPELINE

**Added 2026-08-06.** A proposal to the MAAILMA lead, from the embeddings DRI.

## 16. The ask, in two sentences

> The embedding pass already reads every document, so we could emit typed
> entity–relation triples alongside the vectors — one extra artifact out of ingest,
> not a competing retrieval path. AutoSchemaKG (arXiv:2505.23628) built 5.9B edges
> from 50M documents with schemas induced automatically at 92% alignment to
> hand-built ones, and reports it complements parametric knowledge on multi-hop QA
> — which is the half of the information space vectors structurally cannot reach,
> since an answer three relations from the query has no similarity to it.

Third sentence, if the trust question comes first:

> Keeping such a graph clean at scale is an open problem with active work — SHARP
> (arXiv:2604.04190) is the current approach, schema-aware verification of extracted
> triples — so I would scope it as a side bet measured against our own benchmark,
> not a commitment.

**Why this framing.** It asks for nothing architectural. It is not a second retrieval
system and it does not compete with GCCA; it is an additional output of a pipeline
the embeddings DRI already owns. Cheap to try, cheap to kill.

**The line underneath it.** MAAILMA expands *what the model knows*. A graph expands
*what it can traverse and what it can be checked against*. The datastore-scaling
literature supports exactly that split — large gains on factual recall, modest gains
on reasoning.

---

## 17. Objections, and the citation that answers each

| objection | answer |
|---|---|
| *Can we build one at our scale?* | **AutoSchemaKG** — 5.9B edges from 50M documents, code released. Same order as our 1.5B-chunk target, so it is a precedent rather than an aspiration. |
| *Do we have to hand-write a schema?* | **AutoSchemaKG** — schemas induced automatically, **92% semantic alignment** with human-crafted ones, zero manual intervention. |
| *What is the extraction cost?* | spaCy dependency parsing, no LLM calls — `the_machine/src/ragga/triples.py` already implements it. |
| *What does it buy over vectors?* | **KiRAG** (Fang et al., ACL 2025, arXiv:2502.18397) — triple-based iterative retrieval improves multi-hop. Plus our own measurement, §18. |
| *How do we know the model's output is right?* | **GraphEval + GraphCorrect** (Amazon, arXiv:2407.10793) — locates *which specific triple* is hallucinated and corrects it. A dense index cannot do this at any scale. |
| *How do we know the graph itself is right?* | **SHARP** (arXiv:2604.04190) — schema-aware triple verification. This is the honest open risk. |
| *Hasn't KG-RAG been tried?* | Yes. `the_machine/src/ragga/methods/kirag.py` is already a working implementation. |

**Lead with GraphEval if the lead cares about reliability rather than recall.**
Industrial lab, and "which triple is wrong" is something a vector index structurally
cannot answer.

---

## 18. Our own evidence — MetaQA 3-hop, 2026-08-06

Held-out benchmark, 14,274 questions, exact set match, no LLM judge.
Artifacts: `data/metaqa/results/{verify,loop,ingen}_results.json`.

| mechanism | where the graph acts | accuracy | fixed / broken |
|---|---|---:|---|
| pre-generation stuffing | retrieved text in the prompt | 0.010 | — |
| post-generation correction | diff the answer, re-generate | **0.590** | 58 / 0 |
| in-generation constraint | logit mask, every token (local 1.5B) | 0.210 | 21 / 0 |

- Traversal reaches answers dense retrieval cannot: **1% → 59%**, p < 0.0001.
- **Zero regressions in every configuration run.** Nothing has made a correct answer
  wrong.
- One correction pass beats three (0.590 vs 0.540). Do not loop.

### 18.1 What this does NOT show — state this before someone else does

- **The MetaQA graph is native ground truth.** Nothing was extracted, so extraction
  quality was not a variable. This is the entire risk of the proposal.
- **Our own LLM extraction lost information.** On enterprise documents, triples
  extracted from source prose scored **−0.12 against the prose itself** at matched
  retrieval, CI excluding zero. Today's win was on a graph that was already correct.
- **The relation chain is few-shot prompted.** An ablation puts ~29 of the 58 points
  on three worked examples; enumerating all 9³ paths instead scores 1% → 30%.
- **The in-generation and post-generation numbers are on different models** and are
  not directly comparable.
- 0.59 remains far below published MetaQA 3-hop (GraftNet 77.7, PullNet 91.4,
  EmbedKGQA 94.8).

**Extraction quality is the whole bet.** Saying so first is what makes the ask
credible.

---

## 19. References

| paper | id | what it establishes |
|---|---|---|
| AutoSchemaKG | [arXiv:2505.23628](https://arxiv.org/abs/2505.23628) · [code](https://github.com/HKUST-KnowComp/AutoSchemaKG) | billion-edge KG construction with induced schemas, web scale |
| GraphEval / GraphCorrect | [arXiv:2407.10793](https://arxiv.org/abs/2407.10793) | triple-level hallucination localisation and correction (Amazon) |
| SHARP | [arXiv:2604.04190](https://arxiv.org/abs/2604.04190) | schema-aware verification of extracted triples |
| KiRAG | [ACL 2025](https://aclanthology.org/2025.acl-long.1224/) · arXiv:2502.18397 | iterative triple retrieval for multi-hop |
| RARR | [ACL 2023](https://aclanthology.org/2023.acl-long.910/) | post-generation research-and-revise, preserving the original output |

---

## 20. Existing code worth reusing before building anything

| path | what it is |
|---|---|
| `the_machine/src/ragga/triples.py` | spaCy subject-relation-object extraction, batched and cached; `bridge_score()` for iterative hops |
| `the_machine/src/ragga/methods/kirag.py` | KiRAG as a reranker over dense candidates — triples extracted at query time, **no persistent graph** |
| `the_machine/src/ragga/` | index, embed, retriever, exact/retrieval eval, benchmark harness with a `LOADERS` registry |
| `the_machine/RAGGA_DESIGN.md` | four-method plan (sliding window, LoRAG, KiRAG, adaptive agentic) sized for the DGX |

Note the distinction: ragga's KiRAG uses triples at **retrieval time** and builds no
persistent graph. This proposal is the **ingest-time** counterpart. They are
complementary, and adding MetaQA to the `LOADERS` registry would put KiRAG on the
same benchmark as the three numbers in §18.
