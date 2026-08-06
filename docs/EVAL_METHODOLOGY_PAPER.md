# Proposal: Evaluation Instruments That Cannot Measure

**Working title:** *Inert Instruments: Silent Failure Modes in RAG Faithfulness Evaluation*
**Target venues:** NeurIPS Datasets & Benchmarks · ACM REP · EMNLP/ACL evaluation workshops (Insights from Negative Results)
**Date:** 2026-08-03
**Status:** Proposal, with novelty check performed

---

## Novelty check (done first, deliberately)

Before proposing, I searched for prior work on the strongest finding in this project — that graph-expanded candidates were arithmetically incapable of entering the result set.

**It is largely taken.** [Calibrated Fusion for Heterogeneous Graph-Vector Retrieval in Multi-Hop QA](https://arxiv.org/html/2603.28886) (2026) treats graph/vector score incommensurability directly, notes that "naïve score fusion is poorly behaved under this mismatch," and proposes percentile-rank calibration. Reciprocal Rank Fusion is the established rank-only alternative. [Why RAG Fails: A Graph Perspective](https://arxiv.org/pdf/2605.14192), [RAG vs. GraphRAG](https://arxiv.org/html/2502.11371v3), and [Is GraphRAG Needed?](https://arxiv.org/pdf/2606.25656) cover GraphRAG null results.

What remains ours is a *sharpening*: multiplicative composition can be **strictly infeasible**, not merely miscalibrated — a regime where the similarity required to be admitted exceeds 1.0, the maximum the metric can attain. Measured here in 45 of 60 queries. That is a good section in someone's paper. It is not a paper.

**So the proposal below is not the retrieval paper.** It is the one whose central claim I could not find prior art for.

---

## The paper

### Thesis

RAG faithfulness metrics can be **inert** — structurally incapable of detecting the property they report — while emitting plausible, in-range numbers that pass code review, unit tests, and peer review. We characterise two such failures, give a cheap detection probe for each, and measure their prevalence across widely-used evaluation frameworks.

### The two failures, both measured here

**1. Polarity inversion is invisible to lexical groundedness.**

Content-word-overlap metrics (`groundedness`, `fact_coverage`, and their equivalents) score a claim and its negation identically, because negation is carried by stopwords that the metric strips.

Measured on 500 questions: negating every gold answer changed `fact_coverage` by **exactly 0.0000**. The same metric ceilings at **0.779** when scoring a gold answer against its own decomposed facts — a 22% false-negative floor on provably perfect input.

Downstream consequence, measured: a claim-verification benchmark reported **AUC 0.4492 on negated claims — below chance** — and the result was uninterpretable rather than negative.

**2. NLI faithfulness judges become evidence-invariant past their context limit.**

This is the finding I believe is novel and is the paper's centre of gravity.

Cross-encoder NLI models are the standard substrate for faithfulness metrics. They have a 512-token limit. RAG evaluation routinely concatenates multiple retrieved documents into a single premise well past that limit. When the implementation truncates rather than windows, the score stops depending on whether the evidence supports the claim.

Measured, with a DeBERTa NLI cross-encoder:

```
support present, ~1900 tokens  ->  truth_score +0.826
support ABSENT,  ~1900 tokens  ->  truth_score +0.826    <- identical
support absent,  short          ->  truth_score -0.001    <- correct
```

The model is well-behaved on short input and **degenerate on the input the harness actually feeds it**. The failure is not degraded accuracy; it is complete loss of dependence on the variable being measured. And it is silent — the scores sit in a plausible range.

**The unifying property:** both failures produce reasonable-looking numbers. Neither raises an exception, fails a type check, or trips a unit test. Both invalidate every comparison built on them.

### Contributions

1. **Characterisation** of instrument inertness in RAG faithfulness evaluation, with two measured instances and the conditions under which each arises.
2. **Two detection probes**, each a few lines, runnable against any harness:
   - **Negation-invariance probe** — score a claim and its negation. If the scores are equal, the metric cannot measure truthfulness.
   - **Support-ablation probe** — score a claim against evidence containing the support, then against matched evidence with the support removed. If the scores are equal, the metric is not reading the evidence.
   These are cheap, deterministic, and require no labels.
3. **Prevalence study** — the work that makes it publishable. Audit widely-used RAG evaluation frameworks (RAGAS, ARES, TruLens, DeepEval, LlamaIndex and LangChain evaluators, and the NLI-based faithfulness metrics in recent GraphRAG papers) for: truncation versus windowing in the entailment path, and polarity sensitivity of lexical metrics.
   Headline of the form: *N of M widely-used RAG faithfulness metrics fail at least one inertness probe.*
4. **A positive protocol** — the identity control. For systems that modify model internals, assert that the disabled configuration reproduces the unmodified model token-for-token. Verified here: α=0 reproduced base exactly, 0 mismatches, delta 0.0000, CI [0.0, 0.0]. This is a falsifiable harness guarantee that most work in this space lacks.

### Why the prevalence study is the paper

Single-codebase findings are anecdote. The claim that carries a venue is *"this is common and nobody is checking."* The probes are designed to make that scan mechanical: for each framework, construct one negation pair and one support-ablation pair, run the metric, compare.

Prior expectation, to be stated and then tested: truncation-based NLI faithfulness is common, because `truncation=True, max_length=512` is the default idiom in the `transformers` tokenizer API and windowing requires deliberate effort.

---

## Evidence already in hand

All measured by running code in this repository. No new experiments required for §1, §2, or the case study.

| Finding | Measurement |
|---|---|
| Lexical polarity blindness | `fact_coverage` negation delta **0.0000**, n=500 |
| Lexical false-negative floor | Oracle ceiling **0.779**; mismatched-pair floor 0.1135 |
| Downstream consequence | Negated-claim AUC **0.4492**, below chance |
| NLI evidence-invariance | **+0.826** with and without support at ~1900 tokens; −0.001 correct at short length |
| Identity control | 0 mismatches; α=0 delta 0.0, CI [0.0, 0.0] |
| Admissibility (case study) | Expanded candidate won **0/60** queries; required cosine > 1.0 in **45/60** |
| Post-fix outcome (case study) | Removing the infeasibility moved overall AUC **down**, 0.5744 → 0.5220 |

That last row matters and should be reported prominently: **fixing a disabled mechanism did not make it effective.** Admissibility failure and ineffectiveness are distinct, and the literature conflates them. A GraphRAG null is uninterpretable unless the admissibility rate is reported alongside it.

### The supporting taxonomy

A secondary section can draw on the defect classes already catalogued in `research_paper_notes.md`, of which one is genuinely underexplored:

**Type-compatible semantic substitution** — a character-sum hash embedding was passed where a sentence-transformer vector was expected. Dimensionality matched, so nothing raised, no test failed, and semantic retrieval was silently replaced by hash retrieval across every comparison. Shapes and dtypes are correct; only the meaning is wrong.

A related class this project supplies fresh instances of: **unreachable components that pass their own tests.** A relational GNN encoder and an OWL ontology module each shipped with green test suites and were called by nothing in the runtime; a benchmark arm labelled "GNN" was measured without the GNN in its path. The proposed check is an integration assertion — *is this component reachable from the measured entry point?* — which no standard test framework provides.

---

## Work required

| Task | Effort |
|---|---|
| Formalise the two probes; release as a small package | ~1 week |
| Prevalence scan across 15–25 frameworks and recent papers | 2–4 weeks |
| Write-up | ~2 weeks |
| **Total** | **5–7 weeks** |

No GPU. No corpus. No dependence on whether OCTO's thesis holds.

---

## Why this over the alternatives

**Versus the OCTO systems paper.** That one needs the GNN actually trained and wired in (neither is true today), n ≥ 126, the 72B model, length-matched decoding, and doc recall above 0.05. Weeks of work with an uncertain outcome. It should proceed in parallel, but it cannot be scheduled.

**Versus the GraphRAG admissibility paper.** Prior art, as established above.

**Versus a pure silent-degradation taxonomy.** Taxonomies are hard to place without a quantitative result. Leading with the NLI inertness finding plus a prevalence number gives the paper a headline.

This proposal is the only one of the four that is **publishable regardless of any experimental outcome**, because its subject is the measurement apparatus rather than the system.

---

## Risks, stated honestly

1. **The prevalence result may be small.** If most frameworks already window their NLI premises, the headline collapses to a case study. **This must be spot-checked on two or three frameworks before committing** — a day's work, and it is the go/no-go.
2. **Novelty is not fully established.** I searched for the score-composition claim and found prior art. I have *not* exhaustively searched for prior work on NLI truncation in faithfulness metrics. A proper related-work pass over RAGAS/ARES/AlignScore/MiniCheck evaluation critiques is required before writing.
3. **Self-reporting bias.** The measured instances come from one codebase, authored partly with AI assistance. The prevalence scan is what converts this from confession to contribution.
4. **The probes may be considered obvious.** Mitigation: obviousness is the point, and the prevalence number is the evidence that obvious checks are not being run.

---

## Immediate next step

Spend one day running the support-ablation probe against RAGAS and one other framework. If either truncates, the paper is live and worth the five to seven weeks. If both window correctly, drop this proposal and reallocate to the oracle-subgraph experiment.

That is a cheap, decisive test of the paper's central premise — which is the standard this project should have been applying all along.
