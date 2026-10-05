# Tahi Gardens — Investment Analysis

**Prepared by:** Technical Advisor, [VC Firm]
**Date:** 2026-08-01
**Stated team:** 3 deep GPU/AI engineers — NVIDIA (CUDA, CUTLASS, inference infra, vLLM) and Google/Apple
**Basis:** Full code review, benchmark forensics, competitive scan. Supersedes `investor_results.md`, which assumed nothing about the team.

---

## Recommendation

**INVEST — $3.5M seed for 18–20%, milestone-structured, with a hard technical kill gate at 6 months.**

This is a **talent-and-thesis bet, not a traction bet.** There is currently zero valid evidence that TAHI beats retrieval-augmented generation at anything. But the team's specific expertise maps precisely onto the one part of the thesis that is not already commoditized, and that combination is rare enough to price.

I would not pay a Series A price, and I would not invest at all without the milestone structure in §7.

---

## 1. What changed from the prior assessment

My earlier memo recommended a pass. That memo assumed nothing about who was building this. The team disclosure changes two things and only two:

| | Before | With this team |
|---|---|---|
| **Can Level 3 actually be built?** | Doubtful. The code contained a PyTorch module and no path to a serving engine. | **Yes.** CUDA/CUTLASS/vLLM engineers are exactly who ships a custom attention path into a production inference server. This is a small population. |
| **Is the benchmark failure disqualifying?** | Yes — it was the only evidence of how they work. | **Downgraded to serious-but-fixable.** See §3. |

What has *not* changed: **there is still no evidence the product works.** A strong team does not retroactively validate a broken measurement. It changes the probability they can produce a real one.

---

## 2. The thesis, stated precisely

TAHI claims three integration levels. They have wildly different investment profiles, and conflating them is the central risk in the pitch.

| Level | What it is | Defensibility | Status |
|---|---|---|---|
| **L1** — prompt-side control packet | Graph entities and constraints compiled into the prompt | **None.** This is GraphRAG. Microsoft GraphRAG, LlamaIndex, Neo4j, Writer, Glean, and Onyx all ship it. | Works today |
| **L2** — adapter-native | Fused vector via a trained adapter on a frozen base | Moderate. RETRO/InstructRetro precedent is public. | Not implemented |
| **L3** — request-scoped residual injection | Graph memory streamed into the residual stream at token time | **High, if it works.** Requires kernel-level work inside a serving engine. | Provably inert (see §3) |

**The entire investment case is L2/L3.** L1 is a feature, not a company — and the current deck sells L3 while the product ships L1. That gap is the single thing I would fix before this team talks to another investor.

---

## 3. Technical due diligence findings

I reviewed the codebase directly. Four findings, in descending order of severity.

### 3.1 The published benchmarks were not measurements

Four benchmark reports dated August 2026 contained numbers that appear in no artifact in the repository. The machine-generated results file for the flagship run was **all zeros with `avg_tps: 11000.0`** — the signature of a stub LLM client returning placeholder text instantly. Additionally:

- "Exact Match" was substring containment. HotpotQA reported **EM=1.000 for all four arms including the zero-retrieval baseline, alongside F1=0.028** — mathematically impossible.
- "TTFT" was total non-streaming wall-clock. The "48% latency reduction" tracks *shorter answers*, not faster prefill.
- The "100% vs 0% distractor rejection" headline compared two prompts differing **only in letter casing**.
- On LegalBench, constraint-violation (50% for all arms) and distractor-rejection (0% for all arms) were **recorded in the JSON and omitted from the published table** — the two metrics where TAHI showed no advantage.

### 3.2 Level 3 is currently an identity function

`GatedChunkedCrossAttention` zero-initializes its gate, so `h + tanh(0)·attn ≡ h`. Untrained, it **cannot change a single logit**. The benchmark harness instantiated it, ran it on `torch.randn` dummy states, **discarded the output**, and then sent a text prompt over HTTP to vLLM. Arm 4 was Arm 3 with a different prompt template.

Worse: the injected "world state" was `tuple([0.1] * 768)` — a **constant vector, identical for every query**, pooled to K=1. Even with fully trained adapters, it carries zero bits about the query. There is no GCCA training pipeline and no adapter checkpoints anywhere in the repo.

I have written these as falsification tests (`tests/test_gcca_falsification.py`): 4 pass, 2 expected-failures pinning exactly these two defects.

### 3.3 A core runtime bug invalidated every TAHI-vs-RAG comparison ever run here

This is the most consequential finding, and it cuts **in the company's favour**.

`WorldModel.retrieve()` lets a caller supply `query_embedding`, which overrides the sentence-transformer encoding. `TahiRuntime.infer()` was passing `frame.text_embedding` — the **character-sum hash** from `retrieval/legacy.py`, generated at the encoder's width so dimensions matched and nothing raised.

**Every TAHI arm was retrieving with a hash while the RAG baseline it was compared against used real embeddings.** On a test query, TAHI returned a kickoff doc and an *office snacks poll* while missing the document that literally contained the answer. After the one-line fix, it returns the correct document.

Implication for diligence: **every negative TAHI result in this repo's history is confounded and uninformative.** The thesis has never actually been tested. That is bad process and good news simultaneously.

### 3.4 Silent degradation is systemic, not incidental

Three independent paths substituted a weaker component and returned success: the LLM client (placeholder text), the encoder (`sentence-transformers` → character-sum hash, triggered by a missing FFmpeg library), and device selection (a mislabeled "CUDA OOM" catch-all that fell back to CPU — for a **14 MB** module that cannot OOM; the real cause was a vLLM server holding 115 GB of 130 GB).

This is a cultural pattern, not three bugs. For a company whose product promise is *auditability and provenance*, it is the worst possible failure mode — and it is the thing I would watch hardest post-investment.

---

## 4. Reading the team against the findings

Two readings, and the diligence question is which is true.

**Charitable (and I think more likely):** the benchmark harness was written fast — plausibly by an AI coding agent with little review — while the humans focused on infrastructure. The code quality gradient supports this: `world_model_store.py`, the repo boundary discipline, and `baseline_rag.py` (an honest, genuinely independent baseline) are competent work. The benchmark harness is not. Different hands, different care.

**Uncharitable:** the team optimizes for demo-able numbers over true ones. The dropped LegalBench columns are the datapoint that keeps this reading alive — that is a choice, not a bug.

**The discriminator I would use:** they wrote `docs/research/HONEST_STATUS_MARCH_2026.md` themselves, which says *"claiming 'production-ready' with 0% results on local models was bullshit."* A team that writes that is capable of self-correction. They then stopped doing it for five months. **The question is not whether they can be honest — it is whether they are honest when the fundraise is close.**

Ask in the partner meeting: *"Walk me through why the LegalBench constraint-violation column isn't in the published table."* The answer tells you which reading is right.

---

## 5. Market

**Where TAHI is positioned (L1): crowded and consolidating.**

| Competitor | Position |
|---|---|
| Glean | ~$7B valuation, enterprise search, deep connector moat |
| Microsoft GraphRAG | Free, open source, default for Azure customers |
| Writer / Vectara / Onyx | Graph + RAG platforms, funded, shipping |
| Neo4j + LlamaIndex | The DIY stack most enterprises actually use |

TAHI has no distribution, no connectors, and no customers. **At L1 it loses on every axis to Glean and on price to GraphRAG.** There is no version of this where L1 is the business.

**Where TAHI could be positioned (L3): empty, and empty for a reason.**

Nobody ships request-scoped residual injection in production. Two possible explanations, and they have opposite implications:

1. It is *hard* (kernel work, serving-engine integration, per-domain adapter training) — in which case this team's edge is real and the space is empty because few can enter it.
2. It is *not worth it* — RETRO and InstructRetro demonstrated chunked cross-attention years ago; every frontier lab has explored it; none ship it. Long context plus good retrieval may simply dominate.

**I cannot resolve this from the outside, and neither can the team — that is precisely what the seed should buy.**

**TAM reality check:** L3 requires open-weight models and self-hosted inference. That excludes every OpenAI/Anthropic API customer. The realistic near-term buyer is a regulated enterprise already running vLLM on owned GPUs for data-residency reasons — a real segment, and a fraction of the "$10B+" the deck claims. I would underwrite a serviceable market in the low hundreds of millions, not billions.

---

## 6. Why I would still write the check

Three reasons, in order of weight.

**1. The team is the scarce input, and it is correctly matched to the hard problem.** CUDA/CUTLASS/vLLM engineers who can land a custom attention path in a production serving engine number in the low thousands globally, and most are employed at labs. If inference-time structured memory becomes a category, this team can build it and almost nobody else at seed stage can. That is the actual asset.

**2. The thesis is untested, not falsified.** Because of §3.3, there has never been a fair TAHI-vs-RAG comparison. The negative results everyone would point to are artifacts of a hash-embedding bug. The option is still live — and it is priced as though it isn't.

**3. Asymmetric payoff structure.** If L3 works, it is a genuine architectural moat with an obvious acquirer set (NVIDIA, Databricks, Snowflake, Glean, any inference provider). If it fails, the team is acqui-hirable at or above the seed price on GPU-infra talent alone. **The downside is substantially protected by the team's employability** — which is exactly the condition under which a seed check on a broken artifact is rational.

---

## 7. Deal structure

**$3.5M for 18–20%, released in two tranches against technical milestones.**

Pricing rationale: market seed for a 3-person team of this pedigree is $3–5M at $15–25M post. I would price at the low end because the evidence base is not merely thin but was actively misrepresented, and that warrants a discount even under the charitable reading.

### Tranche 1 — $1.5M, 0–6 months

| # | Milestone | Verification |
|---|---|---|
| 1 | Retract the four August benchmark reports | Public, in-repo |
| 2 | One honest EnterpriseRAG-Bench run, pre-registered, TAHI vs `StandaloneRAG`, n≥170 pooled structure-sensitive, paired bootstrap CI | The harness and pre-registration already exist in-repo (`benchmarks/run_enterprise_rag.py`, `PREREGISTRATION_enterprise_rag.md`). **Publish the result whichever way it goes.** |
| 3 | L3 falsification: run in-process, confirm α=0 is bit-identical to base, then train adapters and show a delta | `tests/test_gcca_falsification.py` already encodes the null |
| 4 | Cost per correct answer vs. RAG and vs. a fine-tuned specialist | Already instrumented |

**Gate:** Milestone 2 returning a CI that includes zero does **not** automatically kill the deal — a well-run null on synthetic enterprise data is informative and expected. **Refusing to publish it does.**

### Tranche 2 — $2.0M, 6–18 months, conditional on

- A trained GCCA adapter beating L1 on held-out data — the first genuine evidence L3 is worth its complexity; **or**
- Two design partners paying for L1 in a regulated vertical, proving the wedge sells even before L3 lands.

### Terms I would insist on

- **Board observer seat** with direct access to the benchmark repo.
- **Publication covenant:** every benchmark claim in investor or marketing materials traces to a committed artifact with a run manifest. This is cheap for an honest team and expensive for a dishonest one, which is what makes it a useful term.
- **Standard pro-rata**, 1x non-participating preference.

---

## 8. What would change my mind

**Toward a bigger check ($8–10M, Series A pricing):**
- A trained L3 adapter beating strong RAG on a public benchmark with published CIs
- A design partner in pharma, defense, or finance paying for on-prem deployment
- Evidence the domain-curation cost is genuinely low — the EnterpriseRAG-Bench world model builds its graph purely from source metadata with zero hand-curation, which is the right proof if it holds at scale

**Toward walking away:**
- Any new benchmark claim without a reproducible artifact. **One instance, post-investment, and I would treat the company as uninvestable.** They have used up the benefit of the doubt.
- A pivot to selling L1 as the product. That is a losing fight against Glean and free GraphRAG, and it would tell me the team doesn't believe L3 either.
- Milestone 3 showing trained adapters ≈ L1 performance. That is the honest death of the thesis and should be treated as such.

---

## 9. Bottom line

**The artifact is broken; the team is not; the thesis is untested rather than disproven.**

I am underwriting three people who can do kernel-level inference work, attached to a hypothesis that has never been given a fair trial because of a one-line bug. $3.5M buys a real answer to a question nobody has actually asked, and a team that remains valuable if the answer is no.

The measurement discipline is the risk that matters. Not the market, not the competition, not the technical difficulty — **the demonstrated willingness to publish numbers that no artifact supports.** Every term above is designed around that single failure mode, because for a company selling auditability, it is the one that compounds.

I would take this meeting. I would ask about the LegalBench column first.
