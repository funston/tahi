"""Tests for the TAHI HotpotQA evaluation."""

from implementations.hotpotqa import evaluate_hotpotqa, load_hotpotqa_sample
from implementations.hotpotqa.hotpotqa_eval import HotpotQACoprocessor


def test_load_hotpotqa_sample():
    samples = load_hotpotqa_sample()
    assert len(samples) >= 2
    question, facts = samples[0]
    assert question.text
    assert question.answer
    assert len(facts) >= 2


def test_coprocessor_builds_model():
    samples = load_hotpotqa_sample(max_samples=1)
    question, facts = samples[0]
    coprocessor = HotpotQACoprocessor(question, facts)
    nodes = coprocessor.world_model.nodes
    facts_count = len([n for n, v in nodes.items() if v.get("type") == "fact"])
    articles_count = len([n for n, v in nodes.items() if v.get("type") == "article"])
    assert facts_count >= 2
    assert articles_count >= 1


def test_retrieval_returns_evidence():
    samples = load_hotpotqa_sample(max_samples=1)
    question, facts = samples[0]
    coprocessor = HotpotQACoprocessor(question, facts)
    evidence = coprocessor.retrieve()
    assert len(evidence) > 0
    # Evidence should cover the fact nodes from the supporting facts.
    node_ids = {e["node_id"] for e in evidence}
    assert any(n.startswith("fact::") for n in node_ids)


def test_evaluate_hotpotqa_runs():
    report = evaluate_hotpotqa(max_samples=2)
    assert "rag" in report
    assert "tahi" in report
    assert "delta" in report
    assert report["rag"]["total"] == 2
    assert report["tahi"]["total"] == 2
