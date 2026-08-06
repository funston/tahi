"""
Does this span affirm or deny the claim it mentions?

The graph knows `aspirin --binds--> COX-1`. If a model emits "it does not bind
COX-1", the graph plainly says that is false, and a validator that returns
SUPPORTED is broken. This module supplies the missing half: which mentions are
inside a negation, so the edge lookup can be read the right way round.

It is scope-aware rather than a keyword flag, because a bare `"not" in text`
test is wrong on the cases that actually occur:

    "Aspirin binds COX-2, not COX-1"     negation applies to COX-1 only
    "It doesn't fail to bind COX-1"      two cues cancel -- affirmed
    "It binds everything except COX-1"   `except` is a negation cue
    "Aspirin lacks affinity for COX-1"   negated with no negation word

The rule: a cue opens a scope that runs to the next clause boundary (comma,
conjunction, or sentence end). A mention inside an odd number of scopes is
denied; an even number (including zero) is affirmed.

This is a heuristic and it has an error rate. `tests/test_polarity.py` measures
that rate on an adversarial probe set and asserts a floor, because an
unmeasured heuristic is how `fact_coverage` shipped with a negation delta of
exactly 0.0000.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Cues that open a negation scope. Multi-word cues are matched before single
# words so "fail to" is not missed by a "to" boundary.
NEGATION_CUES = (
    "does not", "do not", "did not", "is not", "are not", "was not",
    "were not", "has not", "have not", "had not", "cannot", "can not",
    "will not", "would not", "should not", "must not",
    "doesn't", "don't", "didn't", "isn't", "aren't", "wasn't", "weren't",
    "hasn't", "haven't", "hadn't", "can't", "won't", "wouldn't",
    "shouldn't", "mustn't",
    "fails to", "fail to", "failed to",
    "lacks", "lack", "lacked",
    "never", "not", "no", "none", "neither", "nor",
    "without", "except", "excluding", "other than", "rather than",
    "absent", "devoid of", "free of",
)

# A negation scope ends at a clause boundary. Without this, "binds COX-2, not
# COX-1" would mark COX-2 as denied.
CLAUSE_BOUNDARIES = (",", ";", ".", " and ", " but ", " while ", " whereas ",
                     " although ", " though ", " however ")


@dataclass
class Polarity:
    """Whether a span affirms or denies, and why."""

    negated: bool
    cues: list[str]
    scope_text: str = ""

    @property
    def affirmed(self) -> bool:
        return not self.negated


def _cue_positions(text: str) -> list[tuple[int, int, str]]:
    """(start, end, cue) for every negation cue, longest-match, no overlaps."""
    lowered = text.lower()
    hits: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for cue in sorted(NEGATION_CUES, key=len, reverse=True):
        # Word-boundary match so "no" does not fire inside "node" or "known".
        for m in re.finditer(rf"(?<![a-z]){re.escape(cue)}(?![a-z])", lowered):
            s, e = m.span()
            if any(s < te and ts < e for ts, te in taken):
                continue
            taken.append((s, e))
            hits.append((s, e, cue))
    return sorted(hits)


def _scope_end(text: str, start: int) -> int:
    """Where the negation opened at `start` stops applying."""
    lowered = text.lower()
    end = len(text)
    for b in CLAUSE_BOUNDARIES:
        idx = lowered.find(b, start)
        if idx != -1:
            end = min(end, idx)
    return end


def polarity_of_mention(text: str, mention: str) -> Polarity:
    """Is `mention` denied in `text`?

    Counts how many negation scopes cover the mention. Odd means denied, which
    makes double negation ("doesn't fail to bind") come out affirmed rather
    than flipping once and stopping.
    """
    lowered = text.lower()
    m_low = mention.lower()
    pos = lowered.find(m_low)
    if pos == -1:
        return Polarity(negated=False, cues=[])

    covering: list[str] = []
    scope_text = ""
    for start, end, cue in _cue_positions(text):
        if end > pos:
            continue  # cue appears after the mention -- does not scope it
        if pos < _scope_end(text, start):
            covering.append(cue)
            if not scope_text:
                scope_text = text[start:_scope_end(text, start)].strip()

    return Polarity(negated=len(covering) % 2 == 1, cues=covering,
                    scope_text=scope_text)


def span_polarity(text: str) -> Polarity:
    """Polarity of the span as a whole, for callers with no specific mention."""
    cues = [c for _s, _e, c in _cue_positions(text)]
    return Polarity(negated=len(cues) % 2 == 1, cues=cues, scope_text=text)
