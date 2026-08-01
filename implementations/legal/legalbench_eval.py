"""
LegalBench evaluation harness for the OCTO legal coprocessor.

Loads a sample of statutory-reasoning questions, optionally downloads a
HuggingFace LegalBench subset if available, and compares OCTO against a
plain RAG baseline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .legal_coprocessor import LegalQuestion, LegalWorldCoprocessor


LEGAL_CORPUS = [
    {
        "citation": "United States v. Wong Kim Ark, 169 U.S. 649 (1898)",
        "title": "Birthright citizenship for children of aliens",
        "kind": "case",
        "text": (
            "The Supreme Court held that a child born in the United States, regardless of the citizenship "
            "of his parents, becomes a citizen of the United States at birth by virtue of the Fourteenth "
            "Amendment and 8 U.S.C. § 1401(a). Wong Kim Ark was born in San Francisco to Chinese parents "
            "who were subjects of the Emperor of China. After a trip abroad, he was denied re-entry on the "
            "ground that he was not a citizen. The Court rejected the government's argument, holding that "
            "the Fourteenth Amendment affirmed the ancient and fundamental rule of citizenship by birth "
            "within the territory, subject to the jurisdiction thereof."
        ),
        "tags": ["immigration", "citizenship", "birthright"],
    },
    {
        "citation": "8 U.S.C. § 1401",
        "title": "Nationals and citizens of United States at birth",
        "text": (
            "The following shall be nationals and citizens of the United States at birth: "
            "(a) a person born in the United States, and subject to the jurisdiction thereof; "
            "(b) a person born in the United States to a member of an Indian, Eskimo, Aleutian, "
            "or other aboriginal tribe; (c) a person born outside of the United States and its "
            "outlying possessions of parents both of whom are citizens of the United States and "
            "one of whom has had a residence in the United States or one of its outlying possessions, "
            "prior to the birth of such person; (d) a person born outside of the United States and "
            "its outlying possessions of parents one of whom is a citizen of the United States who "
            "has been physically present in the United States or one of its outlying possessions "
            "for a continuous period of one year prior to the birth of such person, and the other "
            "of whom is a national, but not a citizen of the United States; (e) a person born in an "
            "outlying possession of the United States of parents one of whom is a citizen of the "
            "United States who has been physically present in the United States or one of its "
            "outlying possessions for a continuous period of one year at any time prior to the "
            "birth of such person; (f) a person of unknown parentage found in the United States "
            "while under the age of five years, until shown, prior to his attaining the age of "
            "twenty-one years, not to have been born in the United States; (g) a person born outside "
            "the geographical limits of the United States and its outlying possessions of parents "
            "one of whom is an alien, and the other a citizen of the United States who, prior to the "
            "birth of such person, was physically present in the United States or its outlying "
            "possessions for a period or periods totaling not less than five years, at least two "
            "of which were after attaining the age of fourteen years."
        ),
        "tags": ["immigration", "citizenship"],
    },
    {
        "citation": "11 U.S.C. § 362",
        "title": "Automatic stay",
        "text": (
            "A petition filed under section 301, 302, or 303 of this title, or an application filed "
            "under section 5(a)(3) of the Securities Investor Protection Act of 1970, operates as a "
            "stay, applicable to all entities, of (1) the commencement or continuation, including the "
            "issuance or employment of process, of a judicial, administrative, or other action or "
            "proceeding against the debtor that was or could have been commenced before the commencement "
            "of the case under this title; (2) the enforcement, against the debtor or against property "
            "of the estate, of a judgment obtained before the commencement of the case under this title; "
            "(3) any act to obtain possession of property of the estate or of property from the estate "
            "or to exercise control over property of the estate; (4) any act to create, perfect, or "
            "enforce any lien against property of the estate; (5) any act to create, perfect, or enforce "
            "against property of the debtor any lien to the extent that such lien secures a claim that "
            "arose before the commencement of the case under this title; (6) any act to collect, assess, "
            "or recover a claim against the debtor that arose before the commencement of the case under "
            "this title; (7) the setoff of any debt owing to the debtor that arose before the commencement "
            "of the case under this title against any claim against the debtor; and (8) the commencement "
            "or continuation of a proceeding before the United States Tax Court concerning the debtor."
        ),
        "tags": ["bankruptcy"],
    },
    {
        "citation": "11 U.S.C. § 727",
        "title": "Discharge",
        "text": (
            "The court shall grant the debtor a discharge, unless (1) the debtor is not an individual; "
            "(2) the debtor, with intent to hinder, delay, or defraud a creditor or an officer of the "
            "estate charged with custody of property under this title, has transferred, removed, "
            "destroyed, mutilated, or concealed, or has permitted to be transferred, removed, destroyed, "
            "mutilated, or concealed, (A) property of the debtor, within one year before the date of the "
            "filing of the petition; or (B) property of the estate, after the date of the filing of the "
            "petition; (3) the debtor has concealed, destroyed, mutilated, falsified, or failed to keep "
            "or preserve any recorded information, including books, documents, records, and papers, from "
            "which the debtor's financial condition or business transactions might be ascertained, unless "
            "such act or failure to act was justified under all of the circumstances of the case; (4) the "
            "debtor knowingly and fraudulently, in or in connection with the case (A) made a false oath or "
            "account; (B) presented or used a false claim; (C) gave, offered, received, or attempted to "
            "obtain money, property, or advantage, or a promise of money, property, or advantage, for "
            "acting or forbearing to act; or (D) withheld from an officer of the estate entitled to "
            "possession under this title, any recorded information, including books, documents, records, "
            "and papers, relating to the debtor's property or financial affairs."
        ),
        "tags": ["bankruptcy"],
    },
    {
        "citation": "Restatement (Second) of Contracts § 110",
        "title": "Statute of Frauds",
        "text": (
            "The following classes of contracts are subject to a statute, commonly called the Statute "
            "of Frauds: (a) a contract of an executor or administrator to answer for a duty of his "
            "decedent (the executor-administrator provision); (b) a contract to answer for the debt, "
            "default or miscarriage of another person (the suretyship provision); (c) a contract made "
            "upon consideration of marriage (the marriage provision); (d) a contract for the transfer "
            "of an interest in land (the land contract provision); (e) a contract that is not to be "
            "performed within one year from the making thereof (the one-year provision); (f) a contract "
            "for the sale of goods for a price of five hundred dollars or more (the sale of goods provision). "
            "Such a statute requires either that the contract or a memorandum or note thereof be in writing "
            "and subscribed by the party to be charged or by his authorized agent."
        ),
        "tags": ["contracts"],
    },
    {
        "citation": "U.C.C. § 2-207",
        "title": "Additional Terms in Acceptance or Confirmation",
        "text": (
            "(1) A definite and seasonable expression of acceptance or a written confirmation which is "
            "sent within a reasonable time operates as an acceptance even though it states terms additional "
            "to or different from those offered or agreed upon, unless acceptance is expressly made conditional "
            "on assent to the additional or different terms. (2) The additional terms are to be construed as "
            "proposals for addition to the contract. Between merchants such terms become part of the contract "
            "unless (a) the offer expressly limits acceptance to its terms; (b) they materially alter it; or "
            "(c) notification of objection to them has already been given or is given within a reasonable time "
            "after notice of them is received. (3) Conduct by both parties which recognizes the existence of a "
            "contract is sufficient to establish a contract for sale although the writings of the parties do "
            "not otherwise establish a contract. In such case the terms of the particular contract consist of "
            "those terms on which the writings of the parties agree, together with any supplementary terms "
            "incorporated under any other provisions of this Act."
        ),
        "tags": ["contracts"],
    },
    {
        "citation": "U.C.C. § 9-322",
        "title": "Priorities Among Conflicting Security Interests",
        "text": (
            "(a) Conflicting perfected security interests. Except as otherwise provided in this section, "
            "priority among conflicting security interests is determined according to priority in time of "
            "filing or perfection. Priority dates from the earlier of the time a filing covering the collateral "
            "is first made or the time the security interest is first perfected, if there is no period thereafter "
            "when there is neither filing nor perfection. (b) Conflicting unperfected security interests. "
            "Except as otherwise provided in subsection (c), conflicting unperfected security interests rank "
            "according to priority in time of attachment. (c) Conflicting security interests in investment "
            "property, deposit accounts, letter-of-credit rights, or electronic chattel paper. "
            "(d) Conflicting security interests in proceeds. (e) Conflicting security interests in fixtures. "
            "(f) A perfected security interest in collateral has priority over an unperfected security interest "
            "in the same collateral."
        ),
        "tags": ["secured_transactions"],
    },
    {
        "citation": "Restatement (Second) of Torts § 328D",
        "title": "Res Ipsa Loquitur",
        "text": (
            "(1) It may be inferred that harm sustained by the plaintiff is caused by negligence of the "
            "defendant when (a) the event is of a kind which ordinarily does not occur in the absence of "
            "negligence; (b) other responsible causes, including the conduct of the plaintiff and third persons, "
            "are sufficiently eliminated by the evidence; and (c) the indicated negligence is within the scope "
            "of the defendant's duty to the plaintiff. (2) It is the function of the court to determine whether "
            "the inference may reasonably be drawn by the jury, or whether it must be drawn. (3) It is the "
            "function of the jury to determine whether the inference is to be drawn in any case where different "
            "conclusions may reasonably be reached."
        ),
        "tags": ["torts"],
    },
]


def load_legalbench_sample(path: Path | str | None = None) -> list[LegalQuestion]:
    """Load a sample LegalBench statutory-reasoning dataset."""
    if path is None:
        path = Path(__file__).with_name("data") / "sample_legalbench.jsonl"
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"LegalBench sample not found: {path}")

    questions: list[LegalQuestion] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            questions.append(
                LegalQuestion(
                    id=record["id"],
                    text=record["text"],
                    answer=record["answer"],
                    task=record.get("task", "statutory_reasoning"),
                    options=record.get("options"),
                )
            )
    return questions


def build_default_coprocessor(llm_client=None) -> LegalWorldCoprocessor:
    """Build a legal coprocessor pre-loaded with the canonical corpus."""
    coprocessor = LegalWorldCoprocessor(llm_client=llm_client)
    for doc in LEGAL_CORPUS:
        kind = doc.get("kind", "statute")
        if kind == "case":
            coprocessor.ingest_case(
                citation=doc["citation"],
                title=doc["title"],
                text=doc["text"],
                tags=doc.get("tags", []),
            )
        else:
            coprocessor.ingest_statute(
                citation=doc["citation"],
                title=doc["title"],
                text=doc["text"],
                tags=doc.get("tags", []),
            )
    coprocessor.build_index()
    return coprocessor


def evaluate_legal_coprocessor(
    questions: list[LegalQuestion] | None = None,
    *,
    llm_client=None,
) -> dict[str, Any]:
    """Compare OCTO vs RAG baseline on the LegalBench sample."""
    questions = questions or load_legalbench_sample()
    coprocessor = build_default_coprocessor(llm_client=llm_client)

    rag_result = coprocessor.evaluate(questions, use_graph=False)
    octo_result = coprocessor.evaluate(questions, use_graph=True)

    return {
        "rag": rag_result,
        "octo": octo_result,
        "delta": octo_result["accuracy"] - rag_result["accuracy"],
    }
