from __future__ import annotations

from dataclasses import dataclass

from bender.database import SQLSchemaSnapshot
from bender.integration import BlackBoxIntegration, ModelIntegration
from bender.models import CognitiveState, Hypothesis
from bender.sql_coprocessor import (
    SQLSchemaCoprocessor,
    SQLSchemaPlanner,
    SQLSchemaRuleEngine,
)


class SpiderSchemaPlanner(SQLSchemaPlanner):
    def plan(self, query: str, state: CognitiveState) -> CognitiveState:
        super().plan(query, state)
        state.planner_state["benchmark"] = "spider"
        state.add_provenance(
            "planner",
            "planner:spider_schema",
            "Planner tagged the request as Spider-style schema reasoning.",
        )
        return state


class SpiderSchemaRuleEngine(SQLSchemaRuleEngine):
    def apply(self, state: CognitiveState) -> CognitiveState:
        super().apply(state)
        table_names = state.constraints.get("candidate_tables", [])

        if "actor" in table_names and "film" in table_names:
            state.constraints.setdefault("recommended_bridge_tables", []).append("film_actor")
            state.hypotheses.append(
                Hypothesis(
                    text="Actor and film questions likely require traversing film_actor as the bridge table.",
                    confidence=0.8,
                    evidence=["rule:spider_actor_film_bridge"],
                    kind="bridge_table",
                )
            )
            state.add_provenance(
                "reasoning",
                "rule:spider_actor_film_bridge",
                "Suggested film_actor as the bridge between actor and film entities.",
                confidence=0.8,
            )

        if "category" in table_names and "film" in table_names:
            state.constraints.setdefault("recommended_bridge_tables", []).append("film_category")
            state.hypotheses.append(
                Hypothesis(
                    text="Category filtering on films likely requires joining film_category before category.",
                    confidence=0.79,
                    evidence=["rule:spider_film_category_bridge"],
                    kind="bridge_table",
                )
            )
            state.add_provenance(
                "reasoning",
                "rule:spider_film_category_bridge",
                "Suggested film_category as the bridge for category-based film filtering.",
                confidence=0.79,
            )

        return state


@dataclass
class SpiderSchemaCoprocessor(SQLSchemaCoprocessor):
    @classmethod
    def from_snapshot(
        cls,
        snapshot: SQLSchemaSnapshot,
        *,
        model_name: str = "spider-schema-demo",
        integration: ModelIntegration | None = None,
        top_k: int = 8,
        world_model=None,
    ) -> "SpiderSchemaCoprocessor":
        base = SQLSchemaCoprocessor.from_snapshot(
            snapshot,
            model_name=model_name,
            integration=integration or BlackBoxIntegration(),
            top_k=top_k,
            planner=SpiderSchemaPlanner(snapshot=snapshot),
            rules=SpiderSchemaRuleEngine(),
            world_model=world_model,
        )
        return cls(model=base.model, snapshot=base.snapshot)
