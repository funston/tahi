"""
The generation-time checker: every span, ask the graph whether it holds.

This is the mechanism OCTO was always described as having. A span of generated
text arrives, an LLM turns it into a structured claim, and the graph answers.
Nothing is stuffed into the prompt beforehand -- the graph acts on the model's
*output*, as a check, which is what distinguishes this from GraphRAG.

    span --> [extract claim] --> [graph query] --> SUPPORTED
                  LLM                graph         CONTRADICTED
                                                   NOT_COVERED

The LLM does language, the graph does truth. Neither does the other's job.

Exposed two ways:

  `SpanValidationTool`   a tool definition an agent can call, with a JSON
                         schema, so a model can check itself mid-generation.
  `StreamingValidator`   a loop that segments a generation and checks every
                         span, for use around a normal decode.

Cadence is configurable but defaults to sentence boundaries rather than a fixed
token count. A 64-token window cuts mid-clause, and a claim split across two
windows is invisible to both -- the same boundary bug the NLI evaluator has
with its non-overlapping 200-word chunks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional, Sequence

from octo.validate.claim_extractor import Claim, ClaimExtractor
from octo.validate.fact_validator import GraphFactValidator, Validation, Verdict

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_spans(text: str, *, mode: str = "sentence",
                every_tokens: int = 64) -> list[str]:
    """Segment generated text into checkable spans.

    `sentence` is the default because a claim is a sentence-level object.
    `tokens` reproduces the RETRO-style fixed cadence when that is wanted for
    comparability, accepting that it will cut some claims in half.
    """
    text = text.strip()
    if not text:
        return []
    if mode == "sentence":
        return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    if mode == "tokens":
        words = text.split()
        return [" ".join(words[i:i + every_tokens])
                for i in range(0, len(words), every_tokens)]
    raise ValueError(f"unknown span mode {mode!r}")


@dataclass
class SpanCheck:
    """What the graph said about one span."""

    span: str
    claims: list[Claim] = field(default_factory=list)
    validations: list[Validation] = field(default_factory=list)

    @property
    def verdict(self) -> Verdict:
        """Worst verdict across the span's claims.

        CONTRADICTED dominates: one false claim makes the span false, however
        many true ones surround it.
        """
        verdicts = [v.verdict for v in self.validations]
        if Verdict.CONTRADICTED in verdicts:
            return Verdict.CONTRADICTED
        if Verdict.SUPPORTED in verdicts:
            return Verdict.SUPPORTED
        return Verdict.NOT_COVERED

    @property
    def contradictions(self) -> list[Validation]:
        return [v for v in self.validations if v.verdict is Verdict.CONTRADICTED]

    def to_dict(self) -> dict[str, Any]:
        return {
            "span": self.span,
            "verdict": self.verdict.value,
            "claims": [c.to_dict() for c in self.claims],
            "validations": [v.to_dict() for v in self.validations],
        }


class SpanValidationTool:
    """A callable tool: give it a span, it returns the graph's verdict.

    `TOOL_SPEC` is the definition to hand an agent so a model can check its own
    output mid-generation rather than being checked afterwards.
    """

    TOOL_SPEC: dict[str, Any] = {
        "name": "validate_against_graph",
        "description": (
            "Check a span of generated text against the knowledge graph. "
            "Returns supported / contradicted / not_covered for each factual "
            "claim in the span, with the graph edges that decided it. Use "
            "before asserting a fact. A 'not_covered' result means the graph "
            "has no opinion -- it does NOT mean the claim is false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "span": {
                    "type": "string",
                    "description": "The text to check. One or two sentences.",
                },
            },
            "required": ["span"],
        },
    }

    def __init__(self, validator: GraphFactValidator,
                 extractor: ClaimExtractor, *, hops: int = 2):
        self.validator = validator
        self.extractor = extractor
        self.hops = hops

    def __call__(self, span: str) -> SpanCheck:
        return self.check(span)

    def check(self, span: str) -> SpanCheck:
        claims = self.extractor.extract(span)
        if not claims:
            return SpanCheck(span=span, claims=[], validations=[])

        validations: list[Validation] = []
        for claim in claims:
            validations.append(self._validate_claim(claim, span))
        return SpanCheck(span=span, claims=claims, validations=validations)

    def _validate_claim(self, claim: Claim, span: str) -> Validation:
        """Resolve the claim onto the graph, then read polarity the right way.

        The extractor's entities must resolve to real nodes. If they do not,
        the verdict is NOT_COVERED -- the extractor cannot conjure a fact into
        existence, only fail to locate one.
        """
        subj_nodes = self.validator.entities_in(claim.subject)
        obj_nodes = self.validator.entities_in(claim.object)
        claim.subject_node = subj_nodes[0] if subj_nodes else None
        claim.object_node = obj_nodes[0] if obj_nodes else None
        if not claim.subject_node:
            claim.unresolved.append(claim.subject)
        if not claim.object_node:
            claim.unresolved.append(claim.object)

        if not claim.subject_node:
            return Validation(Verdict.NOT_COVERED, claim.verbatim or span,
                              relation=claim.relation)

        base = self.validator.validate(
            claim.object if claim.object_node else "",
            subject=claim.subject_node,
            relation=claim.relation,
            hops=self.hops,
        )

        # Polarity inverts the reading. The graph answers "does this edge
        # exist"; the text may be asserting that it does NOT. A denied claim
        # about an edge that exists is a contradiction, and an affirmed claim
        # about an edge that exists is support.
        if claim.denied:
            if base.verdict is Verdict.SUPPORTED:
                return Validation(Verdict.CONTRADICTED,
                                  claim.verbatim or span,
                                  subject=claim.subject_node,
                                  relation=claim.relation,
                                  matched_entities=base.matched_entities,
                                  supporting_edges=base.supporting_edges,
                                  expected_values=base.expected_values,
                                  hops=base.hops)
            if base.verdict is Verdict.CONTRADICTED:
                # Text denies an edge the graph also denies -- they agree.
                return Validation(Verdict.SUPPORTED, claim.verbatim or span,
                                  subject=claim.subject_node,
                                  relation=claim.relation,
                                  matched_entities=base.matched_entities,
                                  expected_values=base.expected_values)
        return base


class StreamingValidator:
    """Check a generation span by span, optionally intervening.

    `on_contradiction` is called with each contradicted SpanCheck. Returning a
    replacement string substitutes it; returning None leaves the span and
    records the contradiction. Recording without intervening is the honest
    default for a measurement run -- rewriting output would make the
    contradiction rate unmeasurable.
    """

    def __init__(self, tool: SpanValidationTool, *, mode: str = "sentence",
                 every_tokens: int = 64,
                 on_contradiction: Optional[Callable[[SpanCheck], Optional[str]]] = None):
        self.tool = tool
        self.mode = mode
        self.every_tokens = every_tokens
        self.on_contradiction = on_contradiction

    def check_text(self, text: str) -> list[SpanCheck]:
        return [self.tool.check(s) for s in
                split_spans(text, mode=self.mode, every_tokens=self.every_tokens)]

    def iter_checks(self, text: str) -> Iterator[SpanCheck]:
        for span in split_spans(text, mode=self.mode,
                                every_tokens=self.every_tokens):
            yield self.tool.check(span)

    def validate_and_revise(self, text: str) -> tuple[str, list[SpanCheck]]:
        """Return (possibly revised text, all span checks)."""
        out: list[str] = []
        checks: list[SpanCheck] = []
        for span in split_spans(text, mode=self.mode,
                                every_tokens=self.every_tokens):
            check = self.tool.check(span)
            checks.append(check)
            replacement = None
            if check.verdict is Verdict.CONTRADICTED and self.on_contradiction:
                replacement = self.on_contradiction(check)
            out.append(replacement if replacement is not None else span)
        return " ".join(out), checks


def summarise(checks: Sequence[SpanCheck]) -> dict[str, Any]:
    """Counts for a run. Deliberately raw -- no derived 'truthfulness score'.

    A single composite number is what let a broken metric hide for months here.
    Report the three counts and let a reader see the shape.
    """
    counts = {v.value: 0 for v in Verdict}
    for c in checks:
        counts[c.verdict.value] += 1
    total = len(checks)
    return {
        "spans": total,
        "supported": counts[Verdict.SUPPORTED.value],
        "contradicted": counts[Verdict.CONTRADICTED.value],
        "not_covered": counts[Verdict.NOT_COVERED.value],
        "claims": sum(len(c.claims) for c in checks),
    }
