"""
EnterpriseRAG-Bench dataset adapter.

Source: https://github.com/onyx-dot-app/EnterpriseRAG-Bench (MIT)
        https://huggingface.co/datasets/onyx-dot-app/EnterpriseRAG-Bench

511,962 synthetic documents across nine enterprise sources (Slack, Gmail,
Linear, Google Drive, HubSpot, Fireflies, GitHub, Jira, Confluence) and 500
questions in ten categories, with labelled gold document IDs.

Why this benchmark rather than HotpotQA: several of its categories are direct
tests of the structural claim TAHI makes, and flat vector similarity has no
mechanism for them.

    project_related    aggregate across documents linked by project  -> graph edges
    constrained        qualifiers narrow many candidates to one      -> constraints
    conflicting_info   documents disagree; answer must reconcile     -> provenance
    completeness       must retrieve ALL relevant documents          -> graph closure
    info_not_found     answer absent; must recognise absence         -> abstention
    intra_doc_reasoning combine distant sections of one document     -> structure

The corpus is also large enough that gold leakage is impossible by
construction: an arm must retrieve from 512k documents or it has nothing.

KNOWN LIMITATIONS -- state these in any writeup:
  * The corpus is LLM-generated. The authors note it "lacks realistic tangents"
    and carries synthetic-randomness artifacts. Synthetic text may be unusually
    well-structured, which could flatter a structure-exploiting system. Treat a
    win here as necessary, not sufficient.
  * The authors describe gold sets as "revisable hypotheses rather than fixed
    ground truth" -- not a hard oracle.
  * Correctness is LLM-judged. The judge model must be pinned in the manifest
    or results are not reproducible run to run.
  * 500 questions total, but per-category N is small (high_level=10,
    conflicting_info=20). Only `basic` (175) and `semantic` (125) support
    per-category significance; see tahi.eval.stats.required_n.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# Per-category counts published in the paper. Used to check a loaded slice is
# the real dataset and to warn about underpowered per-category claims.
# Verified against the real questions.jsonl (v1.0.0), not the paper's prose --
# the dataset spells it `intra_document_reasoning`.
CATEGORY_COUNTS: dict[str, int] = {
    "basic": 175,
    "semantic": 125,
    "intra_document_reasoning": 40,
    "project_related": 40,
    "constrained": 30,
    "conflicting_info": 20,
    "completeness": 20,
    "miscellaneous": 20,
    "info_not_found": 20,
    "high_level": 10,
}

# Categories where TAHI's structural thesis predicts an advantage over flat
# dense retrieval. Declared here, before any run, so the prediction is on record.
STRUCTURE_SENSITIVE: frozenset[str] = frozenset({
    "project_related",
    "constrained",
    "conflicting_info",
    "completeness",
    "intra_document_reasoning",
    "info_not_found",
})

SOURCE_TYPES: tuple[str, ...] = (
    "slack", "gmail", "linear", "google_drive", "hubspot",
    "fireflies", "github", "jira", "confluence",
)


@dataclass
class EnterpriseQuestion:
    id: str
    text: str
    gold_answer: str
    category: str
    gold_document_ids: list[str] = field(default_factory=list)
    atomic_facts: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)
    """Individual answer facts, for fine-grained completeness scoring."""

    @property
    def is_unanswerable(self) -> bool:
        """info_not_found items: the correct behaviour is to abstain."""
        return self.category == "info_not_found"

    @property
    def is_structure_sensitive(self) -> bool:
        return self.category in STRUCTURE_SENSITIVE


@dataclass
class EnterpriseDocument:
    doc_id: str
    text: str
    source: str
    """One of SOURCE_TYPES -- the top-level directory."""
    container: str = ""
    """The second-level directory. Its meaning is source-dependent and it is
    the single richest free signal in the corpus:

        slack/<channel>        gmail/<person>       github/<repo>
        confluence/<space>     linear/<project>     jira/<queue>
        google_drive/<drive>   hubspot/(flat)       fireflies/(flat)
    """
    slug: str = ""
    """Filename text after the `__` separator, e.g. `pr-29012-cost-pilot-...`."""
    metadata: dict[str, Any] = field(default_factory=dict)

    # Meaning of `container` per source type -> (node type, edge relation).
    _CONTAINER_SEMANTICS: dict[str, tuple[str, str]] = field(
        default=None, init=False, repr=False, compare=False
    )

    def entity_links(self) -> dict[str, Any]:
        """Typed relations derivable with zero hand-curation.

        The corpus ships as plain `.txt` with no JSON metadata, so every edge
        here comes from the filesystem layout the source systems already
        imposed. That is the point: for enterprise systems of record the
        ontology is a byproduct of how the data is stored, not a consulting
        engagement -- which is the direct test of TAHI's main scaling objection.
        """
        semantics = {
            "slack": ("channel", "in_channel"),
            "confluence": ("space", "in_space"),
            "linear": ("project", "in_project"),
            "jira": ("project", "in_project"),
            "github": ("repo", "in_repo"),
            "gmail": ("person", "authored_by"),
            "google_drive": ("drive", "in_drive"),
        }
        links: dict[str, Any] = {}
        if self.container:
            node_type, relation = semantics.get(self.source, ("collection", "in_collection"))
            links[relation] = (node_type, self.container)
        return links


def _first_present(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def load_questions(path: str | Path, limit: int | None = None) -> list[EnterpriseQuestion]:
    """Load questions.jsonl."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"EnterpriseRAG-Bench questions not found at {path}.\n"
            "Download: https://github.com/onyx-dot-app/EnterpriseRAG-Bench (releases)\n"
            "      or: https://huggingface.co/datasets/onyx-dot-app/EnterpriseRAG-Bench"
        )
    out: list[EnterpriseQuestion] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out.append(
                EnterpriseQuestion(
                    id=str(_first_present(rec, "question_id", "id", default=len(out))),
                    text=_first_present(rec, "question", "query", "text", default=""),
                    gold_answer=_first_present(rec, "gold_answer", "answer", default=""),
                    # The dataset field is `question_type`.
                    category=_first_present(
                        rec, "question_type", "category", "type", default="unknown"
                    ),
                    # The dataset field is `expected_doc_ids`.
                    gold_document_ids=list(
                        _first_present(rec, "expected_doc_ids", "gold_document_ids",
                                       "document_ids", default=[]) or []
                    ),
                    atomic_facts=list(
                        _first_present(rec, "answer_facts", "atomic_facts", default=[]) or []
                    ),
                    source_types=list(_first_present(rec, "source_types", default=[]) or []),
                )
            )
            if limit is not None and len(out) >= limit:
                break

    unknown = {q.category for q in out} - set(CATEGORY_COUNTS)
    if unknown:
        raise ValueError(
            f"Unrecognised question categories {sorted(unknown)}. CATEGORY_COUNTS and "
            "STRUCTURE_SENSITIVE must be updated -- a silently-unmatched category "
            "would be dropped from the structure-sensitive pool and quietly shrink "
            "the primary comparison."
        )
    return out


def iter_documents(corpus_dir: str | Path) -> Iterator[EnterpriseDocument]:
    """Stream the corpus. 511,962 documents will not fit comfortably in memory.

    Layout (v1.0.0):  <corpus>/<source_type>/[<container>/]<dsid>__<slug>.txt

    Documents are plain text, NOT JSON -- the paper's "flattened JSON key-value
    pairs" describes generation, not the released artifact. The document ID is
    the filename segment before `__`, and it is what `expected_doc_ids`
    references, so getting this parse wrong silently zeroes document recall for
    every arm.
    """
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        raise FileNotFoundError(
            f"EnterpriseRAG-Bench corpus not found at {corpus_dir}.\n"
            "Download all_documents.zip from the GitHub releases page and extract it."
        )

    files = sorted(corpus_dir.rglob("*.txt"))
    if not files:
        raise FileNotFoundError(
            f"No .txt documents under {corpus_dir}. Expected the extracted "
            "all_documents.zip tree (sources/<source_type>/.../<dsid>__<slug>.txt)."
        )

    root_parts = len(corpus_dir.parts)
    for fp in files:
        rel = fp.parts[root_parts:]
        source = rel[0] if len(rel) > 1 else "unknown"
        container = rel[1] if len(rel) > 2 else ""

        stem = fp.stem
        doc_id, _, slug = stem.partition("__")
        if not doc_id.startswith("dsid_"):
            # Unexpected filename shape: keep the document but leave the id
            # empty so it is excluded from recall rather than scored wrongly.
            doc_id, slug = "", stem

        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        yield EnterpriseDocument(
            doc_id=doc_id,
            text=text,
            source=source,
            container=container,
            slug=slug,
            metadata={"path": fp.as_posix()},
        )


def summarize(questions: list[EnterpriseQuestion]) -> dict[str, Any]:
    """Category breakdown plus a power warning for underpowered categories."""
    from collections import Counter

    from tahi.eval.stats import required_n

    counts = Counter(q.category for q in questions)
    need = required_n(0.10)  # items to detect a 10-point delta at 95%/80%
    underpowered = sorted(c for c, n in counts.items() if n < need)
    return {
        "n_total": len(questions),
        "by_category": dict(sorted(counts.items())),
        "structure_sensitive_n": sum(
            n for c, n in counts.items() if c in STRUCTURE_SENSITIVE
        ),
        "required_n_for_0.10_delta": need,
        "underpowered_categories": underpowered,
        "power_note": (
            f"Categories with fewer than {need} items cannot support a per-category "
            "significance claim for a 0.10 delta. Report those as descriptive only, "
            "and draw significance from the aggregate or from pooled "
            "structure-sensitive categories."
        ),
    }
