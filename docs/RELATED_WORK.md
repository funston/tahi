# Related work

Shortlist assembled 2026-08-21. Grouped by which of our open problems each paper
speaks to. Read GMT and KBLaM in full before touching the GCCA bridge.

## A. Inject structure into activations, not the prompt

**Beyond Prefixes: Graph-as-Memory Cross-Attention (GMT)** — arXiv:2510.08966
(Oct 2025, rev. Mar 2026). Local KG neighbourhood -> compressed "graph memory
tokens" -> token-wise cross-attention at multiple layers. Base LLM frozen; LoRA
applied only to the memory cross-attention. Their stated motivation is ours:
prefix concatenation gives shallow interactions that cannot support fine-grained
evidence retrieval *during* generation. Closest published relative of our design.

**KBLaM: Knowledge Base augmented Language Model** — arXiv:2410.10450, ICLR 2025
(Microsoft Research). KB triples -> continuous key/value pairs via a sentence
encoder plus linear adapters, injected at every attention layer through
"rectangular attention". Cost linear in KB size; 10K+ triples into an 8B model
with an 8K window; updates without retraining.
Borrow: the key/value factorization. Key vector encodes entity+property (the
*index*); value vector carries the property value. Cleaner than what we stack
into banks today.

**DySK-Attn** — arXiv:2508.07185. Dynamic KG plus sparse coarse-to-fine
knowledge attention that narrows to a small relevant subset.
Relevance: our measured gap is ranking, not reach (reach 0.991-0.995; median
target rank 4-of-9 relevance, 11-of-22 continuation). Coarse-to-fine is a
candidate replacement for inverse-degree ranking.

Lineage for the related-work section: KG-Adapter (ACL Findings 2024), GreaseLM,
Graph Neural Prompting.

## B. The "coprocessor" framing

**Deliberation in Latent Space via Differentiable Cache Augmentation** —
arXiv:2412.17747, ICML 2025 (Google DeepMind). A frozen LLM plus an offline
coprocessor that writes latent embeddings into the KV cache, trained end-to-end
under the decoder's LM loss with the decoder frozen. Reduces perplexity and
improves reasoning without task-specific training.
Relevance: precedent for the frozen-decoder + gated-side-module training setup
we already have, and the source of the word "coprocessor".

## C. Semantic caching / KV reuse -- and two warnings

**CacheBlend** — arXiv:2405.16444, EuroSys 2025. Reuses precomputed *non-prefix*
KV caches, selectively recomputing only high-deviation tokens. 2.2-3.3x TTFT,
2.8-5x throughput, F1/Rouge-L loss 0.01-0.03.
Warning that applies to us: naively concatenating independently-precomputed
chunk caches degrades quality -- that is the whole reason CacheBlend exists.
Same class of bug as `_stack_banks` assuming zero-padded slots are harmless
when they take 87.6% of the attention mass.

**Cartridges: long context via self-study** — arXiv:2506.06266. Train a small KV
cache offline per corpus with a context-distillation objective; naive next-token
is not competitive. 38.6x less memory, 26.4x higher throughput.
Suggests a second pre-registered arm: *compile* the graph neighbourhood into a
cartridge offline, versus retrieving it live every 64 tokens.

**CacheClip** — arXiv:2510.10129. Same family, more recent.

## Anchor

**Improving language models by retrieving from trillions of tokens (RETRO)** —
Borgeaud et al., arXiv:2112.04426. Chunked cross-attention, chunk size m=64,
causal offset (chunk C_i retrieves using C_{i-1}).
