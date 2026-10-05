# RETRO-v2 Deep-Dive Review — What to Keep, What to Test, What to Borrow

**Scope:** Review `docs/retro-v2-brief.md` and `docs/retro-v2-falsification-plan.md` in the context of TAHI. Identify what is useful, what is missing, and how TAHI can be positioned as a distinct — and testable — alternative.

---

## 1. What the RETRO-v2 proposal gets right

The brief and falsification plan are unusually clear about risk separation:

- **Science vs. systems split.** Claim A (GCCA beats RAG) is separable from Claim B (serve 1 PB at <2 ms). This is the most important framing in the whole document.
- **Tier 0 kill test.** "Run iterative/agentic RAG against single-shot RAG first. If iterative doesn't win, stop." This is correct and cheap.
- **Small-corpus discriminating power.** The hidden-bridge-entity task design (author → country → capital) means a 100k–1M chunk corpus is enough to test the mechanism, not the hardware.
- **Real baseline is iterative RAG, not single-shot RAG.** The win condition "iterative-RAG quality at single-shot cost" is the right bar.
- **Staged hardware de-risking.** Stage 1 (MacBook math sandbox) → Stage 2 (1 GPU alignment) → Stage 3 (multi-GPU pre-production) → Stage 4 (enterprise NVMe) is sound.

## 2. The central unanswered question for us

Does **continuous structured world-state retrieval** beat both single-shot RAG and iterative RAG on multi-hop QA?

RETRO-v2 assumes the retrieved signal is **text chunks**. TAHI's bet is that the retrieved signal should be **entities, relations, and traversed paths**. The same falsification plan can test both hypotheses.

So the expanded experiment matrix should be:

| System | Retrieval signal | When | Memory |
|---|---|---|---|
| Base LLM | none | — | O(1) |
| Single-shot RAG | top-k text chunks | step 0 | O(L) |
| Iterative RAG | top-k text chunks, re-retrieved | per reasoning step | O(L) |
| GCCA (RETRO-v2) | top-k text chunks via cross-attention | every 64 tokens | O(1) |
| **TAHI world coprocessor** | entity graph + relation paths + chunk evidence | per reasoning step | O(graph) |

If TAHI's graph path can surface the hidden bridge entity deterministically while RAG relies on embedding luck, that is a real win.

## 3. Gaps in the RETRO-v2 verification plan

### 3.1 No structured-reasoning competitor

The plan compares GCCA against RAG variants. It does not compare against a system that explicitly models entities and relations. TAHI should be added as a fifth arm.

### 3.2 No provenance or correctness metrics

Accuracy (EM/F1) is necessary but not sufficient for a coprocessor claim. We should also measure:

- **Retrieval precision at the bridge entity.** Did the system retrieve the correct intermediate entity?
- **Path correctness.** For multi-hop questions, is the chain of entities/relations correct?
- **Hallucination rate.** How often does the system invent an entity or relation not in the corpus?
- **Constraint adherence.** Can the system reject answers that violate stated facts?

These are TAHI's natural evaluation dimensions.

### 3.3 Corpus choice mismatch

The plan proposes Semantic Scholar as the ultimate corpus. That is fine for open research QA, but it is a poor fit for the Wikipedia multi-hop benchmarks (HotpotQA, 2WikiMultiHopQA, MuSiQue, FRAMES). The decisive Tier 2 experiment should run on the **Wikipedia subset those benchmarks are built from**, not Semantic Scholar.

Semantic Scholar becomes relevant only if the mechanism is proven and the goal shifts to research synthesis.

### 3.4 Missing cost-per-correct-answer analysis

The plan compares efficiency (tokens/sec, KV memory) but not cost-per-correct-answer across systems. For TAHI, the relevant cost metric is:

> cost per correct answer = (embedding/build cost + inference cost + world-model maintenance) / accuracy

RETRO-v2's cost is dominated by PB-scale storage and custom serving. TAHI's cost is dominated by world-model construction. A head-to-head cost model should be part of Tier 2.

### 3.5 No ablation of retrieval vs. reasoning

The plan does not isolate whether GCCA wins because of **when it retrieves** (continuous) or **what it retrieves** (chunks). A TAHI arm naturally ablates this: it retrieves structured entities continuously but does not use cross-attention adapters. If TAHI matches or beats GCCA on accuracy, the "continuous" mechanism is validated but the "chunk" representation is not necessary.

## 4. What TAHI should borrow from RETRO-v2

| RETRO-v2 idea | TAHI application | Priority |
|---|---|---|
| GCCA adapter mechanics | `NativeIntegration` / Level 3 residual injection | High — concrete implementation path |
| `tanh(α)` zero-initialized gate | Controlled opening of world-model signal | High — avoids base-model distortion |
| 1-chunk causal offset | Prevents future information leakage in native mode | High — safety/correctness |
| Late chunking | Better document evidence nodes in world models | Medium — improves chunk quality |
| Async prefetch pipeline | Hide world-model retrieval latency in native mode | Medium — only needed at scale |
| Salient-span masking + distractors | Training data for native adapters | Medium — if we train adapters |
| Out-of-core NVMe engine | `WorldModelStore` backend for huge graphs | Low — not needed until world models exceed RAM |

## 5. Revised kill criteria for TAHI

Add TAHI-specific stopping rules to the falsification plan:

- **Tier 0:** If iterative RAG does not beat single-shot RAG on multi-hop, **stop** — neither GCCA nor TAHI gains from continuous retrieval.
- **Tier 1:** If the TAHI world model cannot retrieve the bridge entity for >50% of multi-hop questions using graph traversal, the structured-representation hypothesis is weak.
- **Tier 2:** If TAHI with graph traversal does not match iterative-RAG accuracy, structured continuous retrieval is not competitive with text continuous retrieval.
- **Tier 2:** If GCCA does not beat TAHI on accuracy **and** does not beat single-shot RAG on efficiency, GCCA is not justified.

## 6. Recommended next step

Run the **Tier 0 experiment with a TAHI arm**:

1. Build a small Wikipedia entity-graph world model.
2. Evaluate on HotpotQA / 2WikiMultiHopQA / MuSiQue / FRAMES against:
 - base LLM,
 - single-shot RAG,
 - iterative RAG,
 - TAHI graph-traversal coprocessor.
3. If iterative RAG and TAHI both beat single-shot, proceed to Tier 2 adapter alignment for native mode.

This is the cheapest way to validate TAHI's core claim: **structured world-state retrieval improves multi-hop QA.**

## 7. Key references

- `docs/retro-v2-brief.md`
- `docs/retro-v2-falsification-plan.md`
- `docs/RETRO_ANN_VS_TAHI.md`
- RETRO (Borgeaud et al., ICML 2022)
- Flamingo (Alayrac et al., NeurIPS 2022)
- InstructRetro (Wang et al., NVIDIA 2023)
