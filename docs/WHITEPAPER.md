# Whitepaper

The current paper draft is:

- [OCTO Whitepaper v2](/Users/richiek/work/bender/whitepaper/OCTO_whitepaper_v2.md)

## What The Paper Covers

- why implicit LLM world models are weak interfaces
- why OCTO is not just RAG
- why runtime world models can be better than retraining for specialized domains
- how OCTO is intended to integrate natively into open-weight model runtimes

## What To Read First

If you are new to the repo:

1. [Quick Start](/Users/richiek/work/bender/docs/QUICKSTART.md)
2. [Tutorial](/Users/richiek/work/bender/docs/TUTORIAL.md)
3. [Architecture](/Users/richiek/work/bender/docs/ARCHITECTURE.md)
4. [Integration Levels](/Users/richiek/work/bender/docs/INTEGRATION_LEVELS.md)
5. then the full whitepaper

## Paper Status

The whitepaper is a review draft, not a final publication artifact.

The current codebase and docs are meant to keep the implementation story aligned with the paper:

- pure core package in `src/octo`
- reference world models outside core
- benchmark implementations isolated from the framework itself
- clear distinction between structured control mode and native coprocessor mode
