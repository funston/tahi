# Whitepaper

The current paper draft is:

- [TAHI Whitepaper v2](whitepaper/TAHI_whitepaper_v2.md)

## What The Paper Covers

- why implicit LLM world models are weak interfaces
- why TAHI is not just RAG
- why runtime world models can be better than retraining for specialized domains
- how TAHI is intended to integrate natively into open-weight model runtimes

## What To Read First

If you are new to the repo:

1. [Quick Start](docs/QUICKSTART.md)
2. [Tutorial](docs/TUTORIAL.md)
3. [Architecture](docs/ARCHITECTURE.md)
4. [Integration Levels](docs/INTEGRATION_LEVELS.md)
5. then the full whitepaper

## Paper Status

The whitepaper is a review draft, not a final publication artifact.

The current codebase and docs are meant to keep the implementation story aligned with the paper:

- pure core package in `src/tahi`
- reference world models outside core
- benchmark implementations isolated from the framework itself
- clear distinction between structured control mode and native coprocessor mode
