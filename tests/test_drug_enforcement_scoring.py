"""
Targeted unit tests for DEA coprocessor scoring and retrieval-recall logic.

These tests catch the specific bugs that appeared during evaluation:
  - "no" substring false positives inside words like "cannabinoid"
  - adverb-form scoring typos (temporarytly)
  - fragile query splitting for scheduling-action questions
  - whole-word matching for schedule/class answers
"""

from __future__ import annotations

import pytest

from implementations.drug_enforcement.drug_coprocessor import (
    DrugEnforcementCoprocessor,
    DrugEnforcementQuestion,
)


@pytest.fixture
def scorer() -> DrugEnforcementCoprocessor:
    return DrugEnforcementCoprocessor()


# ---------------------------------------------------------------------------
# _score: yes/no
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "predicted, expected, should_pass",
    [
        ("Yes, it is an analogue.", "yes", True),
        ("No, it is not.", "no", True),
        # "no" inside "cannabinoid" must not trigger false negative for Yes.
        ("Yes, AM-2201 is a synthetic cannabinoid.", "yes", True),
        ("Yes, it has no currently accepted medical use.", "yes", True),
        # Wrong polarity.
        ("No, it is a cannabinoid.", "yes", False),
        ("Yes, it is not an analogue.", "no", False),
        # Ambiguous / no clear yes/no.
        ("It is similar.", "yes", False),
    ],
)
def test_score_yes_no(predicted, expected, should_pass, scorer):
    q = DrugEnforcementQuestion(id="t", text="Is X an analogue of Y?", answer=expected, task="analogue_classification")
    assert scorer._score(predicted, expected, q) is should_pass


# ---------------------------------------------------------------------------
# _score: schedule determination
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "predicted, expected, should_pass",
    [
        ("Fentanyl is Schedule II.", "Schedule II", True),
        ("Heroin is Schedule I.", "Schedule I", True),
        # Schedule I must not match Schedule II.
        ("It is Schedule II.", "Schedule I", False),
        # Schedule II must not match Schedule I.
        ("It is Schedule I.", "Schedule II", False),
    ],
)
def test_score_schedule(predicted, expected, should_pass, scorer):
    q = DrugEnforcementQuestion(id="t", text="What schedule is X?", answer=expected, task="schedule_determination")
    assert scorer._score(predicted, expected, q) is should_pass


# ---------------------------------------------------------------------------
# _score: scheduling action
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "predicted, expected, should_pass",
    [
        ("Schedule I permanent placement.", "Schedule I permanent placement", True),
        ("Schedule I permanently placed.", "Schedule I permanent placement", True),
        ("Schedule II temporary placement.", "Schedule II temporary placement", True),
        ("Schedule II temporarily placed.", "Schedule II temporary placement", True),
        # Missing placement type.
        ("Schedule I.", "Schedule I permanent placement", False),
        # Wrong schedule.
        ("Schedule II permanent placement.", "Schedule I permanent placement", False),
    ],
)
def test_score_scheduling_action(predicted, expected, should_pass, scorer):
    q = DrugEnforcementQuestion(id="t", text="What action was taken on X?", answer=expected, task="scheduling_action")
    assert scorer._score(predicted, expected, q) is should_pass


# ---------------------------------------------------------------------------
# _score: structural class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "predicted, expected, should_pass",
    [
        ("MDPV belongs to synthetic cathinones.", "synthetic cathinones", True),
        ("It is a synthetic cannabinoid.", "synthetic cannabinoids", True),
        # Substring should not count.
        ("It is a cathinone derivative.", "synthetic cathinones", False),
    ],
)
def test_score_class(predicted, expected, should_pass, scorer):
    q = DrugEnforcementQuestion(id="t", text="What class?", answer=expected, task="structural_class")
    assert scorer._score(predicted, expected, q) is should_pass


# ---------------------------------------------------------------------------
# _retrieval_recall
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question, evidence, expected",
    [
        # Yes/no analogue: both substances + similarity signal.
        (
            DrugEnforcementQuestion(id="t", text="Is acetylfentanyl a controlled substance analogue of fentanyl?", answer="Yes", task="analogue_classification"),
            "Acetylfentanyl is a fentanyl analogue with no accepted medical use.",
            True,
        ),
        # Missing similarity signal.
        (
            DrugEnforcementQuestion(id="t", text="Is acetylfentanyl a controlled substance analogue of fentanyl?", answer="Yes", task="analogue_classification"),
            "Acetylfentanyl and fentanyl are both opioids.",
            False,
        ),
        # Schedule: exact whole phrase.
        (
            DrugEnforcementQuestion(id="t", text="What schedule is fentanyl?", answer="Schedule II", task="schedule_determination"),
            "Substances in Schedule II have accepted medical use. Fentanyl is Schedule II.",
            True,
        ),
        # Schedule I evidence must not count for Schedule II.
        (
            DrugEnforcementQuestion(id="t", text="What schedule is fentanyl?", answer="Schedule II", task="schedule_determination"),
            "Substances in Schedule I have no accepted medical use.",
            False,
        ),
        # Action: substance + schedule + permanence.
        (
            DrugEnforcementQuestion(id="t", text="What DEA scheduling action was taken on acetylfentanyl?", answer="Schedule I permanent placement", task="scheduling_action"),
            "DEA permanently placed acetylfentanyl into Schedule I.",
            True,
        ),
        # Missing permanence.
        (
            DrugEnforcementQuestion(id="t", text="What DEA scheduling action was taken on acetylfentanyl?", answer="Schedule I permanent placement", task="scheduling_action"),
            "Acetylfentanyl is Schedule I.",
            False,
        ),
        # Class: exact class name.
        (
            DrugEnforcementQuestion(id="t", text="What class is MDPV?", answer="synthetic cathinones", task="structural_class"),
            "MDPV is a synthetic cathinone.",
            True,
        ),
    ],
)
def test_retrieval_recall(question, evidence, expected, scorer):
    assert scorer._retrieval_recall(question, evidence) is expected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_adverb_form_no_typos(scorer):
    assert scorer._adverb_form("permanent") == "permanently"
    assert scorer._adverb_form("temporary") == "temporarily"
    assert scorer._adverb_form("temporarily") == "temporarily"


def test_extract_substance_from_action_question(scorer):
    assert scorer._extract_substance_from_action_question("What DEA scheduling action was taken on acetylfentanyl?") == "acetylfentanyl"
    assert scorer._extract_substance_from_action_question("What action on furanylfentanyl?") == "furanylfentanyl"
    assert scorer._extract_substance_from_action_question("What is it?") is None


def test_has_whole_word(scorer):
    assert scorer._has_whole_word("schedule i", "it is schedule i now") is True
    assert scorer._has_whole_word("schedule i", "it is schedule ii now") is False
    assert scorer._has_whole_word("fentanyl", "furanylfentanyl is a drug") is False
