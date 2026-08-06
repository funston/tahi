# Benchmarks

This directory stores reproducible benchmark inputs, machine-readable results, and human-readable benchmark reports.

Layout:

- `benchmarks/sql_grounding_report.html`
 - secondary aggregate SQL benchmark page
- `benchmarks/sql_grounding_report.svg`
 - optional single-image SQL benchmark report
- `benchmarks/gretel/`
 - Gretel synthetic text-to-SQL grounding benchmark inputs and JSON results
- `benchmarks/mass_spec/`
 - mass spectrometry benchmark inputs and results

Naming convention:

- `*_input.json`
 - benchmark input sample or frozen dataset slice
- `*_report.json`
 - machine-readable benchmark output for reproducibility and scripting
 - primary benchmark report to open first
- `sql_grounding_report.html`
 - secondary aggregate report
- `sql_grounding_report.svg`
 - single combined SVG for the current SQL benchmark charts and legend

The goal is to keep benchmark artifacts readable and easy to publish, instead of scattering temporary `.tmp_*` files in the repo root.
