"""
Kùzu-backed graph store for OCTO world models.

This replaces a flat Python list. `WorldModel.edges` was
`List[Tuple[str, str, str, dict]]` and `neighbors()` scanned it linearly, so a
single lookup was O(E). On the 511,962-document EnterpriseRAG-Bench build that
is 956,232 comparisons per hop -- roughly 19 million per query at 10 seeds and
two hops, 9.5 billion across a 500-question run. There was no index of any kind.

Kùzu is an embedded property-graph database (MIT). It needs no server, stores to
a directory like SQLite, and answers multi-hop traversal with vectorized joins
instead of a scan. The queries OCTO actually needs -- "documents sharing a
project with these seeds", "documents two hops from this ticket" -- become
Cypher rather than hand-rolled BFS.

Schema
------
    (:Node {id, node_type, label, text})
    (:Node)-[:REL {rel_type, weight}]->(:Node)

A single generic node/edge table keeps the store domain-agnostic: `node_type`
and `rel_type` are properties, so a new domain adds rows, not DDL. That costs
some type-level query optimisation and buys the ability to back every OCTO
implementation with one store.
"""

from __future__ import annotations

import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import kuzu
except ImportError:  # pragma: no cover
    kuzu = None


class KuzuGraphStore:
    """Persistent, indexed graph store with multi-hop traversal.

    Falls back to nothing -- if Kùzu is unavailable the constructor raises.
    A silent fallback to linear scan is exactly the class of defect that made
    the first benchmark meaningless, so this fails loudly instead.
    """

    def __init__(self, db_path: str | Path | None = None, *, read_only: bool = False):
        if kuzu is None:
            raise ImportError(
                "kuzu is not installed. `pip install kuzu`. Refusing to fall back "
                "to linear edge scanning -- that is O(E) per lookup and was the "
                "reason graph traversal did not work."
            )
        # Kùzu wants a file path it creates itself, not an existing directory.
        self._temp = db_path is None
        if db_path is None:
            self._temp_root = Path(tempfile.mkdtemp(prefix="octo-kuzu-"))
            self.db_path = self._temp_root / "graph.kz"
        else:
            self._temp_root = None
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = kuzu.Database(str(self.db_path), read_only=read_only)
        self.conn = kuzu.Connection(self.db)
        if not read_only:
            self._ensure_schema()

    def _ensure_schema(self) -> None:
        for ddl in (
            "CREATE NODE TABLE IF NOT EXISTS Node("
            "  id STRING, node_type STRING, label STRING, text STRING,"
            "  PRIMARY KEY (id))",
            "CREATE REL TABLE IF NOT EXISTS REL("
            "  FROM Node TO Node, rel_type STRING, weight DOUBLE)",
        ):
            self.conn.execute(ddl)

    # -- ingest ------------------------------------------------------------

    def add_nodes(self, nodes: Iterable[tuple[str, dict]], batch: int = 50_000) -> int:
        """Bulk-insert nodes. `nodes` yields (node_id, attrs)."""
        rows, total = [], 0
        for node_id, attrs in nodes:
            rows.append({
                "id": node_id,
                "node_type": str(attrs.get("type") or ""),
                "label": str(attrs.get("label") or node_id),
                # Truncated: the store is for traversal, not document storage.
                # Full text stays in the WorldModel's node dict.
                "text": str(attrs.get("summary") or attrs.get("text") or "")[:2000],
            })
            if len(rows) >= batch:
                total += self._flush_nodes(rows); rows = []
        if rows:
            total += self._flush_nodes(rows)
        return total

    def _flush_nodes(self, rows: list[dict]) -> int:
        self.conn.execute(
            "UNWIND $rows AS r MERGE (n:Node {id: r.id}) "
            "SET n.node_type = r.node_type, n.label = r.label, n.text = r.text",
            {"rows": rows},
        )
        return len(rows)

    def add_edges(self, edges: Iterable[tuple[str, str, str, dict]],
                  batch: int = 50_000) -> int:
        """Bulk-insert edges. `edges` yields (src, rel_type, dst, attrs)."""
        rows, total = [], 0
        for src, rel, dst, attrs in edges:
            rows.append({"src": src, "dst": dst, "rel": str(rel),
                         "w": float(attrs.get("score", 1.0)) if attrs else 1.0})
            if len(rows) >= batch:
                total += self._flush_edges(rows); rows = []
        if rows:
            total += self._flush_edges(rows)
        return total

    def _flush_edges(self, rows: list[dict]) -> int:
        self.conn.execute(
            "UNWIND $rows AS r "
            "MATCH (a:Node {id: r.src}), (b:Node {id: r.dst}) "
            "MERGE (a)-[e:REL {rel_type: r.rel}]->(b) SET e.weight = r.w",
            {"rows": rows},
        )
        return len(rows)

    # -- query -------------------------------------------------------------

    def neighbors(self, node_id: str, rel_types: Sequence[str] | None = None
                  ) -> list[tuple[str, str, str]]:
        """Direct neighbours in both directions. Indexed, not scanned."""
        clause = "AND e.rel_type IN $rels" if rel_types else ""
        params: dict[str, Any] = {"nid": node_id}
        if rel_types:
            params["rels"] = list(rel_types)
        res = self.conn.execute(
            f"MATCH (a:Node)-[e:REL]-(b:Node) WHERE a.id = $nid {clause} "
            "RETURN a.id, e.rel_type, b.id",
            params,
        )
        return [(r[0], r[1], r[2]) for r in res]

    def expand(
        self,
        seeds: Sequence[str],
        *,
        hops: int = 2,
        node_type: str | None = None,
        exclude: Sequence[str] = (),
        limit: int = 50,
    ) -> list[tuple[str, int, int]]:
        """Documents reachable from `seeds`, ranked by how many seeds reach them.

        This is the query the hand-rolled version could not express. Support
        count is the ranking signal that matters: a document connected to five
        of the seeds is far more likely to be on-topic than one connected to a
        single seed through a hub node with thousands of edges -- which is the
        failure shape behind the conflicting_info recall collapse.

        Returns (node_id, support, min_hops).
        """
        if not seeds:
            return []
        exclude_set = set(exclude) | set(seeds)
        type_filter = "AND b.node_type = $ntype" if node_type else ""
        params: dict[str, Any] = {"seeds": list(seeds)}
        if node_type:
            params["ntype"] = node_type

        found: dict[str, tuple[int, int]] = {}
        for hop in range(1, hops + 1):
            res = self.conn.execute(
                f"MATCH (a:Node)-[:REL*1..{hop}]-(b:Node) "
                f"WHERE a.id IN $seeds {type_filter} "
                "RETURN b.id AS bid, count(DISTINCT a.id) AS support",
                params,
            )
            for row in res:
                bid, support = row[0], int(row[1])
                if bid in exclude_set:
                    continue
                prev = found.get(bid)
                # Keep the shortest hop distance and the largest support seen.
                if prev is None:
                    found[bid] = (support, hop)
                else:
                    found[bid] = (max(prev[0], support), min(prev[1], hop))
            if len(found) >= limit * 4:
                break

        ranked = sorted(found.items(), key=lambda kv: (-kv[1][0], kv[1][1], kv[0]))
        return [(nid, s, h) for nid, (s, h) in ranked[:limit]]

    def shared_entity_documents(self, seeds: Sequence[str], *,
                                entity_types: Sequence[str],
                                limit: int = 50) -> list[tuple[str, int]]:
        """Documents sharing an entity of the given type with any seed.

        The canonical `project_related` / `completeness` query: "everything in
        the same project/thread/ticket as what I already found". Dense retrieval
        has no mechanism for this at any corpus size -- similarity ranks, it does
        not enumerate a set.
        """
        if not seeds:
            return []
        res = self.conn.execute(
            "MATCH (a:Node)-[:REL]-(e:Node)-[:REL]-(b:Node) "
            "WHERE a.id IN $seeds AND e.node_type IN $etypes "
            "  AND b.node_type = 'document' AND NOT b.id IN $seeds "
            "RETURN b.id AS bid, count(DISTINCT e.id) AS shared "
            "ORDER BY shared DESC LIMIT $lim",
            {"seeds": list(seeds), "etypes": list(entity_types), "lim": limit},
        )
        return [(r[0], int(r[1])) for r in res]

    def stats(self) -> dict[str, int]:
        n = self.conn.execute("MATCH (n:Node) RETURN count(n)")
        e = self.conn.execute("MATCH ()-[r:REL]->() RETURN count(r)")
        return {"nodes": int(next(iter(n))[0]), "edges": int(next(iter(e))[0])}

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        if self._temp and self._temp_root and self._temp_root.exists():
            shutil.rmtree(self._temp_root, ignore_errors=True)

    def __enter__(self) -> "KuzuGraphStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def build_adjacency(edges: Sequence[tuple[str, str, str, dict]]
                    ) -> dict[str, list[tuple[str, str, str, dict]]]:
    """In-memory adjacency index -- the O(1) stopgap for small worlds.

    Same asymptotics as Kùzu for a single hop without the dependency, but no
    persistence and no query language. Used for demo-scale world models where
    standing up a database is not worth it; anything at corpus scale should use
    KuzuGraphStore.
    """
    adj: dict[str, list[tuple[str, str, str, dict]]] = defaultdict(list)
    for edge in edges:
        adj[edge[0]].append(edge)
        adj[edge[2]].append(edge)
    return dict(adj)
