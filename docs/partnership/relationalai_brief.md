# Tahi × RelationalAI — one-paragraph brief

Audience: Molham Aref, Founder & CEO, RelationalAI. Register: strategic, not technical.
The engineering account — including the open defects in the current retrieval
path — lives in `docs/TAHIRETRO_SPEC.md` and `tests/test_graph_retrieval.py`.
Those are deliberately absent here; this is a research-partnership pitch, not a
code review.

---

RelationalAI's thesis — put semantics next to the data, inside the customer's
governance boundary — is right, and it has one unprotected hop. When the
knowledge graph finally reaches a language model, it does so as text pasted into
a prompt: flattened back into prose, fixed before the first word is generated,
and competing for context window with everything else. That hop is where the
differentiation is most exposed, because every quarter that context gets longer
and cheaper, "just paste more text" looks more like an adequate substitute for a
governed graph — and it quietly reduces a reasoning engine to a better
retriever, which is a commodity race. **Tahi is a second channel into the model
that is not a prompt.** Graph neighbourhoods enter the model's internal state
through a narrow, gated pathway and are re-aimed continuously as the model
writes, so the graph sits inside the generation loop rather than queued in front
of it. Three things follow that a longer context window cannot erode.
*Governance:* the graph crosses as numbers, never as readable text handed to a
third-party context window — the same no-egress posture Snowflake-native design
is sold on, extended to the last hop. *Auditability:* the gate yields a measured
quantity for every generated word — how much the graph moved this token —
turning "trust our retrieval" into per-token attribution that no RAG vendor can
produce and that regulated buyers pay for. *Economics:* cost scales with the size
of the knowledge base, not with the square of the prompt, so the graph stops
paying context-window rent. The retrieval half is already measured and working:
our graph traversal reaches the correct answer in 99% of test queries, well ahead
of vector search on the same corpus. The open problem — and the reason this is
research rather than a product — is the injection interface itself: how to hand
structured knowledge to a frozen model through a channel narrower than a prompt,
and how to prove the model actually used it. That interface is an active
frontier, not a speculation. Microsoft Research has demonstrated knowledge-base
triples entering every attention layer of a frozen model at a cost that scales
linearly with the size of the base rather than quadratically with the prompt.
Google DeepMind has demonstrated a separate coprocessor writing directly into a
frozen model's working memory and measurably improving its reasoning. Published
work through 2026 extends the same mechanism specifically to graph
neighbourhoods. What none of it has settled is **measurement** — whether the
model leaned on the injected knowledge or quietly ignored it and answered from
its weights, which is precisely the question an enterprise buyer needs answered
before trusting a governed graph in a regulated decision. That is the gap we
propose to close, with an instrument that reports per token how much the graph
moved the answer and a counterfactual test that swaps the real knowledge for
noise and measures what the model loses. We are seeking research funding and a
design partnership, and RelationalAI is the only company whose substrate this
architecture already assumes.

---

## Citations for the three claims above

1. **Knowledge-base triples into every attention layer, linear in KB size.**
   KBLaM: Knowledge Base augmented Language Model — arXiv:2410.10450, ICLR 2025,
   Microsoft Research. KB triples become continuous key/value pairs via a
   sentence encoder plus linear adapters, injected through "rectangular
   attention". 10K+ triples into an 8B model with an 8K context window; updates
   without retraining.

2. **A coprocessor writing into a frozen model's working memory.**
   Deliberation in Latent Space via Differentiable Cache Augmentation —
   arXiv:2412.17747, ICML 2025, Google DeepMind. An offline coprocessor augments
   a frozen decoder's KV cache with latent embeddings, trained end-to-end under
   the decoder's own loss. Reduces perplexity and improves reasoning across
   tasks with no task-specific training.

3. **The same mechanism applied to graph neighbourhoods.**
   Beyond Prefixes: Graph-as-Memory Cross-Attention for Knowledge Graph
   Completion with LLMs — arXiv:2510.08966 (Oct 2025, rev. Mar 2026). Local
   graph structure becomes explicit graph memory tokens injected by token-wise
   cross-attention across layers, base LLM frozen. Their stated motivation is
   ours: prefix concatenation gives shallow interactions that cannot support
   fine-grained evidence retrieval during generation.

Supporting:
- **The re-aiming schedule.** RETRO — Borgeaud et al., arXiv:2112.04426.
  Retrieval re-issued every 64 generated tokens, keyed on what the model just
  wrote, injected by chunked cross-attention.
- **Selection over a live KG is unsolved and being worked.** DySK-Attn —
  arXiv:2508.07185. Coarse-to-fine sparse attention over a dynamic knowledge
  graph.
- **Naive approaches measurably lose quality.** CacheBlend — arXiv:2405.16444,
  EuroSys 2025. Concatenating independently precomputed caches degrades output;
  selective recomputation recovers it. Evidence that the interface is a real
  engineering problem with real money behind solving it.
