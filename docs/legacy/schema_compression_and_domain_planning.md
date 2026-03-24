# Schema Compression And Domain Planning

## Purpose

Large enterprise and benchmark databases often do not fail because they have too little schema.
They fail because they have too much flat schema presented without structure.

BENDER's reusable approach is:

1. compress related tables into schema families,
2. plan first at the family level,
3. resolve family candidates into concrete tables using domain hints,
4. pass the narrowed plan into generation, validation, and repair.

This keeps the generic framework reusable while still allowing strong domain-specific planning for hard databases.

## Generic Framework

### Schema Compression

The generic compression layer groups near-duplicate tables into `SchemaFamily` clusters based on:

- normalized table-name tokens,
- normalized release/build/source suffixes,
- overlapping column signatures.

This is implemented in:

- `src/bender/schema_compression.py`

The output is a `SchemaCompressionPlan` with:

- `families`
- `table_to_family`

### World-Model Integration

The compression plan is projected into the world model so retrieval can see:

- concrete table nodes,
- schema-family nodes,
- family membership edges,
- family-level keywords and common columns.

This is implemented in:

- `src/bender/database.py`

That means downstream retrieval is no longer forced to choose from a flat list of hundreds of raw tables.

### Why This Matters

Schema families help in three places:

- retrieval: family summaries are shorter and more semantically legible than individual versioned tables,
- planning: candidate selection can happen at the family level first,
- context compaction: dozens of near-duplicate tables can be represented by one family plus a small disambiguation policy.

## Domain Planning

The generic compression layer is not enough by itself for benchmark-hard domains.
Some domains need a second step that maps query semantics to the right family and then to the right concrete table.

The reusable pattern is:

1. parse domain hints from the question,
2. score generic schema families,
3. apply domain-specific boosts or penalties,
4. resolve to concrete tables,
5. emit join-path hints where the domain has known bridge patterns.

## TCGA_MITELMAN Application

`TCGA_MITELMAN` is a strong example because it contains many versioned and modality-specific tables:

- `CLINICAL_GDC_R*`
- `PER_SAMPLE_FILE_METADATA_*`
- `COPY_NUMBER_SEGMENT_*`
- `DNA_METHYLATION_CHR*_*`
- Mitelman `PROD.*` cytogenetics tables

The specific planner for this database is implemented in:

- `src/bender/spider_tcga.py`

It extracts hints such as:

- `TCGA-KIRC`, `TCGA-LAML`, `TCGA-BRCA`
- release tokens like `R23`
- chromosome and cytoband mentions
- modality phrases like:
  - `copy number segment allelic`
  - `cytobands`
  - `Mitelman`
  - `Pearson correlation`

Then it resolves those hints into:

- schema families
- candidate tables
- candidate join paths

Examples:

- copy-number + cytoband tasks prefer:
  - `TCGA_VERSIONED.COPY_NUMBER_SEGMENT_ALLELIC_HG38_GDC_R23`
  - `PROD.CYTOBANDS_HG38`
- Mitelman correlation tasks additionally prefer:
  - `PROD.CYTOGENINVVALID`
  - `PROD.REFERENCE`
  - `PROD.CYTOGEN`
  - `PROD.KODER`
  - `PROD.CYTOCONVERTED`

## Current Outcome

This design improved the planning side of `TCGA_MITELMAN` without hard-coding full SQL answers:

- family-aware planning now recovers the correct tables for several previously failing tasks,
- join-path hints are now emitted for copy-number/cytoband and Mitelman-correlation patterns,
- the same abstraction can be reused for other large schema families outside genomics.

## What It Does Not Solve Yet

Schema compression and domain planning fix the front half of the problem.
They do not by themselves solve:

- full SQL generation,
- result-shape correctness,
- benchmark-specific aggregation semantics,
- execution-time repair for genomics queries.

Those remain downstream compiler-stage work.

## Product Implication

For enterprise onboarding, this same pattern generalizes cleanly:

- ingest raw warehouse schema,
- build schema families,
- let admins inspect family groupings,
- attach domain hints and policies,
- run with/without BENDER evaluations,
- then promote the compressed world into production inference.

That is more usable than exposing users to hundreds of raw tables and expecting prompting alone to solve the problem.
