"""
Tests for the OCTO drug-enforcement world coprocessor.

These tests verify that the coprocessor builds a DEA world model, retrieves
substances/schedules/actions, and runs the full DEA evaluation. They do not
require an LLM API key.
"""

from __future__ import annotations

import pytest

from implementations.drug_enforcement import (
    DrugEnforcementQuestion,
    build_default_coprocessor,
    evaluate_drug_coprocessor,
    load_dea_eval_questions,
)


@pytest.fixture
def coprocessor():
    return build_default_coprocessor()


@pytest.fixture
def questions() -> list[DrugEnforcementQuestion]:
    return load_dea_eval_questions()


def test_dea_model_contains_substances_schedules_and_actions(coprocessor):
    """The default DEA world model should contain substances, schedules, and actions."""
    nodes = coprocessor.world_model.nodes
    substances = [n for n, v in nodes.items() if v.get("type") == "substance"]
    schedules = [n for n, v in nodes.items() if v.get("type") == "schedule"]
    actions = [n for n, v in nodes.items() if v.get("type") == "scheduling_action"]
    assert len(substances) >= 6
    assert len(schedules) == 2
    assert len(actions) >= 4


def test_analogue_edges_exist(coprocessor):
    """The world model should contain explicit analogue relationships."""
    edges = coprocessor.world_model.edges
    analogue_edges = [e for e in edges if e[1] == "analogue_of"]
    assert len(analogue_edges) >= 3
    targets = {e[2] for e in analogue_edges}
    assert "substance::Fentanyl" in targets or "substance::JWH-018" in targets


def test_retrieval_finds_fentanyl_analogue(coprocessor, questions):
    """Retrieval should return fentanyl-related substances for an analogue question."""
    q = next(q for q in questions if q.id == "dea-analogue-1")
    results = coprocessor.retrieve_octo(q)
    texts = " ".join(r["text"].lower() for r in results)
    assert "fentanyl" in texts


def test_graph_expansion_adds_action_or_schedule(coprocessor, questions):
    """Graph expansion should bring in scheduling actions or schedule nodes."""
    q = next(q for q in questions if q.id == "dea-schedule-1")
    results = coprocessor.retrieve_octo(q)
    types = {r["type"] for r in results}
    assert "scheduling_action" in types or "schedule" in types


def test_evaluation_runs_and_reports_metrics(coprocessor, questions):
    """Evaluation should produce a valid metric dictionary."""
    result = coprocessor.evaluate(questions[:4], use_graph=True)
    assert "accuracy" in result
    assert result["total"] == 4
    assert 0.0 <= result["accuracy"] <= 1.0


def test_full_dea_evaluation():
    """End-to-end DEA comparison should return both RAG and OCTO results."""
    report = evaluate_drug_coprocessor()
    assert "rag" in report
    assert "octo" in report
    assert "delta" in report
    for key in ("rag", "octo"):
        assert "accuracy" in report[key]
        assert report[key]["total"] == len(load_dea_eval_questions())
