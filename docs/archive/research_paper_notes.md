# Research Paper Opportunities

**Date:** 2026-08-01
**Context:** Findings from the OCTO measurement-discipline remediation.

---

## Option 1 — Methods paper (RECOMMENDED)

### Working title
*Silent Degradation in Retrieval-Augmented Generation Evaluation: A Taxonomy and Detection Harness*

### The core finding

A caller-supplied query embedding matched the encoder's dimensionality exactly,
so passing a character-sum hash where a sentence-transformer vector was expected
raised no error, failed no type check, and silently replaced semantic retrieval
with hash retrieval.

This is not a bug report. It is a **class** of failure — *type-compatible
semantic substitution* — that is:

- invisible to unit tests (shapes and dtypes are correct)
- invisible to CI (nothing raises)
- silently confounding for any A/B between retrieval systems

In the OCTO case it meant the graph arm retrieved with a hash while the baseline
used real embeddings, across every comparison ever run. Every negative result was
uninformative and nobody could have known from the output.

### Supporting defects, all found in one codebase in one day

| Defect | Observable symptom | Why it survived |
|---|---|---|
| Substring "exact match" | `EM=1.000` reported alongside `F1=0.028` — impossible | No invariant test asserting EM=1 ⟹ F1=1 |
| Wall-clock reported as TTFT | Terser answers appear to have "faster prefill" | Metric name and measurement never reconciled |
| Silent encoder fallback | `sentence-transformers` import fails (missing FFmpeg for `torchcodec`) → hash encoder substituted | `except Exception` around encoder construction |
| Stub LLM client | All-zeros results file, `avg_tps: 11000.0` | Fallback returns plausible text instead of raising |
| Mislabeled device fallback | "CUDA OOM" on a 14 MB module; actually a 115 GB vLLM arena | Catch-all `except` with a memory-shaped message |
| Set-based token F1 | Repetition inflates score | Used `set` intersection instead of `Counter` |

### Contribution

1. **Taxonomy** of silent-degradation failure modes in RAG evaluation.
2. **Detection harness** (already built in this repo):
   - `octo/eval/preflight.py` — fail-loud dependency and resource checks
   - `octo/eval/manifest.py` — run manifests carrying `encoder_is_fallback`,
     `strict_mode`, `fallback_calls`; `validate()` refuses to write a degraded artifact
   - `octo/eval/report.py` — schema-locked rendering so dropping an unfavourable
     column is a reviewable diff, not a silent omission
   - `tests/test_eval_metrics.py` — regression tests pinning each pathology
   - `tests/test_gcca_falsification.py` — the `@expectedFailure` pattern for
     turning architectural claims into checkable assertions
3. **Empirical prevalence study** — the work that makes it publishable.

### The work required

Clone 15–25 popular open-source RAG / RAG-eval repositories and scan for the
patterns. The headline result would be of the form:

> *N of 20 widely-used RAG evaluation harnesses contain at least one
> silent-degradation defect.*

Prior: substring-EM and silent-encoder-fallback are likely common. That number is
the paper.

### Venues
- NeurIPS Datasets & Benchmarks track
- ACM REP (reproducibility)
- ACL / EMNLP evaluation workshops (RepL4NLP, Insights from Negative Results)
- arXiv preprint immediately regardless

**Effort:** 4–6 weeks. **Odds:** good — reproducibility venues want this and it
is uncatalogued.

---

## Option 2 — Benchmark critique (cheapest; fold into Option 1 as a section)

### Finding
**8 of EnterpriseRAG-Bench's 10 categories are statistically underpowered.**

Power analysis (95% confidence, 80% power), from `octo/eval/stats.py`:

| n | Smallest detectable delta |
|---:|---:|
| 20 | 0.125 – 0.250 |
| 40 | 0.089 – 0.177 |
| 170 (pooled) | 0.043 – 0.086 |
| 500 | 0.025 – 0.050 |

Only `basic` (175) and `semantic` (125) individually support a per-category
claim at typical effect sizes — yet the benchmark's most interesting categories
(`completeness`, `conflicting_info`, `info_not_found`, all n=20) are exactly the
ones practitioners will quote per-category numbers from.

Recommendation the paper would make: report pooled category groups, or expand
the small categories.

The benchmark is v1.0.0 — first-mover advantage, and the authors would likely
welcome it. **Effort:** ~2 weeks. Largely written already.

---

## Option 3 — The OCTO result itself (contingent)

Depends on the run in flight.

- **Positive** (`fact_coverage` up AND `doc_recall` up on the n=170 structural
  pool): a systems paper on typed world models for enterprise multi-source QA.
- **Null**: "graph retrieval does not beat dense retrieval on enterprise
  multi-source QA" — publishable at a negative-results venue. Modest, but real,
  and establishes priority.

**Do not plan around this.** Odds unknown until the run lands.

---

## Caveats

**Timeline.** Peer review is 3–9 months. For the near-term partner/acqui-hire
conversation, an arXiv preprint next month does the job; the reviewed version
arrives long after.

**Authorship.** The work is the human author's. AI assistance was used for code
and analysis; several venues now require that disclosure — a factual note in the
acknowledgements costs nothing and pre-empts the question.

**Single-codebase weakness.** Findings from one repository are anecdote. The
prevalence scan across public repos is what converts it into a result.

---

## Recommendation

**Option 1, with Option 2 as a section.** Writable regardless of tonight's
outcome, genuinely novel, and the artifact (detection harness) already exists.
