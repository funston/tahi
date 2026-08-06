"""
Build an OCTO WorldModel from the EnterpriseRAG-Bench corpus.

This is where OCTO either earns its keep or does not. `StandaloneRAG` sees the
same documents as a flat list of text chunks. The world model additionally
carries typed relations lifted from source metadata:

    doc --authored_by--> person
    doc --in_project---> project
    doc --in_thread----> thread      (Slack threads, email chains)
    doc --references---> ticket      (Jira/Linear IDs mentioned in text)
    doc --in_repo------> repo
    doc --about--------> company     (HubSpot deals)

Nothing here is hand-curated. Every edge comes from a structured field that the
source system already populated, which is the practical answer to OCTO's main
scaling objection: for enterprise systems of record, the ontology is a byproduct
of the data, not a consulting engagement.

The prediction under test: on questions that require combining documents linked
by one of these relations, traversing the edge beats hoping the two documents
happen to be near each other in embedding space.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from octo.world_state import WorldModel

from .dataset import EnterpriseDocument

# Jira/Linear-style ticket references appearing in free text (ENG-1234, OPS-77).
TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9})-(\d{1,6})\b")

# `Marco:` / `legal-bot:` at line start in Slack and Fireflies transcripts.
SPEAKER_RE = re.compile(r"^([A-Z][a-zA-Z]{1,20})(?=:\s)", re.MULTILINE)

# Token shapes that match TICKET_RE but are not tickets. Without these, every
# document mentioning UTF-8 gets joined to every other one -- a hub node that
# actively degrades traversal.
_TICKET_STOPWORDS = frozenset({
    "UTF", "ISO", "SHA", "RFC", "HTTP", "HTTPS", "TLS", "SSL", "AES", "RSA",
    "GPT", "API", "SLA", "SLO", "P", "A", "B", "X", "IPV", "CVE", "SOC",
})

_SPEAKER_STOPWORDS = frozenset({
    "note", "impact", "summary", "environment", "expected", "observed",
    "issue", "steps", "context", "update", "action", "owner", "status",
    "timeline", "agenda", "attendees", "decision", "risk", "next", "goal",
    "problem", "solution", "background", "scope", "result", "example",
})

# metadata key -> (node type, edge relation). Order is stable so builds are
# reproducible across runs.

MAX_DOC_CHARS = 4000
"""Documents are truncated for the embedding text only. Full text stays on the
node so an answer prompt can use it."""


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_world_model(
    documents: Iterable[EnterpriseDocument],
    *,
    domain: str = "enterprise_rag",
    use_ann: bool = True,
    extract_tickets: bool = True,
) -> tuple[WorldModel, dict[str, int]]:
    """Build a typed graph + vector world model over the corpus.

    Returns the model and a stats dict recording how many nodes and edges of
    each kind were created -- reported in the manifest so a run where the graph
    came out empty is visible rather than being read as "the graph didn't help".
    """
    wm = WorldModel(domain=domain)
    try:
        wm.init_kuzu()
    except Exception as e:
        pass
    stats: Counter[str] = Counter()

    for doc in documents:
        if not doc.doc_id:
            stats["skipped_no_id"] += 1
            continue

        doc_node = f"doc::{doc.doc_id}"
        wm.upsert_node(
            doc_node,
            type="document",
            label=doc.doc_id,
            text=doc.text,
            summary=doc.text[:MAX_DOC_CHARS],
            source=doc.source,
        )
        stats["documents"] += 1
        stats[f"source::{doc.source}"] += 1

        def link(node_type: str, value: str, relation: str) -> None:
            value = _clean(value) or ""
            if not value:
                return
            entity_node = f"{node_type}::{value}"
            wm.upsert_node(
                entity_node, type=node_type, label=value,
                summary=f"{node_type}: {value}", text=value,
            )
            wm.add_edge(doc_node, relation, entity_node)
            # Reverse edge so traversal from an entity reaches its documents --
            # this is what "aggregate everything in project X" needs.
            wm.add_edge(entity_node, f"has_{relation}", doc_node)
            stats[f"edge::{relation}"] += 1

        # 1. Container edge (channel / space / project / repo / mailbox).
        #    Free structure from the source system's own organisation.
        for relation, (node_type, value) in doc.entity_links().items():
            link(node_type, value, relation)

        head = doc.text[:MAX_DOC_CHARS]

        # 2. Ticket and incident IDs in prose. These are the genuine
        #    cross-source links -- a Slack thread citing INC-2026-0142 and the
        #    Jira issue itself become two documents joined by one node, which
        #    embedding similarity has no way to connect.
        if extract_tickets:
            for prefix, number in set(TICKET_RE.findall(head)):
                if prefix in _TICKET_STOPWORDS:
                    continue
                link("ticket", f"{prefix}-{number}", "mentions")

        # 3. Speaker names in transcript-shaped sources (Slack, Fireflies).
        #    `Marco: ...` at line start is a participation edge.
        if doc.source in ("slack", "fireflies"):
            for name in set(SPEAKER_RE.findall(head)):
                if name.lower() not in _SPEAKER_STOPWORDS:
                    link("person", name, "participant")

    # These node types exist to be traversed through, not read. Excluding them
    # from results means `top_k` buys the same number of readable documents it
    # buys a document-only baseline -- previously it did not, and the two arms
    # were compared at different effective budgets.
    wm.set_index_node_types({
        "person", "project", "thread", "channel", "space", "repo",
        "drive", "ticket", "company", "collection",
    })
    wm.use_ann = use_ann
    wm.build_index()

    stats["total_nodes"] = len(wm.nodes)
    return wm, dict(stats)


def graph_health(stats: dict[str, int]) -> list[str]:
    """Warn when the graph is too sparse for traversal to be doing anything.

    A world model with no edges is a vector index with extra steps. If that is
    the state, the honest conclusion from a null result is "the graph was empty",
    not "structure does not help".
    """
    problems: list[str] = []
    docs = stats.get("documents", 0)
    edges = sum(v for k, v in stats.items() if k.startswith("edge::"))
    if docs == 0:
        problems.append("No documents were indexed.")
        return problems
    if edges == 0:
        problems.append(
            "The world model has ZERO relation edges -- it is a vector index with "
            "extra steps. Any OCTO-vs-RAG null result here says nothing about the "
            "structural thesis. Check that corpus metadata is being parsed."
        )
    elif edges / docs < 0.5:
        problems.append(
            f"Only {edges} edges across {docs} documents ({edges/docs:.2f} per doc). "
            "Graph traversal has little to traverse; treat structural conclusions "
            "as weak."
        )
    return problems
