"""
Derive a graph query from a prompt, using only the graph's published schema.

This is the step that was previously cheated. Earlier trials carried the target
relation in the question metadata, so the system never had to work out what was
being asked -- the equivalent of hardcoding which SiriKit intent fires instead
of resolving it from the utterance.

Nothing here is specific to Hetionet. The graph publishes
`[source_kind, target_kind, relation, direction]` for each edge type, and that
schema does most of the work:

    "What genes does the compound Mepyramine bind?"
        subject span  -> "Mepyramine" -> Compound::DB06691   (kind: Compound)
        target kind   -> "genes"      -> Gene
        schema filter -> Compound->Gene = {binds, downregulates, upregulates}
        verb match    -> "bind"       -> binds
        => query (Compound::DB06691, CbG)

Step 3 is what makes this tractable: knowing the subject's kind and the asked-for
kind usually leaves a handful of candidate relations, exactly as an intent schema
constrains what an utterance can mean. The verb only has to disambiguate among
those, not among everything.

Returns None when it cannot resolve, which is a first-class outcome: the caller
is expected to fall back to unassisted generation and report the abstention rate
rather than hide it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence


@dataclass
class QueryPlan:
    """A resolved graph query, or an explained failure."""

    subject_span: Optional[str] = None
    subject_node: Optional[str] = None
    subject_kind: Optional[str] = None
    target_kind: Optional[str] = None
    relation: Optional[str] = None
    metaedge: Optional[str] = None
    candidates: list[str] = None
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return bool(self.subject_node and self.metaedge)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_span": self.subject_span, "subject_node": self.subject_node,
            "subject_kind": self.subject_kind, "target_kind": self.target_kind,
            "relation": self.relation, "metaedge": self.metaedge,
            "candidates": list(self.candidates or []), "reason": self.reason,
            "resolved": self.resolved,
        }


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower())


def _stem(word: str) -> str:
    """Crude suffix stripping so `bind`/`binds`/`binding` collapse together."""
    w = word.lower()
    for suf in ("ing", "es", "ed", "s"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


class QueryPlanner:
    """Turns a prompt into (subject node, metaedge) from schema alone."""

    def __init__(self, metagraph: dict, resolve_entity: Callable[[str, str], Any],
                 node_kinds: Sequence[str] | None = None):
        """`resolve_entity(span, kind) -> (node_id, score)`; supply the linker."""
        self.tuples = [tuple(t) for t in metagraph["metaedge_tuples"]]
        self.abbrev = metagraph.get("kind_to_abbrev", {})
        self.kinds = list(node_kinds or metagraph.get("metanode_kinds", []))
        self.resolve_entity = resolve_entity

        # Surface forms for each node kind, derived from the schema's own names.
        self.kind_forms: dict[str, list[str]] = {}
        for k in self.kinds:
            base = k.lower()
            forms = {base, base + "s"}
            if base.endswith("y"):
                forms.add(base[:-1] + "ies")
            forms.add(base.replace(" ", ""))
            self.kind_forms[k] = sorted(forms, key=len, reverse=True)

    def metaedge_abbrev(self, src: str, tgt: str, rel: str) -> str:
        """Hetionet's abbreviation scheme: SrcAbbrev + relAbbrev + TgtAbbrev."""
        return (f"{self.abbrev.get(src, src[:1])}"
                f"{self.abbrev.get(rel, rel[:1])}"
                f"{self.abbrev.get(tgt, tgt[:1])}")

    def mentioned_kinds(self, prompt: str) -> list[str]:
        """Every node kind named in the prompt, in order of first appearance.

        A prompt commonly names two: the kind being asked for and the kind of
        the subject ("What **genes** does the **compound** Mepyramine bind?").
        Position order is the useful signal -- the asked-for kind follows the
        wh-word -- but it is only a prior. `plan` confirms the choice against
        the schema rather than trusting it.
        """
        p = f" {_norm(prompt)} "
        found: list[tuple[int, str]] = []
        for kind, forms in self.kind_forms.items():
            best = None
            for f in forms:
                i = p.find(f" {f} ")
                if i != -1 and (best is None or i < best):
                    best = i
            if best is not None:
                found.append((best, kind))
        return [k for _i, k in sorted(found)]

    def detect_target_kind(self, prompt: str) -> Optional[str]:
        kinds = self.mentioned_kinds(prompt)
        return kinds[0] if kinds else None

    def detect_subject(self, prompt: str, kind: str | None) -> tuple:
        """Longest capitalised or quoted span that resolves to a node of `kind`.

        Tries progressively shorter n-grams so multi-word names are preferred.
        """
        words = re.sub(r"[?.,;:]", " ", prompt).split()
        spans: list[str] = []
        for n in range(min(5, len(words)), 0, -1):
            for i in range(len(words) - n + 1):
                spans.append(" ".join(words[i:i + n]))
        for span in spans:
            if len(span) < 3:
                continue
            nid, score = self.resolve_entity(span, kind)
            if nid:
                return span, nid, score
        return None, None, 0.0

    def plan(self, prompt: str, subject_kind_hint: str | None = None) -> QueryPlan:
        """Try each kind named in the prompt as the target; keep the first that
        the schema and the linker can both satisfy.

        Taking the longest-matching kind name is wrong: "What genes does the
        **compound** Mepyramine bind?" names Compound as a modifier of the
        subject, not as the thing being asked for. Letting the schema arbitrate
        removes the guess.
        """
        candidates = self.mentioned_kinds(prompt)
        if not candidates:
            return QueryPlan(reason="no node kind named in the prompt")
        attempts: list[QueryPlan] = []
        for target in candidates:
            p = self._plan_for_target(prompt, target, subject_kind_hint)
            if p.resolved:
                return p
            attempts.append(p)
        return attempts[0]

    def _plan_for_target(self, prompt: str, target_kind: str,
                         subject_kind_hint: str | None = None) -> QueryPlan:

        # Only kinds the schema can actually point AT target_kind. Including
        # kinds merely adjacent to it let a spurious trigram match on an
        # unrelated kind win purely because it sorted earlier alphabetically.
        source_kinds = sorted({s for s, t, _r, _d in self.tuples
                               if t == target_kind and s != target_kind})
        if subject_kind_hint:
            source_kinds = [subject_kind_hint]

        # Best-scoring subject across candidate kinds, not the first to match.
        span = node = subj_kind = None
        best_score = 0.0
        for k in source_kinds:
            s, n, sc = self.detect_subject(prompt, k)
            if n and sc > best_score:
                span, node, subj_kind, best_score = s, n, k, sc
        if not node:
            return QueryPlan(target_kind=target_kind,
                             reason="no entity in the prompt resolved to a node "
                                    f"of a kind connected to {target_kind}")

        # Schema narrows the relation set to those linking these two kinds.
        cands = [r for s, t, r, _d in self.tuples
                 if s == subj_kind and t == target_kind]
        if not cands:
            return QueryPlan(subject_span=span, subject_node=node,
                             subject_kind=subj_kind, target_kind=target_kind,
                             reason=f"schema has no {subj_kind}->{target_kind} edge")
        if len(cands) == 1:
            rel = cands[0]
            return QueryPlan(span, node, subj_kind, target_kind, rel,
                             self.metaedge_abbrev(subj_kind, target_kind, rel),
                             cands, "only one relation in schema")

        # More than one: the prompt's verb disambiguates.
        stems = {_stem(w) for w in _norm(prompt).split()}
        hits = [r for r in cands if _stem(r) in stems]
        if len(hits) == 1:
            rel = hits[0]
            return QueryPlan(span, node, subj_kind, target_kind, rel,
                             self.metaedge_abbrev(subj_kind, target_kind, rel),
                             cands, "verb matched schema relation")
        return QueryPlan(subject_span=span, subject_node=node,
                         subject_kind=subj_kind, target_kind=target_kind,
                         candidates=cands,
                         reason=("ambiguous: prompt verb matched "
                                 f"{len(hits)} of {len(cands)} candidate relations"))
