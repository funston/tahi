"""
Tests for the OCTO legal world coprocessor.

These tests verify that the coprocessor builds a structured legal world model,
retrieves grounded evidence, and runs a full LegalBench evaluation. They do not
require an LLM API key; when no key is present the LLM falls back to a marker
and the pipeline still produces valid metrics.
"""

from __future__ import annotations

import pytest

from implementations.legal import (
    LegalQuestion,
    LegalWorldCoprocessor,
    build_default_coprocessor,
    evaluate_legal_coprocessor,
    load_legalbench_sample,
)


@pytest.fixture
def sample_questions() -> list[LegalQuestion]:
    return load_legalbench_sample()


@pytest.fixture
def legal_coprocessor() -> LegalWorldCoprocessor:
    return build_default_coprocessor()


def test_legal_corpus_loaded(legal_coprocessor: LegalWorldCoprocessor):
    """The default coprocessor should contain statutes and chunks."""
    nodes = legal_coprocessor.world_model.nodes
    statutes = [n for n, v in nodes.items() if v.get("type") == "statute"]
    chunks = [n for n, v in nodes.items() if v.get("type") == "chunk"]
    assert len(statutes) >= 4
    assert len(chunks) >= 8


def test_vector_retrieval_returns_relevant_statute(
    legal_coprocessor: LegalWorldCoprocessor,
    sample_questions: list[LegalQuestion],
):
    """Baseline retrieval should return chunks from the relevant statute."""
    q = next(q for q in sample_questions if "citizen" in q.text.lower())
    results = legal_coprocessor.retrieve_baseline(q, top_k=3)
    assert len(results) > 0
    sources = {r["source"] for r in results}
    assert "8 U.S.C. § 1401" in sources


def test_graph_expansion_increases_evidence_coverage(
    legal_coprocessor: LegalWorldCoprocessor,
    sample_questions: list[LegalQuestion],
):
    """OCTO retrieval should return more evidence than the baseline."""
    q = sample_questions[0]
    baseline = legal_coprocessor.retrieve_baseline(q)
    octo = legal_coprocessor.retrieve_octo(q)
    assert len(octo) >= len(baseline)
    # At least one item should come from graph expansion.
    origins = {item["origin"] for item in octo}
    assert any(origin.startswith("graph:") for origin in origins)


def test_evaluation_runs_and_reports_metrics(
    legal_coprocessor: LegalWorldCoprocessor,
    sample_questions: list[LegalQuestion],
):
    """Evaluation should produce a valid metric dictionary."""
    result = legal_coprocessor.evaluate(sample_questions[:3], use_graph=True)
    assert "accuracy" in result
    assert "total" in result
    assert result["total"] == 3
    assert 0.0 <= result["accuracy"] <= 1.0
    assert len(result["results"]) == 3


def test_full_legalbench_evaluation():
    """End-to-end LegalBench comparison should return both RAG and OCTO results."""
    report = evaluate_legal_coprocessor()
    assert "rag" in report
    assert "octo" in report
    assert "delta" in report
    for key in ("rag", "octo"):
        assert "accuracy" in report[key]
        assert "total" in report[key]
        assert report[key]["total"] == len(load_legalbench_sample())
