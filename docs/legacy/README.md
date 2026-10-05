# docs/

_2026-08-06. Six live files; everything else is history._

| file | what it is |
|---|---|
| **[STATUS.md](STATUS.md)** | The current state. Benchmark, methodology, every result, every limit, how to regenerate. **Start here.** |
| **[TAHI_PITCH.md](TAHI_PITCH.md)** | One page for a reviewer with ten minutes. Mechanisms, results, limits. |
| **[TAHI_ARCHITECTURE.md](TAHI_ARCHITECTURE.md)** | How the code works: the shared question→entity-set step, and the three injection points. |
| **[TAHI_INTEGRATION.md](TAHI_INTEGRATION.md)** | How TAHI drops into an organisation that already runs a KG with a curated ontology, and the three-week test to prove it on their data. |
| **[dashboard.html](dashboard.html)** | The results page. Self-contained, no CDN. |
| **[MRAG.md](MRAG.md)** | Graph-extraction scope proposal for the RAGGA project (separate effort; live docs are in `../maailma/the_machine/RAGGA_*.md`). |

## `legacy/`

Everything else. These describe systems that were never run, results since retracted, or
plans superseded by the work in `STATUS.md`. Kept for history, **not for reference** — do
not quote a number out of `legacy/` without regenerating it first.

Two worth knowing about:

- `legacy/HANDOVER_CRITICAL_REVIEW.md` — the itemised record of what was invented and why
  the prior numbers were void.
- `legacy/GATE1_SPEC.md` — specifies a GraphRAG-Bench run against
  `third_party/graphrag_bench_eval/` that **has still never been executed.**
