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
from octo.llm_client import LLMClient, LLMResponse


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
    results = coprocessor.retrieve(q)
    texts = " ".join(r["text"].lower() for r in results)
    assert "fentanyl" in texts


def test_graph_expansion_adds_action_or_schedule(coprocessor, questions):
    """Graph expansion should bring in scheduling actions or schedule nodes."""
    q = next(q for q in questions if q.id == "dea-schedule-1")
    results = coprocessor.retrieve(q)
    types = {r["type"] for r in results}
    assert "scheduling_action" in types or "schedule" in types


def test_evaluation_runs_and_reports_metrics(coprocessor, questions):
    """Evaluation should produce a valid metric dictionary."""
    result = coprocessor.evaluate(questions[:4])
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


def test_evaluation_with_mock_llm():
    """Evaluation should work with a deterministic mock LLM and produce real scores."""

    class MockLLMClient(LLMClient):
        def complete(self, prompt: str, system: str | None = None) -> LLMResponse:
            # Simple heuristic: if the prompt contains the expected schedule/action,
            # echo it back; otherwise say "I don't know".
            lowered = prompt.lower()
            if "what schedule is fentanyl" in lowered or "prototype substance that acetylfentanyl" in lowered:
                return LLMResponse(text="Schedule II", model="mock")
            if (
                "what schedule is heroin" in lowered
                or "what schedule is acetylfentanyl" in lowered
                or "what schedule is furanylfentanyl" in lowered
            ):
                return LLMResponse(text="Schedule I", model="mock")
            if "structural class does mdpv" in lowered:
                return LLMResponse(text="synthetic cathinones", model="mock")
            if "structural class does am" in lowered:
                return LLMResponse(text="synthetic cannabinoids", model="mock")
            if "shared prototype for both acetylfentanyl and furanylfentanyl" in lowered:
                return LLMResponse(text="Fentanyl", model="mock")
            if "synthetic cannabinoid related to jwh-018" in lowered:
                return LLMResponse(text="AM-2201", model="mock")
            if "temporarily placed alongside ur-144" in lowered:
                return LLMResponse(text="XLR-11", model="mock")
            if "2014 scheduling action" in lowered:
                return LLMResponse(text="Schedule I permanent placement", model="mock")
            if "permanently placed into schedule i in 2013" in lowered:
                return LLMResponse(text="Methylone", model="mock")
            if "permanently placed into schedule i in 2015" in lowered:
                return LLMResponse(text="Acetylfentanyl", model="mock")
            if "temporary then permanent placement in 2017" in lowered:
                return LLMResponse(text="Furanylfentanyl", model="mock")
            return LLMResponse(text="I don't know", model="mock")

    coprocessor = build_default_coprocessor(llm_client=MockLLMClient())
    questions = load_dea_eval_questions()
    result = coprocessor.evaluate(questions)
    assert result["total"] == len(questions)
    assert result["accuracy"] >= 0.0
    # With this mock, we should get several right.
    assert result["correct"] >= 3
