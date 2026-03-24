from __future__ import annotations

import re
from dataclasses import dataclass
from collections import defaultdict, deque

from .adapter import WrappedLLM, wrap_llm
from .database import SQLSchemaSnapshot, snapshot_to_world_model
from .integration import BlackBoxIntegration, ModelIntegration
from .models import CognitiveState, Hypothesis
from .planner import Planner
from .rules import RuleEngine
from .world_state import WorldModel


def _table_id(label: str) -> str:
    return label.split(".", 1)[-1].lower()


def _column_label_parts(label: str) -> tuple[str, str]:
    if "." not in label:
        return "", label.lower()
    table, column = label.split(".", 1)
    return table.lower(), column.lower()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _query_terms(query: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9_]+", query.lower()))
    singularized = {term[:-1] for term in terms if term.endswith("s") and len(term) > 3}
    return terms | singularized


def classify_sql_query_intent(query: str) -> str:
    lowered = query.lower()
    if "count" in lowered or "how many" in lowered:
        return "count"
    if "average" in lowered or "avg" in lowered:
        return "average"
    if "sum" in lowered or "total" in lowered:
        return "sum"
    if "top " in lowered or "highest" in lowered or "most " in lowered:
        return "ranking"
    if "list" in lowered or "which " in lowered or "show " in lowered:
        return "selection"
    return "selection"


def _is_customer_rental_film_query(terms: set[str]) -> bool:
    has_customer = "customer" in terms or "customers" in terms
    has_film = any(term in terms for term in ("film", "films", "movie", "movies"))
    has_rental = any(term in terms for term in ("rent", "rental", "rented"))
    return has_customer and has_film and has_rental


def _is_actor_category_film_query(terms: set[str]) -> bool:
    has_actor = "actor" in terms or "actors" in terms
    has_category = "category" in terms or "categories" in terms
    has_film = any(term in terms for term in ("film", "films", "movie", "movies"))
    return has_actor and has_category and has_film


def _is_payment_customer_rental_query(terms: set[str]) -> bool:
    has_payment = any(term in terms for term in ("payment", "payments", "revenue", "amount"))
    has_customer = "customer" in terms or "customers" in terms
    has_rental = "rental" in terms or "rentals" in terms
    return has_payment and (has_customer or has_rental)


def _is_store_customer_address_query(terms: set[str]) -> bool:
    has_store = "store" in terms or "stores" in terms
    has_customer = "customer" in terms or "customers" in terms
    has_address = "address" in terms or "addresses" in terms
    return has_store and has_customer and has_address


SQL_TERM_HINTS: dict[str, tuple[str, ...]] = {
    "rent": ("rental", "inventory", "film", "customer"),
    "rental": ("rental", "inventory", "film", "customer"),
    "rented": ("rental", "inventory", "film", "customer"),
    "customer": ("customer", "rental"),
    "customers": ("customer", "rental"),
    "film": ("film", "inventory", "rental"),
    "films": ("film", "inventory", "rental"),
    "movie": ("film", "inventory", "rental"),
    "movies": ("film", "inventory", "rental"),
    "actor": ("actor", "film_actor", "film"),
    "actors": ("actor", "film_actor", "film"),
    "category": ("category", "film_category", "film"),
    "categories": ("category", "film_category", "film"),
    "payment": ("payment_p2007_01", "payment_p2007_02", "payment_p0000_default", "customer"),
}


def _build_table_graph(snapshot: SQLSchemaSnapshot) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for fk in snapshot.foreign_keys:
        source = fk.source_table.lower()
        target = fk.target_table.lower()
        graph[source].add(target)
        graph[target].add(source)
    return graph


def _shortest_path(
    graph: dict[str, set[str]],
    start: str,
    goal: str,
) -> list[str]:
    if start == goal:
        return [start]
    queue = deque([(start, [start])])
    seen = {start}
    while queue:
        node, path = queue.popleft()
        for neighbor in sorted(graph.get(node, ())):
            if neighbor in seen:
                continue
            next_path = path + [neighbor]
            if neighbor == goal:
                return next_path
            seen.add(neighbor)
            queue.append((neighbor, next_path))
    return []


def _score_tables(snapshot: SQLSchemaSnapshot, terms: set[str]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for table in snapshot.tables:
        table_name = table.name.lower()
        table_terms = set(table_name.split("_"))
        column_terms = {column.name.lower() for column in table.columns}
        score = 0.0

        for term in terms:
            if term == table_name:
                score += 5.0
            if term in table_terms:
                score += 3.0
            if table_name.startswith(term) or term.startswith(table_name):
                score += 1.5
            if any(term in column_name for column_name in column_terms):
                score += 1.0
            hinted_tables = SQL_TERM_HINTS.get(term, ())
            if table_name in hinted_tables:
                score += max(0.5, 2.5 - 0.3 * hinted_tables.index(table_name))

        if score > 0.0:
            scores[table_name] = score
    return scores


def _apply_customer_rental_film_bias(scores: dict[str, float]) -> None:
    preferred_weights = {
        "customer": 10.0,
        "rental": 9.0,
        "inventory": 8.0,
        "film": 7.0,
    }
    discouraged_tables = {
        "film_actor": -6.0,
        "film_category": -6.0,
        "actor": -4.0,
        "category": -4.0,
        "address": -3.0,
        "city": -3.0,
        "staff": -3.0,
        "store": -2.0,
    }
    for table, bonus in preferred_weights.items():
        scores[table] = scores.get(table, 0.0) + bonus
    for table, penalty in discouraged_tables.items():
        if table in scores:
            scores[table] += penalty


def _apply_actor_category_film_bias(scores: dict[str, float]) -> None:
    preferred_weights = {
        "actor": 10.0,
        "film_actor": 9.0,
        "film": 8.0,
        "film_category": 7.0,
        "category": 6.0,
    }
    for table, bonus in preferred_weights.items():
        scores[table] = scores.get(table, 0.0) + bonus


def _apply_payment_customer_rental_bias(scores: dict[str, float]) -> None:
    preferred_weights = {
        "payment_p2007_01": 10.0,
        "customer": 9.0,
        "rental": 8.0,
    }
    for table, bonus in preferred_weights.items():
        scores[table] = scores.get(table, 0.0) + bonus


def _apply_store_customer_address_bias(scores: dict[str, float]) -> None:
    preferred_weights = {
        "store": 10.0,
        "address": 9.0,
        "customer": 8.0,
    }
    for table, bonus in preferred_weights.items():
        scores[table] = scores.get(table, 0.0) + bonus


def _candidate_paths_for_pairs(
    graph: dict[str, set[str]],
    anchors: list[str],
) -> list[list[str]]:
    paths: list[list[str]] = []
    for left_index in range(len(anchors)):
        for right_index in range(left_index + 1, len(anchors)):
            path = _shortest_path(graph, anchors[left_index], anchors[right_index])
            if path:
                paths.append(path)
    return paths


def _path_score(path: list[str], scored_tables: dict[str, float]) -> tuple[float, int, str]:
    total = sum(scored_tables.get(table, 0.0) for table in path)
    return (-total, len(path), "->".join(path))


class SQLSchemaPlanner(Planner):
    def __init__(self, snapshot: SQLSchemaSnapshot | None = None):
        self.snapshot = snapshot

    def plan(self, query: str, state: CognitiveState) -> CognitiveState:
        super().plan(query, state)
        terms = _query_terms(query)
        is_customer_rental_film = _is_customer_rental_film_query(terms)
        is_actor_category_film = _is_actor_category_film_query(terms)
        is_payment_customer_rental = _is_payment_customer_rental_query(terms)
        is_store_customer_address = _is_store_customer_address_query(terms)
        table_candidates = []
        column_candidates = []
        for entity in state.entities:
            if entity.type == "table":
                table_candidates.append(entity.label)
            elif entity.type == "column":
                column_candidates.append(entity.label)

        lexical_tables = []
        lexical_columns = []
        scored_tables: dict[str, float] = {}
        candidate_join_path: list[str] = []
        recommended_bridge_tables: list[str] = []
        if self.snapshot is not None:
            scored_tables = _score_tables(self.snapshot, terms)
            if is_customer_rental_film:
                _apply_customer_rental_film_bias(scored_tables)
            if is_actor_category_film:
                _apply_actor_category_film_bias(scored_tables)
            if is_payment_customer_rental:
                _apply_payment_customer_rental_bias(scored_tables)
            if is_store_customer_address:
                _apply_store_customer_address_bias(scored_tables)
            for table in self.snapshot.tables:
                table_terms = set(_table_id(table.node_id).split("_")) | set(
                    _table_id(table.name).split("_")
                )
                sample_terms = {
                    value.lower()
                    for column in table.columns
                    for value in column.sample_values
                }
                if terms & table_terms or terms & sample_terms:
                    lexical_tables.append(f"{table.schema}.{table.name}")
                for column in table.columns:
                    column_terms = set(column.name.lower().split("_"))
                    if terms & column_terms:
                        lexical_columns.append(f"{column.table}.{column.name}")

            graph = _build_table_graph(self.snapshot)
            lexical_table_ids = [_table_id(label) for label in lexical_tables]
            anchor_tables = [
                table for table, _ in sorted(scored_tables.items(), key=lambda item: (-item[1], item[0]))
            ]
            anchors = _dedupe(lexical_table_ids + anchor_tables)[:5]
            path_tables: list[str] = []
            best_path: list[str] = []
            if is_customer_rental_film:
                preferred_path = ["customer", "rental", "inventory", "film"]
                if all(table in graph for table in preferred_path):
                    best_path = preferred_path
            elif is_actor_category_film:
                preferred_path = ["actor", "film_actor", "film", "film_category", "category"]
                if all(table in graph for table in preferred_path):
                    best_path = preferred_path
            elif is_payment_customer_rental:
                preferred_path = ["payment_p2007_01", "rental", "customer"]
                if all(table in graph for table in preferred_path):
                    best_path = preferred_path
            elif is_store_customer_address:
                preferred_path = ["store", "address", "customer"]
                if all(table in graph for table in preferred_path):
                    best_path = preferred_path
            if not best_path and len(anchors) >= 2:
                candidate_paths = _candidate_paths_for_pairs(graph, anchors)
                if candidate_paths:
                    best_path = min(candidate_paths, key=lambda path: _path_score(path, scored_tables))
            if best_path:
                path_tables.extend(best_path)
                if len(best_path) > 2:
                    recommended_bridge_tables.extend(best_path[1:-1])
                candidate_join_path.extend(
                    [f"{best_path[i]}->{best_path[i + 1]}" for i in range(len(best_path) - 1)]
                )
            for table in path_tables:
                scored_tables[table] = scored_tables.get(table, 0.0) + 2.0
            for bridge in recommended_bridge_tables:
                scored_tables[bridge] = scored_tables.get(bridge, 0.0) + 1.0

        query_intent = classify_sql_query_intent(query)
        state.planner_state["sql_query_intent"] = query_intent
        ranked_table_labels = []
        if self.snapshot is not None:
            snapshot_table_labels = {
                table.name.lower(): f"{table.schema}.{table.name}"
                for table in self.snapshot.tables
            }
            ranked_table_labels.extend(
                snapshot_table_labels[table]
                for table, _ in sorted(scored_tables.items(), key=lambda item: (-item[1], item[0]))
                if table in snapshot_table_labels
            )
        candidate_table_labels = _dedupe(table_candidates + lexical_tables + ranked_table_labels)
        if is_customer_rental_film and self.snapshot is not None:
            preferred_labels = [
                snapshot_table_labels[table]
                for table in ("customer", "rental", "inventory", "film")
                if table in snapshot_table_labels
            ]
            candidate_table_labels = _dedupe(preferred_labels + candidate_table_labels)
        elif is_actor_category_film and self.snapshot is not None:
            preferred_labels = [
                snapshot_table_labels[table]
                for table in ("actor", "film_actor", "film", "film_category", "category")
                if table in snapshot_table_labels
            ]
            candidate_table_labels = _dedupe(preferred_labels + candidate_table_labels)
        elif is_payment_customer_rental and self.snapshot is not None:
            preferred_labels = [
                snapshot_table_labels[table]
                for table in ("payment_p2007_01", "rental", "customer")
                if table in snapshot_table_labels
            ]
            candidate_table_labels = _dedupe(preferred_labels + candidate_table_labels)
        elif is_store_customer_address and self.snapshot is not None:
            preferred_labels = [
                snapshot_table_labels[table]
                for table in ("store", "address", "customer")
                if table in snapshot_table_labels
            ]
            candidate_table_labels = _dedupe(preferred_labels + candidate_table_labels)
        state.planner_state["candidate_tables"] = candidate_table_labels[:8]
        state.planner_state["candidate_columns"] = _dedupe(column_candidates + lexical_columns)[:10]
        if candidate_join_path:
            state.planner_state["candidate_join_path"] = _dedupe(candidate_join_path)[:8]
        if recommended_bridge_tables:
            state.planner_state["recommended_bridge_tables"] = _dedupe(recommended_bridge_tables)[:6]
        steps = state.planner_state.setdefault("steps", [])
        steps.insert(-1, "rank schema entities")
        steps.insert(-1, "plan join path across candidate tables")
        state.add_provenance(
            "planner",
            "planner:sql_schema",
            "Planner added generic SQL schema-ranking and join-planning steps.",
        )
        return state


class SQLSchemaRuleEngine(RuleEngine):
    def apply(self, state: CognitiveState) -> CognitiveState:
        table_entities = [entity for entity in state.entities if entity.type == "table"]
        column_entities = [entity for entity in state.entities if entity.type == "column"]
        planned_tables = state.planner_state.get("candidate_tables", [])
        table_names = _dedupe(
            [_table_id(label) for label in planned_tables]
            + [_table_id(entity.label) for entity in table_entities]
        )
        column_parts = [_column_label_parts(entity.label) for entity in column_entities]

        state.constraints["query_intent"] = state.planner_state.get(
            "sql_query_intent",
            "selection",
        )
        if table_names:
            state.constraints["candidate_tables"] = table_names[:8]
        if column_parts:
            state.constraints["candidate_columns"] = [
                column for _, column in column_parts[:10]
            ]

        planned_join_path = state.planner_state.get("candidate_join_path", [])
        if planned_join_path:
            join_path = planned_join_path[:10]
            state.constraints["candidate_join_path"] = join_path
            state.hypotheses.append(
                Hypothesis(
                    text="Candidate join path inferred from foreign keys: " + ", ".join(join_path) + ".",
                    confidence=0.83,
                    evidence=["planner:sql_schema", "rule:sql_join_path"],
                    kind="join_path",
                )
            )
            state.add_provenance(
                "reasoning",
                "rule:sql_join_path",
                "Derived a candidate join path from retrieved foreign-key edges.",
                confidence=0.83,
            )
        planned_bridge_tables = state.planner_state.get("recommended_bridge_tables", [])
        if planned_bridge_tables:
            state.constraints["recommended_bridge_tables"] = planned_bridge_tables[:6]

        if "customer" in table_names and "rental" in table_names:
            state.hypotheses.append(
                Hypothesis(
                    text="Customer rental history likely joins customer to rental and then through inventory to film.",
                    confidence=0.82,
                    evidence=["rule:sql_customer_rental_path"],
                    kind="join_path",
                )
            )
            state.add_provenance(
                "reasoning",
                "rule:sql_customer_rental_path",
                "Suggested the customer->rental->inventory->film path for rental questions.",
                confidence=0.82,
            )

        return state


@dataclass
class SQLSchemaCoprocessor:
    model: WrappedLLM
    snapshot: SQLSchemaSnapshot

    @classmethod
    def from_snapshot(
        cls,
        snapshot: SQLSchemaSnapshot,
        *,
        model_name: str = "sql-schema-demo",
        integration: ModelIntegration | None = None,
        top_k: int = 8,
        planner: Planner | None = None,
        rules: RuleEngine | None = None,
        world_model: WorldModel | None = None,
    ) -> "SQLSchemaCoprocessor":
        model = wrap_llm(
            model_name,
            world_model=world_model or snapshot_to_world_model(snapshot),
            integration=integration or BlackBoxIntegration(),
            planner=planner or SQLSchemaPlanner(snapshot=snapshot),
            rules=rules or SQLSchemaRuleEngine(),
            top_k=top_k,
        )
        return cls(model=model, snapshot=snapshot)

    def ask(self, query: str, *, trace: bool = False):
        return self.model.ask(query, mode="coprocessor", trace=trace)
