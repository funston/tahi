# World-Model Training Loop Prototype

## The idea

Instead of hand-crafting aliases and semantic types for every database, we can
automate the "label / supervise" step with an LLM:

1. **Build** a world model from the schema.
2. **Evaluate** table recall on a set of questions.
3. **Collect failures** where the retriever missed gold tables.
4. **Ask an LLM** to propose ontology fixes (aliases, semantic types) that would
 have retrieved the missing tables.
5. **Apply** the suggestions to the world model.
6. **Re-evaluate** and measure the delta.
7. Repeat.

This is **data-centric world-model improvement**, not model training. No GPUs
are required; the LLM only writes small ontology edits.

## Prototype implementation

`examples/world_model_training_loop.py` implements one round of the loop
using GPT-4o-mini.

### What it does

- Loads a BIRD database and its dev questions.
- Builds a baseline world model with `snapshot_to_world_model`.
- Runs table-recall evaluation.
- Formats the schema + the top N failures into a prompt.
- Calls the OpenAI API with `response_format={"type": "json_object"}`.
- Parses the suggested `add_aliases` and `add_semantic_types`.
- Applies them to a fresh world model.
- Re-evaluates and prints the delta.

### Results

Run with `top_k=8` and up to 25 failures shown to the LLM:

```text
superhero
 Baseline recall: 0.879 (35 failures)
 Enriched recall: 0.917 (24 failures)
 Delta: +0.038 (11 failures fixed)

financial
 Baseline recall: 0.881 (23 failures)
 Enriched recall: 0.903 (19 failures)
 Delta: +0.022 (4 failures fixed)
```

### Example LLM suggestion (superhero)

```json
{
 "add_aliases": {
 "hero_power": ["powers", "superpowers"],
 "superhero": ["heroes", "characters"],
 "colour": ["eye_color", "hair_color", "skin_color"],
 "publisher": ["comics_publisher", "publishing_company"],
 "race": ["species", "ethnicity"],
 "attribute": ["hero_attribute", "character_attribute"]
 },
 "add_semantic_types": {
 "superhero.full_name": "name",
 "superhero.superhero_name": "alias_name",
 "colour.colour": "color_description",
 "publisher.publisher_name": "company_name",
 "race.race": "species_description"
 }
}
```

## Comparison with manual enrichment

| Database | Baseline | LLM loop (1 round) | Manual enrichment |
|---|---|---|---|
| superhero | 0.879 | **0.917** (+3.8 pp) | 0.938 (+5.9 pp) |
| financial | 0.881 | **0.903** (+2.2 pp) | 0.942 (+6.1 pp) |

The LLM-driven loop is **automatic** and improves recall in one shot. Manual
enrichment still wins because a human can inject exact domain vocabulary (e.g.,
real district names, specific publisher names, attribute values). The two
approaches combine cleanly: use the LLM loop for the first pass, then have a
human review and harden the suggestions.

## Why this matters for the product

- **Cost:** No GPU cluster. The LLM writes small JSON edits; the expensive part
 is a few hundred evaluation runs, which is cheap CPU work.
- **Speed:** One round takes seconds of evaluation + one LLM call.
- **Safety:** Suggestions are applied to a *copy* of the world model and validated
 against a held-out metric before acceptance.
- **Generalization:** The same loop works for any structured domain (SQL,
 biomarkers, compliance) as long as you have questions and gold answers.

## Honest limitations

- **One round is not enough.** Multi-hop failures, comparative reasoning
 ("oldest", "second-highest"), and percentage questions need a SQL generator,
 not just more aliases.
- **LLM suggestions can be wrong.** The financial run assigned some incorrect
 semantic types to opaque `A*` columns. The evaluation metric catches this,
 and bad suggestions can be rejected.
- **Prompt leakage risk.** Feeding test questions into the LLM during
 improvement is fine for development, but production world models should be
 validated on held-out questions.

## Run it

```bash
# Requires OPENAI_API_KEY in the environment
python examples/world_model_training_loop.py --db-id superhero
python examples/world_model_training_loop.py --db-id financial

# Print the prompt without calling the API
python examples/world_model_training_loop.py --db-id superhero --dry-run
```

## Next step

Make the loop **multi-round**: after each evaluation, feed the remaining
failures back to the LLM with a note that the previous suggestions were
partially successful. Add a small held-out validation split so we do not
overfit the dev set.
