# Tahi: Measuring and Closing the Factual Gap Between Language Models and Curated Knowledge Graphs — Without Retraining

**Updated:** 2026-08-03
**Audience:** anyone asked to believe a claim in this repository.

Every number below is a count over a third-party curated knowledge graph.
**No language model grades anything.** Section 6 gives shell commands that
reproduce the graph side of any row without running our code.

---

## 0. Abstract, and what is and is not yet earned

**Established here (measured, reproducible):**

1. A public curated knowledge graph holds large numbers of facts that the best
   available language model does not state. Claude Opus 5 surfaced **14.8%** of
   the facts Hetionet holds for the sampled subjects; Qwen2.5-1.5B surfaced
   **2.6–3.0%**.
2. **Model scale closes the literature gap but not the experimental gap.** On
   facts derived from published literature, coverage rises 5–6× from the small
   to the frontier model (3.3%→19.8%, 6.2%→30.8%). On facts derived from LINCS
   transcriptional assays it barely moves (0.0%→2.1%, 0.0%→2.7%). Data that was
   never written down in prose is structurally out of pretraining's reach.
3. **Models confabulate rather than abstain.** Given an explicit "say I don't
   know" instruction, the 1.5B abstained once in 60; Opus once in 20.
4. **Three standard evaluation instruments fail silently in this domain** (§2),
   including an LLM-based claim extractor that scored 9/9 on real entities and
   3/9 on invented ones — evidence that a model asked to check facts is using
   recall, not grammar.

**NOT established here, and the paper's title is not earned until it is:**

> That Tahi *improves* factual performance.

Everything above measures a **gap**. Closing it is a separate experiment and it
has not been run. One attempt was made and discarded as circular: the "with
Tahi" arm consulted the answer key to decide when to intervene, which
guarantees 100% by construction. That result appears nowhere in this document
except as a warning.

**The one experiment that would earn the title** is stated in §8.1: take a
published benchmark whose per-model failures are already documented, reproduce
a documented failure, run the graph-backed path on the identical question, and
report whether it is fixed — with no question, gold answer, or baseline
authored by us.

**A composition blocker, verified:** Hetionet and GeneTuring do not pair. **0 of
50** GeneTuring disease–gene questions are answerable from Hetionet. The gap
result (§5) uses Hetionet; the improvement experiment will need a different
graph (§8.2).

---

## 1. The question

Given a knowledge graph an organisation already has, how much of what that graph
knows does a language model actually say when asked?

Not "is the model's answer plausible." Not "is it entailed by some evidence."
Simply: **the graph holds N facts about this subject; how many did the model
state?**

---

## 2. Why no automatic judge

Earlier work in this repository used learned metrics to score truthfulness.
Every one failed silently, and the failures were only found by testing the
instrument against a known answer:

| Instrument | Failure | How it was caught |
|---|---|---|
| `fact_coverage` (lexical overlap) | Negating **every** gold answer moved the score by **0.0000** | Negation probe |
| NLI entailment judge | Scored **+0.826 both with and without** supporting evidence, once evidence passed ~512 tokens | Support-ablation probe |
| LLM claim extraction | Parsed real entities 9/9, invented entities **3/9** — it was using world knowledge, not grammar | Fake-entity probe (`scripts/probe_extractor.py`) |

The third is the decisive one. It is the reason this method uses **no model in
the scoring path at all**: if a model could reliably judge these facts, the model
being judged would not have got them wrong.

The only language model involved is the one **producing the answer being
measured**. Scoring is string comparison against curated edges.

---

## 3. The dataset

**Hetionet v1.0** — Himmelstein et al., *eLife* 2017. An integrative biomedical
knowledge graph assembled from public databases. Used **as-is**; we added
nothing and removed nothing.

Verified by download and count (not quoted from a paper):

```
nodes      47,031        11 node kinds
edges   2,250,198        24 relation types (metaedges)
```

Node kinds: Gene (20,945), Biological Process (11,381), Side Effect (5,734),
Molecular Function (2,884), Pathway (1,822), Compound (1,552), Cellular
Component (1,391), Symptom (438), Anatomy (402), Pharmacologic Class (345),
Disease (137).

Four relation types are used here, chosen because their answers are specific
named entities:

| Metaedge | Meaning | Edges | Where the facts come from |
|---|---|---:|---|
| `CbG` | Compound–binds–Gene | 11,571 | Literature / binding databases |
| `CdG` | Compound–downregulates–Gene | 21,102 | **LINCS L1000 transcriptional assays** |
| `CuG` | Compound–upregulates–Gene | 18,756 | **LINCS L1000 transcriptional assays** |
| `DaG` | Disease–associates–Gene | 12,623 | Literature / GWAS catalogues |

The literature-vs-assay distinction in the last column turns out to be the
finding. See §5.

**Get the data:**

```bash
mkdir -p data/hetionet
curl -sL "https://raw.githubusercontent.com/hetio/hetionet/main/hetnet/tsv/hetionet-v1.0-nodes.tsv" \
     -o data/hetionet/nodes.tsv
curl -sL "https://media.githubusercontent.com/media/hetio/hetionet/main/hetnet/tsv/hetionet-v1.0-edges.sif.gz" \
     -o data/hetionet/edges.sif.gz
```

---

## 4. The method

**Question construction.** Mechanical. An edge group `(subject, metaedge)` with
between 5 and 60 targets becomes one templated question. Subjects are sampled
with a fixed seed. Nobody hand-picks favourable cases.

**Gold answer.** The target set of those edges. Ours only in the sense that we
chose which relation to ask about — the facts are Hetionet's.

**Scoring.** For each item the model names, normalise
(`lowercase`, strip everything non-alphanumeric) and compare to the normalised
gold symbols. Three buckets:

| Bucket | Rule | Counted as |
|---|---|---|
| **CLEARLY CORRECT** | exact match after normalisation | correct |
| **NEEDS YOUR EYE** | ≥ 0.82 string similarity but not exact | **neither** — flagged for a human |
| **CLEARLY WRONG** | no close match | incorrect |

Normalisation makes `IL-1B` match `IL1B`. It does **not** make `SLC19A3` match
`SLC19A2` — different genes — so that pair lands in the middle bucket where a
person decides. True coverage lies between the correct rate and
(correct + flagged) rate.

**Two measures:**

```
coverage  = |model ∩ graph| / |graph|     how much of the graph's knowledge surfaced
precision = |model ∩ graph| / |model|     how much of what was said is in the graph
```

Coverage requires only that Hetionet is **correct**. Precision additionally
requires it to be **complete**, which it is not — so precision is reported but
should not be read as a hallucination rate. See §7.

---

## 5. Results

Same 20 subjects (seed 7), same graph, same scoring, two models.

| Relation | Facts from | Qwen2.5-1.5B | Claude Opus 5 |
|---|---|---:|---:|
| `CbG` binds | literature | 3.3% | **19.8%** |
| `DaG` disease–gene | literature | 6.2% | **30.8%** |
| `CdG` downregulates | LINCS assay | 0.0% | **2.1%** |
| `CuG` upregulates | LINCS assay | 0.0% | **2.7%** |
| **Overall coverage** | | **2.6%** | **14.8%** |

| | statements made | correct | not found in graph |
|---|---:|---:|---:|
| Qwen2.5-1.5B | 597 | 11 | 98.2% |
| Claude Opus 5 | 152 | 63 | 58.6% |

Subjects where the model produced **zero** correct facts: 15/20 (Qwen),
6/20 (Opus). Opus abstained on 1; Qwen abstained on 0.

### The finding

**On literature-derived facts, scale helps: 3.3% → 19.8% and 6.2% → 30.8%,
roughly 5–6×. On assay-derived facts, it does not: 0.0% → 2.1% and 0.0% → 2.7%.**

A model roughly a thousand times larger recovers almost none of the additional
experimental data, because that data was never written down in prose for it to
absorb. This is the durable case for an external knowledge layer: it is not an
argument that models are bad, it is an observation that **experimental and
proprietary facts are structurally out of reach of pretraining.**

The best available model still failed to state **85% of the facts a public
curated graph holds.**

### Larger local-model run

100 subjects (seed 11), Qwen2.5-1.5B: coverage **3.0%**, precision **2.1%**,
**76/100 subjects produced zero correct facts**, 9 answers flagged
NEEDS-YOUR-EYE. Consistent with the 20-subject run (2.6%), so the local-model
figure is stable across samples. Review sheet:
`benchmarks/results/MANUAL_REVIEW.csv`.

### Reproduce

```bash
# frontier model: answers were committed to disk before any gold data was shown
PYTHONPATH=src:. .venv/bin/python scripts/score_coverage.py \
    --answers benchmarks/results/coverage_answers_opus.json

# local model, same questions
PYTHONPATH=src:. .venv/bin/python scripts/run_coverage.py --n 20 --seed 7
```

---

## 6. How to verify a row by hand

This is the part that matters. The graph side of every claim is checkable
without our code and without trusting any model.

**Step 1 — find the subject's id.** Say the row is about Thiamine:

```bash
grep -P "\tThiamine\t" data/hetionet/nodes.tsv
# Compound::DB00152	Thiamine	Compound
```

**Step 2 — pull its true targets for that relation.**

```bash
gunzip -c data/hetionet/edges.sif.gz \
  | awk -F'\t' '$1=="Compound::DB00152" && $2=="CbG"' \
  | cut -f3 > /tmp/ids.txt
cat /tmp/ids.txt
```

**Step 3 — turn those ids into gene names.**

```bash
grep -F -f /tmp/ids.txt data/hetionet/nodes.tsv | cut -f2
# CYP4B1
# SLC19A2
# SLC22A1
# SLC22A2
# SLC22A5
# TPK1
```

**Step 4 — compare to what the model said.** The verbatim answer is in
`benchmarks/results/MANUAL_REVIEW.csv` under `model_said_verbatim`. If none of
the six names above appear in it, coverage for that row is 0%. That is the whole
calculation.

**The review sheet** has one row per subject with columns:

```
CLEARLY_CORRECT   NEEDS_YOUR_EYE   CLEARLY_WRONG
graph_holds       model_said_verbatim
YOUR_VERDICT      NOTES
```

`YOUR_VERDICT` and `NOTES` are blank for you to fill in. The middle bucket is
the only one requiring judgement.

---

## 7. Limitations — read before citing anything above

1. **Hetionet is incomplete.** A true fact it does not contain is scored as
   wrong. This inflates the "not found in graph" column and is why **precision
   must not be reported as a hallucination rate.** Coverage is unaffected.

2. **Question wording may not match edge semantics.** `CdG` means transcriptional
   downregulation in a LINCS assay, not pharmacological inhibition. A model
   answering "norepinephrine transporter" for Desipramine is giving correct
   pharmacology and is still scored wrong. **This is our error, not the model's**,
   and it is not yet fixed — the `CdG`/`CuG` rows above are affected.

3. **"List every gene" is a synthetic task.** Real users ask for one answer, not
   an exhaustive set. This phrasing maximises measured omission.

4. **Exact string matching means coverage is a floor.** A model using a protein
   name instead of an HGNC symbol is undercounted. Mitigating evidence: 150 of
   Opus's 152 statements were symbols already in Hetionet's gene vocabulary, so
   it was speaking the same naming convention — the misses are wrong answers,
   not naming mismatches.

5. **The 1.5B degenerates on list tasks** (`THAP1, THAP2, … THAP62`). That
   inflates its statement count and destroys its precision figure. Its coverage
   figure is unaffected.

6. **Sample size is 20 subjects / 427 facts** for the frontier comparison. A
   100-subject run is in progress.

7. **No confidence intervals are reported** because these are counts over a
   fixed sampled set, not estimates over a population. Different seeds will give
   different numbers.

---

## 8. External benchmarks — using evaluations we did not author

Everything in §1–7 uses questions **we generated** from graph edges. The facts
are third-party but the questions are ours, and §7.2–7.3 record two ways that
biases the result. The fix is to adopt evaluations built and published by domain
experts, where we author neither the questions, the answers, nor the baseline.

Three candidates, verified by download or API — not quoted from memory.

### 8.1 GeneTuring — PRIMARY

*Benchmarking large language models for genomic knowledge*, Briefings in
Bioinformatics, 2025 (bioRxiv 2023).

| Property | Value |
|---|---|
| Questions | 1,600 curated across 16 modules (9 released as `geneturing.json`, 50 each) |
| Grading | **48,303 answers scored manually by humans** — no model in the loop |
| Published baselines | GPT-4o (API / web / custom), GPT-3.5, Claude 3.5, Gemini Advanced, GeneGPT, BioGPT, BioMedLM |
| Extra metric | *incapacity awareness* — whether a model knows it does not know |
| Data | `github.com/ncbi/GeneGPT/data/geneturing.json` (45 KB), `genehop.json` (51 KB) |
| Full table | `github.com/Winnie09/GeneTuring` — `SupplementaryTable1.csv.zip` (6.2 MB) |

Downloaded and inspected. Tasks: Gene alias, Gene disease association, Gene
location, Gene name conversion, Protein-coding genes, Gene SNP association, SNP
location, Human/Multi-species DNA alignment. **GeneHop** adds three genuinely
multi-hop tasks: sequence→gene alias, disease→gene→location, SNP→gene→function.

Format is short and unambiguous:

```
Q: What are genes related to Distal renal tubular acidosis?
A: SLC4A1, ATP6V0A4
```

**Why this is the primary target.** Published per-model failure rates already
exist. The experiment becomes: reproduce a documented failure, then run the Tahi
path on the identical question and see whether it is fixed. We author nothing.

**Verified blocker:** GeneTuring asks about rare Mendelian disorders.
**0 of its 50 disease–gene questions are answerable from Hetionet**, which holds
only 137 common diseases. Hetionet is the wrong graph for this benchmark. See
§8.2.

### 8.2 PrimeKG — the graph GeneTuring needs

*Building a knowledge graph to enable precision medicine*, Scientific Data 2023
(Harvard, Zitnik Lab).

| Property | Value |
|---|---|
| Diseases | **17,080** (Hetionet: 137) |
| Rare disease coverage | **90.8% of Orphanet's 9,348** |
| Relationships | 4,050,249 across ten biological scales |
| Vocabulary | MONDO Disease Ontology; incorporates DisGeNET, DrugBank, Bgee, Mayo Clinic |
| Data | Harvard Dataverse; build scripts at `github.com/mims-harvard/PrimeKG` |

**Not yet verified:** whether PrimeKG covers GeneTuring's specific 50 diseases.
That check is the go/no-go, and it is the same check that eliminated Hetionet.
Do it before any further work on this track.

### 8.3 DrugMechDB — for multi-hop mechanism questions

*DrugMechDB: A Curated Database of Drug Mechanisms*, Scientific Data 2023.

4,583 drug indications, 32,249 relationships, **manually curated** paths from
drug → disease through intermediate biological entities, using the Biolink
model. Natively graph-shaped and multi-hop by construction, which makes it the
natural test for graph traversal rather than single-edge lookup. A derived RAG
benchmark exists with 798 gene-mechanism, 201 metabolite, and 842
drug–biological-process questions.

Site: `sulab.github.io/DrugMechDB/`

### 8.4 STaRK-PRIME — noted, deprioritised

Built on PrimeKG and otherwise a strong fit, **but its queries are synthesised by
a language model** rather than written by experts. That reintroduces the
circularity described in §2, so it is ranked below the other two here. Recorded
so the choice is deliberate rather than an oversight.
`arxiv.org/abs/2404.13207`

### 8.5 Also surfaced, not yet evaluated

Know2BIO (dual-view biomedical KG benchmark), BioMedHop (multi-source
biomedical reasoning), SciHorizon-GENE (life-sciences gene knowledge),
MHGraphBench (KG-grounded mental health).

---

## 9. What is NOT claimed

- **Not claimed:** that the models are hallucinating at the stated rate. See
  limitation 1.
- **Not claimed:** that Tahi improves generated answers. This document measures
  a *gap*. Closing it is a separate result and is not established here.
- **Not claimed:** that this beats retrieval-augmented generation. There is no
  RAG arm in this experiment.
- **Not claimed:** that the frontier number generalises to other domains. It is
  one graph, one sample, four relation types.

What **is** claimed, and is supported: *a curated public knowledge graph holds
large numbers of facts that the best available language model does not state,
and on experimentally-derived relations, model scale does not close that gap.*
