from typing import Any

from .world_state import WorldModel


class Grounder:
    """The Grounder handles dynamic knowledge acquisition for a specific domain.
    It identifies domain meaning, join paths, and semantic roles to build a robust coprocessor."""

    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client

    def ground_world(self, world: WorldModel, schema_context: str, instruction: str) -> None:
        """Enrich world with semantic roles, join logic, and schema isolation."""
        domain = self._identify_domain(schema_context, instruction)
        world.domain = domain

        # 1. Schema Family Isolation (Crucial for Austin/Chicago)
        target_schema_family = self._identify_target_schema(instruction)

        role_map = {
            "ROLE_DURATION": ["seconds", "duration", "minutes", "length", "time_spent"],
            "ROLE_TEMPORAL": ["year", "month", "date", "timestamp", "period", "occurred_at", "start_time"],
            "ROLE_GEOGRAPHIC": ["state", "province", "region", "city", "community", "location", "area", "zip", "postal"],
            "ROLE_METRIC": ["number", "count", "fare", "price", "amount", "total", "value", "quantity"],
            "ROLE_ENTITY_ID": ["id", "uuid", "key", "code", "pk", "fk", "station_id", "bike_id"],
        }

        for node_id, node in world.nodes.items():
            # Apply schema isolation penalty attribute
            if target_schema_family and target_schema_family not in node_id.upper():
                node["relevance_penalty"] = 0.1 # Multiplier for retrieval scores

            if node.get("type") == "table":
                label = node.get("label", "").lower()
                # Table Role Alignment: Identify Fact vs Dimension
                if any(t in label for t in ["trips", "incidents", "requests", "crime", "transactions"]):
                    node["table_role"] = "FACT_TABLE"
                else:
                    node["table_role"] = "DIMENSION_TABLE"
                continue

            if node.get("type") != "column":
                continue

            label = node.get("label", "").lower()

            # Dynamic Role Alignment
            for role, keywords in role_map.items():
                if any(k in label for k in keywords):
                    node["semantic_role"] = role
                    break

            # Type-based Refinement
            if "semantic_role" not in node:
                data_type = node.get("data_type", "").upper()
                if data_type in ["NUMBER", "INTEGER", "FLOAT", "DECIMAL"]:
                    node["semantic_role"] = "ROLE_METRIC"

        # 3. Join-Path Grounding: Identify joinable points
        for node_id, node in world.nodes.items():
            if node.get("semantic_role") == "ROLE_ENTITY_ID" or "id" in node_id.lower():
                node["is_join_key"] = True

    def _identify_target_schema(self, instruction: str) -> str | None:
        lowered = instruction.lower()
        if "bike" in lowered or "station" in lowered:
            return "BIKESHARE"
        if "crime" in lowered:
            return "CRIME"
        if "incident" in lowered or "emergency" in lowered:
            return "INCIDENTS"
        if "311" in lowered or "service request" in lowered:
            return "311"
        return None

    def _identify_domain(self, schema_context: str, instruction: str) -> str:
        lowered = (schema_context + " " + instruction).lower()
        if "taxi" in lowered:
            return "Taxis"
        if "crime" in lowered:
            return "Crime"
        if "bikeshare" in lowered or "station" in lowered:
            return "Bikeshare"
        if "baseball" in lowered:
            return "Baseball"
        return "General"
