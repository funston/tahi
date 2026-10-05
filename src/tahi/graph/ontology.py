"""
Typed Ontology Schemas for TAHI World Models.

Provides explicit, domain-enforced ontologies governing node types, relation types,
and valid traversal paths. Prevents noisy or arbitrary edge expansion by ensuring
that graph traversal strictly follows legal ontology paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OntologySchema:
    domain: str
    allowed_node_types: set[str] = field(default_factory=set)
    allowed_relation_triples: set[tuple[str, str, str]] = field(default_factory=set)  # (src_type, rel, dst_type)
    evidence_node_types: set[str] = field(default_factory=set)
    traversal_seed_types: set[str] = field(default_factory=set)

    def validate_node(self, node_id: str, attrs: dict) -> bool:
        """Return True if node attrs conform to allowed node types."""
        ntype = attrs.get("type", "concept")
        if self.allowed_node_types and ntype not in self.allowed_node_types:
            return False
        return True

    def validate_relation(self, src_type: str, rel_type: str, dst_type: str) -> bool:
        """Return True if the relation (src_type, rel_type, dst_type) is permitted by ontology."""
        if not self.allowed_relation_triples:
            return True  # Permissive default if schema specifies no restriction
        return (src_type, rel_type, dst_type) in self.allowed_relation_triples or (dst_type, rel_type, src_type) in self.allowed_relation_triples


def get_default_enterprise_rag_ontology() -> OntologySchema:
    """Standard Enterprise RAG ontology schema."""
    return OntologySchema(
        domain="enterprise_rag",
        allowed_node_types={"document", "entity", "project", "topic", "person", "location"},
        allowed_relation_triples={
            ("document", "MENTIONS", "entity"),
            ("document", "MENTIONS", "project"),
            ("document", "MENTIONS", "topic"),
            ("project", "HAS_DOC", "document"),
            ("topic", "COVERS", "document"),
            ("entity", "RELATED_TO", "entity"),
            ("project", "RELATED_TO", "project"),
        },
        evidence_node_types={"document"},
        traversal_seed_types={"entity", "project", "topic", "person", "location"},
    )
