# RelationalAI — where TAHI could align

_2026-08-06. Notes for a conversation with the CEO. Based on public material:
`relational.ai/why-rel` and `relational.ai`._

---

## Their position, in their words

- Rel is "a decision agent aligned to your business, **grounded in your semantic model**".
- The premise: LLMs "don't know anything about your business."
- Deployed as a Snowflake native app. Named customers: Blue Yonder, Fox, EY, Ritchie Bros., AT&T.
- Trust story: **"Rel shows you its reasoning"** and **"if Rel gets something wrong, you fix it."**
- Hallucination is addressed by **"superalignment"** — continuous fine-tuning on private data.
- Accuracy claim: "top of the leaderboard" on Spider 2.0 text-to-SQL.

**Absent from the public material:** any regulated-industry compliance framing, any formal
auditability standard, any stated per-customer error-rate methodology.

---

## Openings, ranked by fit

### 1. Automate the correction loop they already describe

Their stated workflow is *"if Rel gets something wrong, you fix it"* — a human catching the
error. The post-generation loop is that same workflow with the semantic model doing the
catching: generate → query the model → diff → hand back only what is provably wrong → re-ask.

This is not a new idea proposed to them. It is automating the loop they already designed and
already tell customers about.

- **Deliver:** the diff-and-correct loop against their semantic model, measured on one
  customer's question set, reported as fixed / broken / McNemar exact.
- **State up front:** measured on one benchmark, n = 100, on a graph that was dataset ground
  truth.

### 2. Sell them the number they do not have

"Top of the leaderboard on Spider 2.0" is a public-benchmark number. No enterprise buyer runs
Spider. AT&T wants the error rate on AT&T's schema, and EY's risk function will eventually ask
for it in writing.

This is the most sellable engagement and the most honest one, because the measurement harness
is the mature part of the work — more mature than the mechanism. Paired arms, held-out
questions, McNemar exact on discordant cells, per-question transitions, `fixed`/`broken`
counts, pre-registered pass conditions.

- **Deliver:** a per-customer eval harness they can run during onboarding, plus a methodology
  document a customer's risk team can read.
- **Why it wins:** pure services, no product dependency, no claim that cannot be defended, and
  it makes us the party that defines how their accuracy is measured.

### 3. Superalignment makes the model *want* to be right; constrained decoding makes it *unable* to be wrong

Explicitly complementary, not competing.

Fine-tuning shifts probabilities — it makes fabrication unlikely, never impossible.
Constrained decoding masks the sampler, so an entity absent from the semantic model is
**unreachable**. Measured intervention rate **0.440**: the constraint overrode the model's own
top choice on 44% of decode steps.

For a Snowflake native app this is a compliance sentence they cannot currently write: *the
agent cannot name a supplier, SKU, account or counterparty that does not exist in your
governed data.*

- **Deliver:** `GraphConstrainedLogits` wired to their semantic model over one entity class.
  The coupling surface is a single function, `supported(question) -> set[str]`.

### 4. Open Telco — a hunch, not a plan

31 fine-tuned models across the whole stack: embedders, rerankers, LLMs, safety variants that
abstain when context looks thin. 326k examples curated by 100+ domain experts from 3GPP,
O-RAN, IETF, GSMA. Reranker MRR@10 0.952. Serious work.

Two observations, neither a criticism:

- **No structured layer anywhere.** Their own summary: the system "relies on retrieved passage
  context rather than structured semantic representations." 3GPP and O-RAN are about as
  structured as a corpus gets — releases, procedures, interfaces, parameter identifiers, and
  formal relationships between them. It reads like a semantic model waiting to happen. Which
  is RelationalAI's business, and AT&T is already their customer.
- **Their own stated limitation:** *"generated content requires verification before operational
  use."* Effectively the same sentence as "if Rel gets something wrong, you fix it." Both
  landed on a human doing the checking.

**The hunch:** with a reranker that good, retrieval is fine — so remaining errors have moved
downstream of ranking. Worth knowing how often a generated answer names a spec, release,
interface or parameter appearing in none of the retrieved passages. If that is meaningfully
above zero, no further reranking touches it, because it is a decode-time property.

Their datasets are public on HuggingFace (`OTel-LLM`, `OTel-Reranker`, `OTel-Embedding`,
`OTel-Safety`), so this is checkable without AT&T's involvement. **Not started. Concept only.**

### 5. Legend — where this might just fall out

The stated direction has been to train or fine-tune something to learn Pure and do
text-to-Legend. Worth asking whether that is the hard way round.

- **The graph already exists and is formal.** A Legend model is a typed class / property /
  association graph, version-controlled through SDLC, serialisable to JSON Schema, Protobuf and
  Avro. Pure is "an immutable functional language based on UML and inspired by OCL." Nothing to
  extract — which is exactly the precondition our MetaQA results had to borrow from a benchmark.
- **The compiler is a free, exact verifier.** Our correction loop hands the model a list of
  what is provably wrong. Legend's compiler already produces that, and better:
  `Class Person has no property 'birthDate'`, type errors, multiplicity violations. No LLM
  judge anywhere.
- **Fine-tuning looks like the harder road.** A trained model learns one firm's Legend model;
  the next firm has a different one. SDLC changes make it stale. Pure corpora are thin — no
  Spider-sized training pile exists. Constraining the decoder to the grammar plus whatever
  model is loaded needs no examples and works on a model it has never seen.
- **The eval set may already exist.** Legend Services are curated, tested, version-controlled
  queries in the customer's repo. Turn one into a natural-language question and see whether it
  round-trips. Ground truth is the real query and its real output — no judge, no benchmark to
  build.
- **Entitlements could become a decode-time property.** Legend already carries ownership and
  validation constructs. Filter the allowed vocabulary by the caller's entitlements and the
  agent cannot *construct* a query over data it should not see. For the FINOS banks that may
  matter more than any accuracy figure.

**Unverified:** whether Pure's grammar is extractable in a form a constrained decoder can use,
and the fact that a query can compile cleanly and still answer the wrong question. **Not
started. Concept only.**

### 6. Audit how "grounded" actually works


Worth asking directly, because the answer determines whether anything else matters: **how does
the semantic model reach the generation?**

If it is context assembled into a prompt — the common answer — then the measured result is
directly on point. Same graph, same query, same model, same candidates: **0.18** pasted into
the prompt, **0.79** handed back as a diff of errors. How the knowledge reaches the model beat
what was retrieved by a factor of four.

Cheap to test on their stack, and it either finds real headroom or it does not.

### 7. Text-to-SQL schema constraint

Constrained decoding over a schema so the model cannot emit a table or column that does not
exist. Lower priority than Legend, which covers the same ground more specifically. A
SQL/Spider coprocessor was removed from this repo's working tree on 2026-08-06 as legacy and
is recoverable from git history.

---

## How to open

Not as a pitch — as a result.

> "I ran an experiment that's relevant to something you're building. A knowledge graph
> checking an LLM's answer after generation fixed 77 of 100 wrong answers and broke zero. Zero
> is the number I care about. I also built the cross-attention version everyone assumes is the
> right answer, trained it, and it did nothing — +0.002. Want to see both?"

Leading with the failure is what makes the success credible, and it inoculates against the
weaknesses he will find anyway.

**Then give the honest boundary:** every number rests on MetaQA, where the graph is the
dataset's ground truth. Extraction quality was never tested, and our own extraction on
enterprise prose scored −0.12 against its source. **That is precisely the problem RelationalAI
has already solved.** The condition that makes these results clean is the condition their
customers live in permanently. That is the reason the conversation is with them.

---

## Do not bring

| | why |
|---|---|
| GCCA | built, trained 15 epochs, measured, moves exact match +0.002. Only useful as the credibility move above. |
| Graph extraction | their whole business is already having the semantic model. Proposing to extract one is competing with them, badly. |
| `world_state.py` expansion | three failing tests say it does not change retrieval. |
| Accuracy comparisons | 0.79 is 35 points below published MetaQA state of the art. The claim is `broken = 0`, not the accuracy figure. |

---

## Objections he will raise

**"Our semantic model already constrains this."** Expressing a constraint in a query language
is not the same as enforcing it on a token stream. The model can still fabricate; the sampler
does not consult Rel.

**"n = 100, one benchmark."** Correct. Which is why the first engagement is a measurement
sprint on real data, not a licence.

**"We fine-tune for this."** Different guarantee, not a competing one. See opening 3.

---

Evidence: `docs/STATUS.md` · architecture: `docs/TAHI_ARCHITECTURE.md` ·
integration surface: `docs/TAHI_INTEGRATION.md`

---

_Nothing in openings 4–7 is built or started. Concepts only, for conversation._
