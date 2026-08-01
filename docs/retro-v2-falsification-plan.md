# RETRO-v2 — Minimum Falsification Plan

**Prove it — or kill it — on one GPU.** The central bet (GCCA beats RAG) is *not* a petabyte problem. It's
a mechanism claim, testable at toy scale. This is the cheapest experiment that would confirm or bury the
idea before anyone builds an out-of-core engine.

## 1. Split the claim in two

The doc tangles a *science* claim with a *systems* claim. Separate them and the science becomes cheap to
test, while the expensive systems work only matters if the science holds.

- **Claim A — the science: "GCCA output beats RAG."** A mechanism question: does retrieval that re-aims
 mid-generation beat one-shot retrieval? Independent of corpus size. **Provable at Stage 2 · 1 GPU · ~1M chunks.**
- **Claim B — the systems: "Serve 1PB at <2ms."** An engineering question: out-of-core DiskANN/Starling,
 io_uring, IOPS under load. Only worth solving **if A is true.** *Stage 4 · deferred.*

**The reframe:** discriminating power comes from **task design, not data size.** A tiny corpus (100k
chunks, in-RAM FAISS) is plenty — if anything it makes single-shot RAG look artificially good, so a GCCA
win there is a *strong* signal.

## 2. The de-risking ladder

| Tier | Question | Cost | Decision |
|---|---|---|---|
| **0** | Does continuous retrieval even help? | days · ~$0 · no training | No GCCA. On a multi-hop set, run single-shot RAG vs iterative/agentic RAG (off-the-shelf). If iterative does **not** beat single-shot → continuous retrieval doesn't help this task → **STOP.** The whole-program kill-test, for free. |
| **1** | Do the GCCA mechanics work? | days · MacBook | Verify plumbing: α=0 ⇒ bit-identical logits, O(1) KV memory over 1k tokens, causality mask no leak. Proves the *implementation*, **not** quality (untrained ≈ α=0 ≈ no benefit). |
| **2** | GCCA vs the real baselines | weeks · 1 GPU | Train adapters on ~1B tokens, run the full comparison (below) on multi-hop + single-hop control, scored on **accuracy AND efficiency**. Where the thesis lives or dies. |
| **3+** | Scale & serving | months · cluster + NVMe | Out-of-core engine, DiskANN/Starling, 100M → 1PB, <2ms under load. **Only if Tier 2 passes.** |

## 3. The decisive experiment (Tier 2)

| | |
|---|---|
| **Hardware** | 1 GPU — a DGX Spark or *one* of our Blackwells. No NVMe, no out-of-core anything. |
| **Base model** | An 8–14B **frozen** instruction model (e.g. Llama-3-8B / Qwen-2.5-14B). |
| **Corpus** | ~100k–1M chunks in in-memory FAISS `IndexFlatIP` (the Wikipedia subset the multi-hop sets are built on). |
| **Retriever** | Frozen BERT / BGE-base, 64-token chunks. |
| **Training** | Adapter alignment (`W_K, W_V` + gate) on ~1B tokens; salient-span masking + 20% distractor chunks. |
| **Systems compared** | 1. Base LLM (no retrieval) · 2. Single-shot prompt-RAG · 3. **Iterative/agentic RAG** ← the real competitor · 4. GCCA |
| **Benchmarks** | Multi-hop: HotpotQA, 2WikiMultiHopQA, MuSiQue, FRAMES · Single-hop control: PopQA / TriviaQA |
| **Metrics** | Accuracy (EM / F1) · Efficiency (tokens/sec, peak KV memory, retrieval latency, context length) |

## 4. Task design — where the signal comes from

The experiment only discriminates if the task is built so single-shot retrieval **provably can't** fetch
the needed context. That's the **hidden bridge entity**:

> *"What's the capital of the country where the author of [book X] was born?"*
> Single-shot RAG retrieves on the question — it doesn't yet know the author or the country, so it
> **cannot** fetch the hop-2/hop-3 chunks. Continuous retrieval, once it has generated "the author is
> **A**," re-retrieves and finds "**A** was born in **C**."

- **The single-hop control is essential:** GCCA should *win on multi-hop* but *tie on single-hop*. Win on
 both ⇒ a confound, not the mechanism.
- **Small corpus is fine — even favorable:** discriminating power is engineered into the *question
 structure*, not the data volume.

## 5. Scoring & kill criteria

The real baseline is **iterative RAG** (free continuous retrieval), not single-shot RAG. Score the 2×2:

- **Accuracy** — does GCCA *match iterative RAG*, the quality ceiling of continuous retrieval?
- **Efficiency** — …at *single-shot RAG cost*? O(1) memory, one vector-op vs re-running the LLM on a
 growing prompt.

**The win condition:** GCCA delivers **iterative-RAG quality at single-shot cost.** That — not "beats plain
RAG" — is the result that justifies a custom architecture.

**Kill criteria — commit to these before running:**

- **Tier 0:** iterative RAG doesn't beat single-shot on multi-hop → stop.
- **Tier 2:** GCCA fails to beat iterative RAG on *accuracy* **and** fails to beat single-shot RAG on
 *efficiency* → the bet is dead; do not scale.

## 6. Our stake & the pipeline work it implies

- **Stage 2/3 hardware is ours** — one Blackwell runs the decisive test; the 4-GPU cluster is Stage 3.
- **Corpus is Semantic Scholar** — which our pipeline already embeds; the multi-hop benchmarks run on a
 Wikipedia subset first.
- **The pipeline change this needs:** *late chunking* — cut documents into 64-token child vectors that
 still remember their document, instead of embedding whole records. That's the concrete ingestion work.
- **Storage is not on the critical path yet** — Tier 0–2 fit in RAM/FAISS. NFS→NVMe only matters at Tier 3+.

---

*Companion to the RETRO-v2 brief, GCCA mechanism doc, and cheatsheet. Source: `docs/RAG with ANN.txt`.*
