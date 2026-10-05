"""
Turn generated text into structured claims the graph can answer.

The division of labour here is the whole point:

    LLM   ->  "what is being claimed?"        (language)
    GRAPH ->  "is that true?"                 (truth)

The LLM never decides truth. It emits `(subject, relation, object, polarity)`
and nothing else. The verdict comes from an edge existing or not existing. That
separation is what the NLI evaluator got wrong -- there a model was asked to
judge truth directly, and it went support-invariant past 512 tokens (+0.826
with AND without supporting evidence) with nothing in the harness able to tell.

Extractor errors are bounded rather than silent. Every subject and object it
returns must resolve to a real node, and every relation must exist in the
graph's vocabulary. Anything else is reported as unresolvable and the claim
becomes NOT_COVERED. The extractor therefore cannot invent a fact into
existence -- the worst it can do is fail to find one.

Strict by default: with no LLM backend configured this raises rather than
falling back to a heuristic. A silent degrade is how a hash embedding once
replaced a semantic encoder here without a single warning.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from tahi.llm_client import LLMClient, LLMNotConfiguredError, is_configured

SYSTEM = (
    "You extract factual claims from text. You never judge whether a claim is "
    "true. You only report what the text asserts. Reply with JSON only."
)

PROMPT = """\
Extract every factual claim the TEXT makes, as JSON.

Return a JSON array. Each element:
  "subject"  : the entity the claim is about, verbatim from the text
  "relation" : one of the ALLOWED RELATIONS below, or null if none fits
  "object"   : the entity or value asserted, verbatim from the text
  "polarity" : "affirmed" if the text asserts the claim holds,
               "denied" if the text asserts it does NOT hold
  "verbatim" : the exact span of TEXT this came from

Rules:
- "X does not bind Y" -> polarity "denied", NOT a claim about something else.
- "X binds Y, not Z"  -> TWO claims: (X,binds,Y,affirmed) and (X,binds,Z,denied).
- "X lacks affinity for Y" -> polarity "denied".
- Double negation ("does not fail to bind Y") -> polarity "affirmed".
- If the text makes no factual claim, return [].
- Do not infer facts that the text does not state.

ALLOWED RELATIONS:
{relations}

TEXT:
{text}

JSON:"""


@dataclass
class Claim:
    """One assertion made by the text, before any graph lookup."""

    subject: str
    relation: str | None
    object: str
    polarity: str = "affirmed"          # "affirmed" | "denied"
    verbatim: str = ""

    # Filled in by resolution against the graph.
    subject_node: str | None = None
    object_node: str | None = None
    unresolved: list[str] = field(default_factory=list)

    @property
    def denied(self) -> bool:
        return self.polarity == "denied"

    @property
    def resolved(self) -> bool:
        return bool(self.subject_node and self.object_node and self.relation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject, "relation": self.relation,
            "object": self.object, "polarity": self.polarity,
            "verbatim": self.verbatim, "subject_node": self.subject_node,
            "object_node": self.object_node, "unresolved": list(self.unresolved),
        }


class ClaimExtractionError(RuntimeError):
    """The extractor returned something that is not parseable as claims."""


def _parse_json_array(text: str) -> list[dict]:
    """Pull the JSON array out of a model reply, strictly.

    Strict on purpose: a half-parsed extraction that silently drops claims
    would understate the contradiction rate, and understating it is the
    direction that flatters the system.
    """
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ClaimExtractionError(f"No JSON array in extractor reply: {text[:200]!r}")
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ClaimExtractionError(f"Malformed JSON from extractor: {e}") from e
    if not isinstance(parsed, list):
        raise ClaimExtractionError("Extractor reply was not a JSON array.")
    return [p for p in parsed if isinstance(p, dict)]


class ClaimExtractor:
    """LLM-backed text -> claims. Does not touch the graph."""

    def __init__(self, llm: LLMClient | None = None, *,
                 relations: Sequence[str] = (), strict: bool = True):
        if llm is None:
            if strict and not is_configured():
                raise LLMNotConfiguredError(
                    "ClaimExtractor needs a real LLM backend. Refusing to fall "
                    "back to a heuristic: an unmeasured extractor would make "
                    "every downstream verdict unverifiable. Configure a "
                    "provider or pass strict=False deliberately."
                )
            llm = LLMClient.from_env()
        self.llm = llm
        self.relations = list(relations)

    def extract(self, text: str) -> list[Claim]:
        if not text.strip():
            return []
        rel_block = "\n".join(f"- {r}" for r in self.relations) or "- (any)"
        reply = self.llm.complete(
            PROMPT.format(relations=rel_block, text=text.strip()),
            system=SYSTEM,
        )
        out: list[Claim] = []
        for row in _parse_json_array(reply.text):
            subject = str(row.get("subject") or "").strip()
            obj = str(row.get("object") or "").strip()
            if not subject or not obj:
                continue
            polarity = str(row.get("polarity") or "affirmed").strip().lower()
            if polarity not in ("affirmed", "denied"):
                polarity = "affirmed"
            relation = row.get("relation")
            out.append(Claim(
                subject=subject,
                relation=str(relation).strip() if relation else None,
                object=obj,
                polarity=polarity,
                verbatim=str(row.get("verbatim") or "").strip(),
            ))
        return out
