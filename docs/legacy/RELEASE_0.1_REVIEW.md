# OCTO 0.1 Review Cut

## Scope

This `0.1.0` review cut is intentionally narrow:

- `src/octo/` is the pure core package
- `implementations/` contains first-party reference world models
- Spider remains isolated as a benchmark implementation, not the core story
- `bio` and `mass_spec` are the primary demo surfaces for market and community feedback

## Included In This Cut

- pip-installable core package metadata in `pyproject.toml`
- explicit core version export from `octo.__version__`
- optional ANN dependency handling in the retrieval layer
- biomedical reference implementation with:
 - biomarker interpretation
 - target profiling
 - external evidence-record ingestion
- mass spectrometry reference implementation with:
 - spectrum interpretation
 - analyte profile
 - explicit RAG baseline comparison

## Demo Commands

Core hello-world:

```bash
PYTHONPATH=src python examples/hello_world_coprocessor_demo.py
```

Bio biomarker demo:

```bash
PYTHONPATH=src python examples/bio_biomarker_demo.py --mode biomarker --case-id demo_her2_breast
```

Bio ingest demo:

```bash
PYTHONPATH=src python examples/bio_ingest_demo.py --target BRAF --disease Melanoma
```

Mass spec spectrum demo:

```bash
PYTHONPATH=src python examples/mass_spec_demo.py --mode spectrum --case-id demo_glucose_sodium
```

## Review Questions

- Is the core/runtime boundary now clean enough to publish as the open-source heart of the project?
- Are `bio` and `mass_spec` compelling enough as first public reference world models?
- Does the repo now make the anti-RAG argument concretely rather than rhetorically?
- Which reference implementation should be the first public blog post: `bio` for investor narrative, or `mass_spec` for sharper technical differentiation?

## Known Gaps

- Spider accuracy is not the focus of this release cut.
- Packaging has not yet been exercised through a full wheel build/install test.
- The whitepaper is closer to the current architecture, but still a review draft rather than a polished publication artifact.
