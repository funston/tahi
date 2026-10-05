"""Tests for the TAHI MuSiQue evaluation."""

from implementations.musique import evaluate_musique, load_musique_sample
from implementations.musique.musique_eval import MusiqueCoprocessor


def test_load_musique_sample():
    samples = load_musique_sample()
    assert len(samples) >= 2
    question, paragraphs = samples[0]
    assert question.text
    assert question.answer
    assert len(paragraphs) >= 2


def test_coprocessor_builds_model():
    samples = load_musique_sample()
    question, paragraphs = samples[0]
    coprocessor = MusiqueCoprocessor(question, paragraphs)
    nodes = coprocessor.world_model.nodes
    assert len([n for n, v in nodes.items() if v.get("type") == "paragraph"]) >= 2


def test_retrieval_returns_evidence():
    samples = load_musique_sample()
    question, paragraphs = samples[0]
    coprocessor = MusiqueCoprocessor(question, paragraphs)
    evidence = coprocessor.retrieve()
    assert len(evidence) > 0


def test_evaluate_musique_runs():
    report = evaluate_musique(max_samples=2)
    assert "rag" in report
    assert "tahi" in report
    assert "delta" in report
    assert report["rag"]["total"] == 2
