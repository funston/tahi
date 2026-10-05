# TAHI — what was built, how it was tested, what it shows

**Date:** 2026-08-03
**For:** technical review. Read §6 first if you only have five minutes — it lists
the objections we think are strongest against our own result.

---

## 1. TL;DR

We put a knowledge graph inside the token-generation loop of a small language
model by masking the sampler at every decode step to tokens that continue an
entity the graph supports. On 30 biomedical questions:

| arm | model | knowledge access | correct facts | unverifiable statements | coverage |
|---|---|---|---:|---:|---:|
| A | Claude Opus 5 | none | 88 | 77 | 28.0% |
| B | Qwen2.5-1.5B | none | 10 | 91 | 3.2% |
| C | Qwen2.5-1.5B | facts in prompt (**RAG**) | 236 | 1 | 75.2% |
| D | Qwen2.5-1.5B | **sampler masked**, prompt has no facts | 138 | 0 | 43.9% |
| E | Qwen2.5-1.5B | facts in prompt **+ sampler masked** | 299 | 0 | 95.2% |

**The claim we would defend: B → D.** The user prompt is **byte-identical**
between these two arms. The only difference is that D's sampler is masked to
graph entities. Coverage 3.2% → 43.9%, unverifiable statements 91 → 0, and the
knowledge costs **zero context tokens**.

**A claim we thought we could defend and cannot yet: C → E.** We intended these
to differ only by the mask, but their instructions differ too
(`"Answer using only…"` vs `"List every gene…"`). Found while writing §4b.
The trial must be re-run with wording held constant before that +20 is quoted.
See §4c.

**The claim we would NOT defend:** the absolute coverage numbers. See §6.1.

---

## 2. What was built

### 2.1 Graph-constrained decoding — the mechanism

`src/tahi/validate/constrained.py`

A HuggingFace `LogitsProcessor`. Before each token is sampled, it computes which
token IDs would continue some entity name in the graph's answer set, given what
has been generated so far, and sets every other logit to `-inf`.

```python
for step in range(max_tokens):
    logits  = model(input_ids)
    allowed = allowed_next_tokens(generated_so_far, graph_facts)   # graph acts here
    logits[~allowed] = -inf
    next_token = argmax(logits)
```

State is recomputed from the generated tokens each step rather than tracked
incrementally — slower, but immune to desync bugs that silently produce wrong
constraints. Names are tokenized in both sentence-initial and post-separator
forms because tokenizers split them differently. EOS is permitted only at an
entity boundary, never mid-name.

Emits `intervention_rate`: the share of decode steps where the unconstrained
model's argmax was a token the graph forbade. **Measured at 39.3%.** Near zero
would mean the constraint never bound and the arm measured nothing.

No training, no adapters, no gate, no cross-attention.

### 2.2 Entity linking — resolving messy text to a graph node

`src/tahi/validate/linker.py` (embedding version), `TrigramLinker` in
`scripts/run_constrained_trial.py` (the one used).

Character-trigram Jaccard match over node names, filtered by node kind.
Kind filtering is load-bearing: Hetionet contains *dental caries* as both a
Disease and a Side Effect, and without the filter the linker matched the Side
Effect node at score 1.0, which has no disease-gene edges, so the question
silently returned nothing.

### 2.3 Supporting code

| File | Purpose |
|---|---|
| `scripts/run_constrained_trial.py` | The five-arm trial |
| `scripts/probe_linker.py` | Entity-linker robustness probe |
| `scripts/run_coverage.py` | Coverage measurement over a graph |
| `scripts/probe_extractor.py` | Falsification probe for LLM claim extraction |
| `src/tahi/validate/buffer_validator.py` | Validates a generation buffer against the graph (built, not used in this trial) |
| `tests/test_fact_validator.py` | 10 tests, passing |
| `tests/test_memory_symmetry.py` | 8 tests, passing |

---

## 3. Data

**Hetionet v1.0** (Himmelstein et al., *eLife* 2017). Used as-is, nothing added
or removed. Verified by download and count: 47,031 nodes, 2,250,198 edges,
24 relation types.

Two relations, chosen because their ground truth is stable and published:

| Metaedge | Meaning | Edges |
|---|---|---:|
| `CbG` | Compound–binds–Gene | 11,571 |
| `DaG` | Disease–associates–Gene | 12,623 |

**Excluded deliberately:** `CdG`/`CuG` (compound up/down-regulates gene). These
derive from LINCS L1000 assays, where the edge set depends on cell line, dose,
timepoint, and significance threshold. There is no stable fact to score against,
so scoring anything against them would be dishonest. An earlier version of this
work used them and produced numbers we have discarded.

---

## 4. Method

**Questions** are generated mechanically from edge groups with 3–25 targets,
sampled with a fixed seed. 30 questions, 314 gold facts.

**Scoring** is exact string match after normalisation (lowercase, strip
non-alphanumerics). Two buckets only:

- `CERTAIN_CORRECT` — exact match to a curated graph edge
- `MANUAL_CURATION` — everything else

**Nothing is auto-marked wrong.** A model answer that doesn't match may still be
true; Hetionet is incomplete and we have no standing to call it false. Only a
human decides, from `benchmarks/results/constrained_trial/REVIEW.csv`.

**No language model grades anything.** This is deliberate — three prior scoring
instruments failed silently in this repository (§5.3).

**Arm A** (Opus) answers were written to disk before any gold data was displayed.
Three of thirty questions had appeared in an earlier probe where aggregate scores
(not gold sets) were visible; they are flagged in the answers file. Excluding
them, Opus scores 25.9% instead of 28.0% — the direction is unchanged.

---

## 4b. What each arm literally sends to the model

Every arm uses the same system message:

```
Answer with gene symbols separated by commas, nothing else.
If you do not know, answer exactly: I don't know
```

**Arm B — local, no graph.** User message:

```
What genes does the compound Mepyramine bind?
```

**Arm C — facts in prompt (RAG).** The graph's answer set is pasted in as text.
It costs context tokens proportional to the number of facts:

```
What genes does the compound Mepyramine bind?

Knowledge base: HRH1, CYP2D6, HRH2, CHRM1

Answer using only the knowledge base above.
```

Normal decoding. The model may ignore this, contradict it, or add to it — and
on 5 of 30 questions it answered "I don't know" with the facts in front of it.

**Arm D — no facts in prompt, sampler masked.** User message is **byte-identical
to arm B**:

```
What genes does the compound Mepyramine bind?
```

The graph never enters the prompt. It acts only through the `LogitsProcessor`,
which at each step masks the vocabulary to tokens continuing `HRH1`, `CYP2D6`,
`HRH2`, or `CHRM1`. Context cost of the knowledge: **zero tokens.** The model is
not told the facts; it is prevented from emitting anything else.

**Arm E — facts in prompt AND sampler masked:**

```
What genes does the compound Mepyramine bind?

Knowledge base: HRH1, CYP2D6, HRH2, CHRM1

List every gene from the knowledge base above.
```

So "no facts in prompt" means the knowledge is in the *decoder* and costs no
context; "facts in prompt" means it is in the *context window* and costs tokens
proportional to the answer set.

### 4c. A confound in our own C-vs-E claim — found while writing §4b

Arms C and E do **not** use identical prompts:

```
C:  "Answer using only the knowledge base above."
E:  "List every gene from the knowledge base above."
```

`List every gene` is a stronger recall instruction than `Answer using only`.
Some unknown share of E's +20 points may come from that wording rather than from
the sampler mask. **Our claim in §5.1 that C-vs-E isolates the mechanism is
therefore not yet true**, and the trial must be re-run with the instruction held
constant before that number is quoted.

What is *not* affected: the B-vs-D comparison, where the user messages are
byte-identical and the mask is the only difference (3.2% → 43.9%), and the
hallucination result, which is structural.

---

## 5. Results

### 5.1 The one clean comparison

**B → D. User prompts are byte-identical; the sampler mask is the only
variable.**

```
B  no graph                          3.2%   91 unverifiable statements
D  sampler masked, prompt unchanged  43.9%   0 unverifiable statements
```

Same model, same input text, same decoding strategy. The graph acts solely on
the logits, at **zero context cost**. This is the comparison we would put in
front of a skeptic.

**C → E is confounded** (§4c) and should not be quoted until the instruction
wording is held constant:

```
C  facts in prompt                 75.2%   1 hallucination   5 total failures
E  facts in prompt + constrained   95.2%   0                 0
```

One thing here stands on its own regardless: arm C answered "I don't know" on
5 of 30 questions **with the facts sitting in its context window**. Arm D, which
was never shown the facts at all, had zero such failures. Prompted evidence can
be ignored; a masked sampler cannot be.

### 5.2 Hallucination

Across 437 statements from arms D and E, **zero** were entities absent from the
graph. State this correctly: it is a **structural guarantee, not an empirical
finding.** Constrained decoding cannot emit a non-graph token — they are masked
to `-inf`. That is stronger than a measurement, but it is not a surprise.

Unaided, the same 1.5B answered "which genes does Thiamine bind" with
`THAP1, THAP2, … THAP62`. Under the constraint that output is unreachable.

### 5.3 Instruments that failed, and how they were caught

Relevant because it is why §4 uses no learned scoring:

| Instrument | Failure | Probe that caught it |
|---|---|---|
| Lexical overlap metric | Negating **every** gold answer moved the score **0.0000** | Negation probe |
| NLI entailment judge | **+0.826 with AND without** supporting evidence past ~512 tokens | Support ablation |
| LLM claim extractor | 9/9 correct on real entities, **3/9 on invented ones** — recall, not grammar | `probe_extractor.py` |

The third matters architecturally: a model asked to fact-check is using the same
knowledge that produced the error. We abandoned that design.

### 5.4 Entity linking

120 entities × 6 degradations, generated programmatically (character swaps,
drops, doubling, truncation, case) — never hand-written, since choosing
"realistic" phrasings is where an author's expectation leaks in.

| method | correct | confidently wrong |
|---|---:|---:|
| sentence embeddings | 77.4% | 5.7% |
| **character trigrams** | **95.8%** | **2.2%** |

Embeddings are the wrong tool for surface-form matching; `char_swap` was 48.3%
with embeddings and 88.3% with trigrams.

---

## 6. Objections we consider strongest against our own result

### 6.1 The lookup returns the answer key

```python
facts = graph.lookup(subject, relation)   # what arms C/D/E receive
gold  = graph.edges(subject, metaedge)    # what we score against
```

**These are the same query.** `facts == gold` on every row; we verified and
printed this. Questions are generated from graph edges, gold is those edges, and
the system looks up those edges.

So absolute coverage for C, D, and E is close to *"we handed it the answer key
and it repeated it."* **Do not cite those numbers as question-answering
accuracy.**

What survives: the **C-vs-E delta**, because both arms had the answer key.
The +20 measures delivery, not retrieval.

### 6.2 This tests delivery, not retrieval

The subject was named exactly, existed in the graph, and the lookup was a direct
edge query that cannot fail. Ambiguity, multi-hop, incomplete graphs, and wrong
lookups are all absent by construction. The linker probe (§5.4) is the only
retrieval-robustness evidence and it is synthetic.

### 6.3 A sixth arm exists and should not be shown

Arm F constrains to the gold set **and** forbids EOS until every gold item is
emitted. That is `print(gold)` with a language model in the middle. It is
retained for internal diagnostics only. If it appears in a deck, that is an
error.

### 6.4 Scope

n = 30 questions, 314 facts, one graph, one domain, two relation types, one
local model, one frontier model. This is a pilot, not a result.

### 6.5 The guarantee is fidelity, not truth

A model constrained onto a *wrong* graph produces confident, well-formed, wrong
output. Everything here inherits Hetionet's correctness. Also, **polarity is not
interpreted** — the mechanism constrains which entities may be named, not
whether the surrounding claim about them is affirmed or denied.

---

## 7. What we think this does and does not support

**Supported:**

- Masking the sampler to graph entities raises correct-fact output from 3.2% to
  43.9% with a **byte-identical prompt** and zero context cost (B → D).
- Evidence placed in a prompt can be ignored — arm C answered "I don't know" on
  5 of 30 questions with the facts in its context. A masked sampler cannot
  ignore them; arm D had 0 such failures.
- Fabricated entities can be made *structurally impossible*, not merely
  unlikely, without any training.
- A 1.5B model with graph access states more curated facts than a frontier model
  without it. Arm D does this with **no facts in the prompt at all** — 43.9% vs
  28.0% — meaning it costs no context tokens.

**Not supported:**

- Any claim about retrieval quality, multi-hop reasoning, or performance on
  questions we did not generate.
- Any absolute accuracy figure.
- Any comparison against a properly-tuned RAG system on realistic queries.

---

## 8. Next experiment

Use a benchmark somebody else wrote, where gold is not derived from our lookup.
**GeneTuring** (1,600 expert-curated questions, 48,303 human-scored answers,
published baselines for GPT-4o / Claude 3.5 / Gemini) is downloaded and in the
repository at `data/geneturing/`.

Verified blocker: **0 of its 50 disease-gene questions are answerable from
Hetionet**, which holds only 137 common diseases against GeneTuring's rare
Mendelian disorders. PrimeKG (17,080 diseases, 90.8% of Orphanet) is the
candidate replacement, and checking its overlap with GeneTuring is the
go/no-go — the same check that eliminated Hetionet.

Until that runs, §6.1 stands and the honest headline is the C-vs-E delta.
