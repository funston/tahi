# Gretel Synthetic Text-to-SQL

This implementation is a quick SQL grounding benchmark built on Gretel's synthetic text-to-SQL dataset.

What it demonstrates:

- parsing SQL context into a schema snapshot
- comparing naive lexical grounding against OCTO schema grounding
- optionally enriching the OCTO world model with domain and task metadata from the dataset

What it does not demonstrate:

- end-to-end SQL generation accuracy
- native coprocessor mode
- a decisive OCTO win over stronger SQL baselines

The current benchmark is intentionally narrow: it is a fast add-on dataset to pressure-test schema grounding while BIRD remains the more credible SQL benchmark in this repo.

Runner:

```bash
PYTHONPATH=src python examples/run_octo_gretel_ab_benchmark.py --input-json .tmp_gretel_train_100.json --output gretel_ab.json
```
