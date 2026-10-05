"""Tests for the TAHI FRAMES evaluation."""

from implementations.frames import evaluate_frames, load_frames_sample
from implementations.frames.frames_eval import FramesCoprocessor


def test_load_frames_sample():
    samples = load_frames_sample()
    assert len(samples) >= 2
    question, paragraphs = samples[0]
    assert question.text
    assert question.answer
    assert len(paragraphs) >= 2


def test_coprocessor_builds_model():
    samples = load_frames_sample()
    question, paragraphs = samples[0]
    coprocessor = FramesCoprocessor(question, paragraphs)
    nodes = coprocessor.world_model.nodes
    assert len([n for n, v in nodes.items() if v.get("type") == "paragraph"]) >= 2


def test_retrieval_returns_evidence():
    samples = load_frames_sample()
    question, paragraphs = samples[0]
    coprocessor = FramesCoprocessor(question, paragraphs)
    evidence = coprocessor.retrieve()
    assert len(evidence) > 0
    assert all("text" in item and "origin" in item for item in evidence)


def test_evaluate_frames_runs():
    report = evaluate_frames(max_samples=2)
    assert "rag" in report
    assert "tahi" in report
    assert "delta" in report
    assert report["rag"]["total"] == 2
