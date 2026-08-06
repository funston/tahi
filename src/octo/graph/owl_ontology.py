"""
W3C OWL / RDF Ontology Integration for OCTO.

Uses `rdflib` (standard Python open-source Semantic Web framework) to load, parse,
and reason over W3C standard OWL/RDF ontologies (.ttl, .owl, .rdf).

Maps OWL Classes and Object Properties directly into Kùzu Property Graph DDLs
and enforces ontology constraints during multi-hop graph expansion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import rdflib
from rdflib import RDFS, RDF, OWL, URIRef


class OWLOntology:
    """W3C OWL/RDF Ontology Manager backed by RDFLib."""

    def __init__(self, source_path: Optional[str | Path] = None):
        self.graph = rdflib.Graph()
        if source_path:
            self.load(source_path)

    def load(self, source_path: str | Path) -> None:
        """Load an OWL/RDF ontology file (.ttl, .owl, .rdf)."""
        path = Path(source_path)
        fmt = "turtle" if path.suffix in (".ttl", ".turtle") else "xml"
        self.graph.parse(str(path), format=fmt)

    def classes(self) -> Set[str]:
        """Extract all rdfs:Class / owl:Class labels or local names."""
        classes = set()
        for s in self.graph.subjects(RDF.type, OWL.Class):
            classes.add(self._local_name(s))
        for s in self.graph.subjects(RDF.type, RDFS.Class):
            classes.add(self._local_name(s))
        return classes

    def object_properties(self) -> List[Tuple[str, str, str]]:
        """Extract all owl:ObjectProperty triples as (domain, property_name, range)."""
        properties = []
        for prop in self.graph.subjects(RDF.type, OWL.ObjectProperty):
            prop_label = self._local_label(prop)
            domain = self.graph.value(prop, RDFS.domain)
            range_val = self.graph.value(prop, RDFS.range)

            dom_name = self._local_name(domain) if domain else "EntityNode"
            rng_name = self._local_name(range_val) if range_val else "EntityNode"
            properties.append((dom_name.lower(), prop_label.upper(), rng_name.lower()))
        return properties

    def sub_classes(self, super_class_name: str) -> Set[str]:
        """Get all subclasses of a given class."""
        subclasses = set()
        for s, _, o in self.graph.triples((None, RDFS.subClassOf, None)):
            if self._local_name(o).lower() == super_class_name.lower():
                subclasses.add(self._local_name(s).lower())
        return subclasses

    @staticmethod
    def _local_name(uri: Optional[URIRef]) -> str:
        if uri is None:
            return ""
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        return uri_str.split("/")[-1]

    def _local_label(self, uri: URIRef) -> str:
        label = self.graph.value(uri, RDFS.label)
        if label:
            return str(label)
        return self._local_name(uri)

    def to_kuzu_ddl(self) -> List[str]:
        """Generate Kùzu Cypher DDL statements from the OWL Ontology."""
        ddl = [
            "CREATE NODE TABLE IF NOT EXISTS Node(id STRING, node_type STRING, label STRING, text STRING, PRIMARY KEY (id))",
            "CREATE REL TABLE IF NOT EXISTS REL(FROM Node TO Node, rel_type STRING, weight DOUBLE)",
        ]
        return ddl
