"""
DEA controlled-substance evaluation harness.

Builds a realistic world model around the Controlled Substance Analogue
Enforcement Act and real DEA scheduling actions, then evaluates OCTO against a
RAG baseline on analogue-classification and schedule-determination questions.
"""

from __future__ import annotations

from typing import Any

from octo.baseline_rag import RAGDocument, StandaloneRAG

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
        "name": "Carfentanil",
        "common_names": ["Wildnil"],
        "schedule": "Schedule II",
        "structural_class": "fentanyl analogues",
        "chemical_features": ["4-methoxycarbonylfentanyl", "potent opioid"],
        "pharmacology": "Ultra-potent synthetic opioid analogue of fentanyl",
        "description": "Carfentanil is a fentanyl analogue used as a large animal tranquilizer.",
    },
    {
        "name": "U-47700",
        "common_names": ["Pink", "U4"],
        "schedule": "Schedule I",
        "structural_class": "synthetic opioids",
        "chemical_features": ["trans-3,4-dichloro-N-[2-(dimethylamino)cyclohexyl]-N-methylbenzamide"],
        "pharmacology": "Synthetic opioid analgesic",
        "description": "U-47700 is a synthetic opioid with no accepted medical use.",
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
        "name": "UR-144",
        "common_names": ["TMCP-018"],
        "schedule": "Schedule I",
        "structural_class": "synthetic cannabinoids",
        "chemical_features": ["tetramethylcyclopropylindole"],
        "pharmacology": "CB1 receptor agonist analogous to JWH-018",
        "description": "UR-144 is a synthetic cannabinoid with structural similarity to JWH-018.",
    },
    {
        "name": "XLR-11",
        "common_names": ["XLR11"],
        "schedule": "Schedule I",
        "structural_class": "synthetic cannabinoids",
        "chemical_features": ["fluoropentylindole", "UR-144 analogue"],
        "pharmacology": "CB1 receptor agonist analogous to UR-144",
        "description": "XLR-11 is a synthetic cannabinoid structurally related to UR-144.",
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
        "name": "Methylone",
        "common_names": ["M1", "bk-MDMA"],
        "schedule": "Schedule I",
        "structural_class": "synthetic cathinones",
        "chemical_features": ["beta-keto-MDMA", "methylenedioxycathinone"],
        "pharmacology": "Stimulant and empathogen analogous to cathinone",
        "description": "Methylone is a synthetic cathinone with no accepted medical use.",
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
        "action_id": "FR-2018-14681",
        "title": "Placement of U-47700 into Schedule I",
        "date": "2018-04-04",
        "substance": "U-47700",
        "action": "Schedule I permanent placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA permanently placed U-47700 into Schedule I as a synthetic opioid with abuse potential and "
            "no accepted medical use."
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
        "action_id": "FR-2013-0942",
        "title": "Temporary Placement of UR-144 and XLR-11 into Schedule I",
        "date": "2013-04-12",
        "substance": "UR-144",
        "action": "Schedule I temporary placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA temporarily placed UR-144 and XLR-11 into Schedule I as synthetic cannabinoids with "
            "structural similarity to JWH-018."
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
    {
        "action_id": "FR-2013-0294",
        "title": "Placement of Methylone into Schedule I",
        "date": "2013-01-07",
        "substance": "Methylone",
        "action": "Schedule I permanent placement",
        "legal_basis": "21 U.S.C. 811(h); 21 CFR 1308.11",
        "summary": (
            "DEA permanently placed methylone into Schedule I as a synthetic cathinone with no accepted "
            "medical use."
        ),
    },
]


DEA_ANALOGUE_RELATIONSHIPS = [
    ("Acetylfentanyl", "Fentanyl"),
    ("Furanylfentanyl", "Fentanyl"),
    ("Carfentanil", "Fentanyl"),
    ("AM-2201", "JWH-018"),
    ("UR-144", "JWH-018"),
    ("XLR-11", "UR-144"),
    ("Alpha-PVP", "MDPV"),
]


# Distractor substances that are not controlled-substance analogues.
DEA_DISTRACTOR_SUBSTANCES = [
    {
        "name": "Morphine",
        "common_names": ["MS Contin", "Roxanol"],
        "schedule": "Schedule II",
        "structural_class": "morphinans",
        "chemical_features": ["phenanthrene", "tertiary amine"],
        "pharmacology": "Opioid analgesic",
        "description": "Morphine is a naturally occurring opioid analgesic used for pain relief.",
    },
    {
        "name": "Caffeine",
        "common_names": ["Coffee", "Tea"],
        "schedule": None,
        "structural_class": "xanthines",
        "chemical_features": ["xanthine", "methylxanthine"],
        "pharmacology": "Central nervous system stimulant",
        "description": "Caffeine is a widely consumed stimulant found in coffee and tea.",
    },
    {
        "name": "Ibuprofen",
        "common_names": ["Advil", "Motrin"],
        "schedule": None,
        "structural_class": "propionic acids",
        "chemical_features": ["phenylpropionic acid", "isobutylphenyl"],
        "pharmacology": "Nonsteroidal anti-inflammatory drug",
        "description": "Ibuprofen is an over-the-counter nonsteroidal anti-inflammatory drug.",
    },
    {
        "name": "Tramadol",
        "common_names": ["Ultram"],
        "schedule": "Schedule IV",
        "structural_class": "synthetic opioids",
        "chemical_features": ["cyclohexanol", "dimethylaminomethyl"],
        "pharmacology": "Synthetic opioid analgesic",
        "description": "Tramadol is a synthetic opioid analgesic with accepted medical use.",
    },
    {
        "name": "Ketamine",
        "common_names": ["Ketalar"],
        "schedule": "Schedule III",
        "structural_class": "arylcyclohexylamines",
        "chemical_features": ["cyclohexanone", "2-chlorophenyl"],
        "pharmacology": "Dissociative anesthetic",
        "description": "Ketamine is a dissociative anesthetic with accepted medical use.",
    },
    {
        "name": "Methamphetamine",
        "common_names": ["Desoxyn"],
        "schedule": "Schedule II",
        "structural_class": "phenethylamines",
        "chemical_features": ["phenethylamine", "methylamphetamine"],
        "pharmacology": "Central nervous system stimulant",
        "description": "Methamphetamine is a Schedule II stimulant with severe restrictions on medical use.",
    },
    {
        "name": "Psilocybin",
        "common_names": ["Magic mushrooms"],
        "schedule": "Schedule I",
        "structural_class": "tryptamines",
        "chemical_features": ["indole", "phosphoryloxy"],
        "pharmacology": "Psychedelic tryptamine",
        "description": "Psilocybin is a Schedule I psychedelic compound with no accepted medical use.",
    },
    {
        "name": "Cocaine",
        "common_names": ["Coca"],
        "schedule": "Schedule II",
        "structural_class": "tropane alkaloids",
        "chemical_features": ["tropane", "benzoylmethylecgonine"],
        "pharmacology": "Local anesthetic and stimulant",
        "description": "Cocaine is a Schedule II tropane alkaloid with accepted medical use as a local anesthetic.",
    },
]


DEA_EVAL_QUESTIONS = [
    # Direct single-fact questions.
    DrugEnforcementQuestion(
        id="dea-analogue-1",
        text="Is acetylfentanyl a controlled substance analogue of fentanyl?",
        answer="Yes",
        task="analogue_classification",
    ),
    DrugEnforcementQuestion(
        id="dea-analogue-2",
        text="Is AM-2201 a controlled substance analogue of JWH-018?",
        answer="Yes",
        task="analogue_classification",
    ),
    DrugEnforcementQuestion(
        id="dea-analogue-3",
        text="Is alpha-PVP a controlled substance analogue of MDPV?",
        answer="Yes",
        task="analogue_classification",
    ),
    DrugEnforcementQuestion(
        id="dea-schedule-1",
        text="What schedule is furanylfentanyl?",
        answer="Schedule I",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-schedule-2",
        text="What schedule is heroin?",
        answer="Schedule I",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-schedule-3",
        text="What schedule is fentanyl?",
        answer="Schedule II",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-action-1",
        text="What DEA scheduling action was taken on acetylfentanyl?",
        answer="Schedule I permanent placement",
        task="scheduling_action",
    ),
    DrugEnforcementQuestion(
        id="dea-class-1",
        text="Which structural class does MDPV belong to?",
        answer="synthetic cathinones",
        task="structural_class",
    ),
    # Negative analogue examples (distractors).
    DrugEnforcementQuestion(
        id="dea-analogue-neg-1",
        text="Is morphine a controlled substance analogue of fentanyl?",
        answer="No",
        task="analogue_classification",
    ),
    DrugEnforcementQuestion(
        id="dea-analogue-neg-2",
        text="Is JWH-018 a controlled substance analogue of MDPV?",
        answer="No",
        task="analogue_classification",
    ),
    DrugEnforcementQuestion(
        id="dea-analogue-neg-3",
        text="Is caffeine a controlled substance analogue of fentanyl?",
        answer="No",
        task="analogue_classification",
    ),
    # Multi-hop questions: answering requires traversing graph edges.
    # These are designed so that pure vector search may miss the target node,
    # while graph expansion follows explicit relationships.
    DrugEnforcementQuestion(
        id="dea-prototype-schedule-1",
        text="What schedule is the prototype substance that acetylfentanyl is an analogue of?",
        answer="Schedule II",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-prototype-name-1",
        text="Which Schedule II substance is the shared prototype for both acetylfentanyl and furanylfentanyl?",
        answer="Fentanyl",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-cannabinoid-hop-1",
        text="A synthetic cannabinoid related to JWH-018 was placed into Schedule I in 2012. What is its name?",
        answer="AM-2201",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-cannabinoid-hop-2",
        text="Which synthetic cannabinoid was temporarily placed alongside UR-144 in 2013?",
        answer="XLR-11",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-cathinone-hop-1",
        text="A synthetic cathinone temporarily placed in Schedule I in 2011 has a related stimulant that was permanently placed in 2014. What is the 2014 scheduling action?",
        answer="Schedule I permanent placement",
        task="scheduling_action",
    ),
    DrugEnforcementQuestion(
        id="dea-cathinone-hop-2",
        text="Which synthetic cathinone was permanently placed into Schedule I in 2013?",
        answer="Methylone",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-fentanyl-hop-1",
        text="Which fentanyl analogue was permanently placed into Schedule I in 2015?",
        answer="Acetylfentanyl",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-fentanyl-hop-2",
        text="Which fentanyl analogue received a temporary then permanent placement in Schedule I in 2017?",
        answer="Furanylfentanyl",
        task="schedule_determination",
    ),
    DrugEnforcementQuestion(
        id="dea-common-name-hop",
        text="What common name is shared by the synthetic cannabinoids JWH-018 and AM-2201?",
        answer="Spice",
        task="structural_class",
    ),
    DrugEnforcementQuestion(
        id="dea-opioid-distractor",
        text="Is U-47700 a controlled substance analogue of fentanyl?",
        answer="No",
        task="analogue_classification",
    ),
]


def build_default_coprocessor(llm_client=None) -> DrugEnforcementCoprocessor:
    """Build a drug-enforcement coprocessor pre-loaded with DEA public data."""
    coprocessor = DrugEnforcementCoprocessor(llm_client=llm_client)

    for name, description in DEA_SCHEDULES.items():
        coprocessor.add_schedule(name, description)

    for sub in DEA_SUBSTANCES + DEA_DISTRACTOR_SUBSTANCES:
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


def _coprocessor_documents(coprocessor: DrugEnforcementCoprocessor) -> list[RAGDocument]:
    """Extract raw text documents from the OCTO world model for the RAG baseline."""
    documents: list[RAGDocument] = []
    for node_id, node in coprocessor.world_model.nodes.items():
        text = node.get("text", "")
        if not text:
            continue
        documents.append(
            RAGDocument(
                doc_id=node_id,
                text=text,
                metadata={
                    "type": node.get("type", ""),
                    "label": node.get("label", ""),
                },
            )
        )
    return documents


def evaluate_drug_coprocessor(llm_client=None) -> dict[str, Any]:
    """Compare OCTO vs a standalone RAG baseline on the DEA eval questions."""
    questions = load_dea_eval_questions()
    coprocessor = build_default_coprocessor(llm_client=llm_client)

    # Standalone RAG baseline over the same raw documents, no graph access.
    rag = StandaloneRAG(top_k=5, llm_client=llm_client)
    rag.add_documents(_coprocessor_documents(coprocessor))
    rag.build_index()

    rag_results: list[dict[str, Any]] = []
    rag_correct = 0
    rag_retrieval_correct = 0
    for q in questions:
        answer_text, model_name, retrievals = rag.answer(
            q.text,
            system="You answer controlled-substance questions from provided DEA sources only.",
        )
        is_correct = coprocessor._score(answer_text, q.answer, q)
        rag_correct += int(is_correct)

        evidence_text = " ".join(r.text for r in retrievals).lower()
        rec_ok = coprocessor._retrieval_recall(q, evidence_text)
        rag_retrieval_correct += int(rec_ok)

        rag_results.append(
            {
                "id": q.id,
                "question": q.text,
                "predicted": answer_text,
                "expected": q.answer,
                "correct": is_correct,
                "retrieval_recall": rec_ok,
                "model": model_name,
            }
        )

    rag_result = {
        "method": "RAG-baseline",
        "correct": rag_correct,
        "total": len(questions),
        "accuracy": rag_correct / len(questions) if questions else 0.0,
        "retrieval_correct": rag_retrieval_correct,
        "retrieval_recall": rag_retrieval_correct / len(questions) if questions else 0.0,
        "results": rag_results,
    }

    octo_result = coprocessor.evaluate(questions)

    return {
        "rag": rag_result,
        "octo": octo_result,
        "delta": octo_result["accuracy"] - rag_result["accuracy"],
    }
