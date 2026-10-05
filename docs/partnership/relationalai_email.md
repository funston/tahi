# Cold intro email — Molham Aref, RelationalAI

Long-form brief (send only if asked): `relationalai_brief.md`

Subject line options:
  1. The last hop between your graph and the model
  2. A channel into the LLM that isn't a prompt
  3. Where long context erodes the knowledge graph

---

Molham —

RelationalAI put semantics next to the data. But when the graph finally reaches
a language model, it goes in as text in a prompt: flattened back into prose,
fixed before the first token, competing for context window. That hop is the one
place a longer context window can quietly erode the difference between a
governed knowledge graph and a better retriever.

I'm building the alternative — a channel into the model that isn't a prompt.
Graph neighbourhoods enter the model's internal state through a narrow gated
pathway, re-aimed continuously as it writes. Microsoft Research (KBLaM) and
Google DeepMind (cache augmentation) have both shown the mechanism works on a
frozen model. What nobody has solved is measurement: proving the model leaned on
the injected knowledge rather than answering from its weights. That's what I'm
working on, and it's what your buyers need settled before they'll trust a graph
inside a regulated decision.

Early-stage research, one corpus, real numbers — graph traversal reaches the
right answer in 99% of my test queries. Happy to send the two-page version.

Worth 30 minutes?

Rich Schiavi
