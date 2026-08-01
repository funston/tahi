"""
DEA controlled-substance evaluation harness.

Builds a realistic world model around the Controlled Substance Analogue
Enforcement Act and real DEA scheduling actions, then evaluates OCTO against a
RAG baseline on analogue-classification and schedule-determination questions.
"""

from __future__ import annotations

from typing import Any

from .drug_coprocessor import DrugEnforcementCoprocessor, DrugEnforcementQuestion


# Real DEA scheduling information (public domain, from Federal Register notices).
DEA_SCHEDULES = {
    "Schedule I": (
        "Substances in Schedule I have a high potential for abuse, have no currently accepted "
        "medical use in treatment in the United States, and lack accepted safety for use under "
        "medical supervision."
    ),
    "Schedule II": (
        "Substances in Schedule II have a high potential for abuse, have a currently accepted "
        "medical use in treatment in the United States or a currently accepted medical use with "
        "severe restrictions, and abuse may lead to severe psychological or physical dependence."
    ),
}


DEA_SUBSTANCES = [
    {
        "name": "Fentanyl",
        "common_names": ["Duragesic", "Sublimaze"],
        "schedule": "Schedule II",
        "structural_class": "fentanyl analogues",
        "chemical_features": ["piperidine", "anilide", "N-phenylpropanamide"],
        "pharmacology": "Potent synthetic opioid analgesic",
        "description": "Fentanyl is a potent synthetic opioid analgesic approved for severe pain.",
    },
    {
        "name": "Acetylfentanyl",
        "common_names": ["Desmethylfentanyl"],
        "schedule": "Schedule I",
        "structural_class": "fentanyl analogues",
        "chemical_features": ["N-phenyl-N-[1-(2-phenylethyl)-4-piperidinyl]acetamide"],
        "pharmacology": "Synthetic opioid analogous to fentanyl",
        "description": "Acetylfentanyl is a fentanyl analogue with no accepted medical use.",
    },
    {
        "name": "Furanylfentanyl",
        "common_names": ["Fu-F"],
        "schedule": "Schedule I",
        "structural_class": "fentanyl analogues",
        "chemical_features": ["furan ring", "N-phenyl-N-[1-(2-phenylethyl)-4-piperidinyl]"],
        "pharmacology": "Synthetic opioid analogous to fentanyl",
        "description": "Furanylfentanyl is a fentanyl analogue associated with overdose deaths.",
    },
    {
        "name": "JWH-018",
        "common_names": ["Spice", "K2"],
        "schedule": "Schedule I",
        "structural_class": "synthetic cannabinoids",
        "chemical_features": ["indole core", "naphthoylindole"],
        "pharmacology": "CB1 receptor agonist",
        "description": "JWH-018 is a synthetic cannabinoid found in herbal smoking mixtures.",
    },
    {
        "name": "AM-2201",
        "common_names": ["Spice"],
        "schedule": "Schedule I",
        "structural_class": "synthetic cannabinoids",
        "chemical_features": ["indole core", "fluoropentyl"],
        "pharmacology": "CB1 receptor agonist analogous to JWH-018",
        "description": "AM-2201 is a synthetic cannabinoid structurally related to JWH-018.",
    },
    {
        "name": "MDPV",
        "common_names": ["Bath salts", "Cloud 9"],
        "schedule": "Schedule I",
        "structural_class": "synthetic cathinones",
        "chemical_features": ["pyrrolidinophenone", "methylenedioxypyrovalerone"],
        "pharmacology": "Stimulant analogous to cathinone",
        "description": "MDPV is a synthetic cathinone with no accepted medical use.",
    },
    {
        "name": "Alpha-PVP",
        "common_names": ["Flakka", "gravel"],
        "schedule": "Schedule I",
        "structural_class": "synthetic cathinones",
        "chemical_features": ["pyrrolidinopentiophenone"],
        "pharmacology": "Stimulant analogous to MDPV and cathinone",
        "description": "Alpha-PVP is a synthetic cathinone structurally similar to MDPV.",
    },
    {
        "name": "Heroin",
        "common_names": ["Diacetylmorphine"],
        "schedule": "Schedule I",
        "structural_class": "morphinans",
        "chemical_features": ["morphine diacetate"],
        "pharmacology": "Opioid analgesic",
        "description": "Heroin is a Schedule I opiate with no accepted medical use.",
    },
]


DEA_ACTIONS = [
    {
        "action_id": "FR-2015-14449",
        "title": "Placement of Acetylfentanyl into Schedule I",
        "date": "2015-05-15",
        "substance": "Acetylfentanyl",
        "action": "Schedule I permanent placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA permanently placed acetylfentanyl, including its isomers, salts, and salts of isomers, "
            "into Schedule I of the Controlled Substances Act."
        ),
    },
    {
        "action_id": "FR-2017-21991",
        "title": "Placement of Furanylfentanyl into Schedule I",
        "date": "2017-11-10",
        "substance": "Furanylfentanyl",
        "action": "Schedule I temporary then permanent placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA temporarily placed furanylfentanyl into Schedule I and subsequently made the placement "
            "permanent due to abuse potential and lack of accepted medical use."
        ),
    },
    {
        "action_id": "FR-2011-5398",
        "title": "Schedules of Controlled Substances: Temporary Placement of Five Synthetic Cannabinoids",
        "date": "2011-03-01",
        "substance": "JWH-018",
        "action": "Schedule I temporary placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA temporarily placed JWH-018 and related cannabinoids into Schedule I based on high abuse "
            "potential and no accepted medical use."
        ),
    },
    {
        "action_id": "FR-2012-1097",
        "title": "Schedules of Controlled Substances: Placement of AM-2201 into Schedule I",
        "date": "2012-07-09",
        "substance": "AM-2201",
        "action": "Schedule I placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA placed AM-2201 into Schedule I as a synthetic cannabinoid with structural and pharmacological "
            "similarity to JWH-018."
        ),
    },
    {
        "action_id": "FR-2011-4214",
        "title": "Schedules of Controlled Substances: Temporary Placement of Three Synthetic Cathinones",
        "date": "2011-10-21",
        "substance": "MDPV",
        "action": "Schedule I temporary placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA temporarily placed MDPV and related synthetic cathinones into Schedule I due to abuse potential."
        ),
    },
    {
        "action_id": "FR-2014-20549",
        "title": "Placement of Alpha-PVP into Schedule I",
        "date": "2014-01-28",
        "substance": "Alpha-PVP",
        "action": "Schedule I permanent placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA permanently placed alpha-PVP into Schedule I as a synthetic cathinone structurally and "
            "pharmacologically similar to MDPV."
        ),
    },
]


DEA_ANALOGUE_RELATIONSHIPS = [
    ("Acetylfentanyl", "Fentanyl"),
    ("Furanylfentanyl", "Fentanyl"),
    ("AM-2201", "JWH-018"),
    ("Alpha-PVP", "MDPV"),
]


DEA_EVAL_QUESTIONS = [
    DrugEnforcementQuestion(
        id="dea-analogue-1",
        text="Is acetylfentanyl a controlled substance analogue of fentanyl?",
        answer="Yes",
    ),
    DrugEnforcementQuestion(
        id="dea-analogue-2",
        text="Is AM-2201 a controlled substance analogue of JWH-018?",
        answer="Yes",
    ),
    DrugEnforcementQuestion(
        id="dea-analogue-3",
        text="Is alpha-PVP a controlled substance analogue of MDPV?",
        answer="Yes",
    ),
    DrugEnforcementQuestion(
        id="dea-schedule-1",
        text="What schedule is furanylfentanyl?",
        answer="Schedule I",
    ),
    DrugEnforcementQuestion(
        id="dea-schedule-2",
        text="What schedule is heroin?",
        answer="Schedule I",
    ),
    DrugEnforcementQuestion(
        id="dea-schedule-3",
        text="What schedule is fentanyl?",
        answer="Schedule II",
    ),
    DrugEnforcementQuestion(
        id="dea-action-1",
        text="What DEA scheduling action was taken on acetylfentanyl?",
        answer="Schedule I permanent placement",
    ),
    DrugEnforcementQuestion(
        id="dea-class-1",
        text="Which structural class does MDPV belong to?",
        answer="synthetic cathinones",
    ),
]


def build_default_coprocessor(llm_client=None) -> DrugEnforcementCoprocessor:
    """Build a drug-enforcement coprocessor pre-loaded with DEA public data."""
    coprocessor = DrugEnforcementCoprocessor(llm_client=llm_client)

    for name, description in DEA_SCHEDULES.items():
        coprocessor.add_schedule(name, description)

    for sub in DEA_SUBSTANCES:
        coprocessor.add_substance(
            name=sub["name"],
            common_names=sub["common_names"],
            schedule=sub["schedule"],
            structural_class=sub["structural_class"],
            chemical_features=sub["chemical_features"],
            pharmacology=sub["pharmacology"],
            description=sub["description"],
        )

    for analogue, prototype in DEA_ANALOGUE_RELATIONSHIPS:
        coprocessor.add_analogue_relationship(analogue, prototype)

    for action in DEA_ACTIONS:
        coprocessor.add_scheduling_action(
            action_id=action["action_id"],
            title=action["title"],
            date=action["date"],
            substance=action["substance"],
            action=action["action"],
            legal_basis=action["legal_basis"],
            summary=action["summary"],
        )

    coprocessor.build_index()
    return coprocessor


def load_dea_eval_questions() -> list[DrugEnforcementQuestion]:
    return list(DEA_EVAL_QUESTIONS)


def evaluate_drug_coprocessor(llm_client=None) -> dict[str, Any]:
    """Compare OCTO vs RAG baseline on the DEA eval questions."""
    questions = load_dea_eval_questions()
    coprocessor = build_default_coprocessor(llm_client=llm_client)

    rag_result = coprocessor.evaluate(questions, use_graph=False)
    octo_result = coprocessor.evaluate(questions, use_graph=True)

    return {
        "rag": rag_result,
        "octo": octo_result,
        "delta": octo_result["accuracy"] - rag_result["accuracy"],
    }
