"""
Find which entity a question is about, using only the question text.

Every result in this project up to now took the starting entity from the dataset
(`q_entity`). That is fine for isolating a retrieval mechanism and useless as a
product: nobody types a question with the answer's starting point attached. It
also made the comparison unfair, because the retrieval baseline got no such
help.

This does the step honestly. Given a question and the set of entity names the
graph knows about, return the entities the question actually mentions.

The method is longest-match-first over surface forms:

    "the films that share directors with the film Catch Me If You Can were ..."
                                                  ^^^^^^^^^^^^^^^^^^^^^^^^

Longest first matters. "Catch Me If You Can" contains "Catch", and a graph of
films contains both; matching the shorter one would silently start the traversal
from the wrong node.

What this deliberately does not do: fuzzy matching, abbreviation expansion,
coreference. Those are the hard parts of entity linking in a real deployment.
This handles the case where the name appears verbatim, and reports how often
that is true rather than assuming it.
"""
from __future__ import annotations

import re
from collections import defaultdict

__all__ = ["EntityLinker"]

_WORD = re.compile(r"[a-z0-9]+")

# Words that are entity names in a film graph but are almost always ordinary
# English in a question. Matching these produces confident nonsense.
_STOP = {
    "the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for", "with",
    "who", "what", "which", "when", "where", "was", "were", "is", "are", "did",
    "do", "does", "movie", "movies", "film", "films", "star", "starred", "acted",
    "directed", "wrote", "written", "release", "released", "year", "years",
    "language", "languages", "genre", "genres", "share", "shares", "shared",
    "same", "also", "person", "people", "actor", "actors", "director", "writer",
}


def _norm(s: str) -> str:
    return " ".join(_WORD.findall(s.lower()))


class EntityLinker:
    """Surface-form lookup over a fixed entity vocabulary, with short forms.

    Exact-match-only was measured and it is not enough. Shortening people's names
    the way a model does when it writes -- "Steven Spielberg" once, "Spielberg"
    after that -- left the link rate at 0.998 while the graph's *reach* fell from
    0.991 to 0.511 (`benchmarks/results/graph_vs_ann_surname.json`). Linking did
    not report failure: it matched the film title, which is always present and
    always spelled canonically, and walked from the wrong entry point. A silent
    wrong answer is worse than an empty one, because a fallback can see an empty
    one -- the zero-result fallback fired on 0.3% of those queries.

    So short forms are registered here, and only where they are unambiguous. Two
    people sharing a surname means that surname resolves to nobody rather than to
    a coin flip; `ambiguous_forms` counts how often that happened, because a
    linker that quietly guesses is the failure this exists to remove.
    """

    def __init__(self, entities, *, min_words: int = 1, min_chars: int = 4,
                 short_forms: bool = True):
        self.min_words = min_words
        self.min_chars = min_chars
        # normalised surface form -> the original names that produce it
        self._forms: dict[str, list[str]] = defaultdict(list)
        self._max_words = 1
        full: set[str] = set()
        for e in entities:
            f = _norm(e)
            if not f:
                continue
            n = len(f.split())
            if n == 1 and (f in _STOP or len(f) < min_chars):
                continue
            self._forms[f].append(e)
            full.add(f)
            self._max_words = max(self._max_words, n)

        self.ambiguous_forms = 0
        self.short_form_count = 0
        if short_forms:
            self._add_short_forms(full, min_chars)

    def _add_short_forms(self, full: set[str], min_chars: int) -> None:
        """Register `last token` and `initials + last token` for multi-word names.

        A short form never overrides a full name: if "spielberg" is already an
        entity in its own right, the short form is not registered on top of it.
        Longest-match-first in `link` then still prefers the full name whenever
        the text spells it out.
        """
        candidates: dict[str, set[str]] = defaultdict(set)
        for f in full:
            parts = f.split()
            if len(parts) < 2:
                continue
            last = parts[-1]
            if len(last) < min_chars or last in _STOP:
                continue
            candidates[last].add(f)
            initials = " ".join([p[0] for p in parts[:-1]] + [last])
            if initials != f:
                candidates[initials].add(f)

        for form, sources in candidates.items():
            if form in full:
                continue                      # a real entity owns this string
            if len(sources) != 1:
                self.ambiguous_forms += 1     # two people, one surname: link neither
                continue
            source = next(iter(sources))
            self._forms[form] = list(self._forms[source])
            self.short_form_count += 1
            self._max_words = max(self._max_words, len(form.split()))

    def link(self, question: str, *, max_hits: int = 4) -> list[str]:
        """Entities mentioned in `question`, longest match first, no overlaps."""
        toks = _norm(question).split()
        taken = [False] * len(toks)
        hits: list[str] = []
        # longest spans first, so "Catch Me If You Can" beats "Catch"
        for width in range(min(self._max_words, len(toks)), 0, -1):
            for i in range(0, len(toks) - width + 1):
                if any(taken[i:i + width]):
                    continue
                span = " ".join(toks[i:i + width])
                names = self._forms.get(span)
                if not names:
                    continue
                if width < self.min_words:
                    continue
                hits.append(names[0])
                for j in range(i, i + width):
                    taken[j] = True
                if len(hits) >= max_hits:
                    return hits
        return hits

    def __len__(self) -> int:
        return len(self._forms)
