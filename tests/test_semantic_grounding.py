"""
Demonstrable Integration Test: Semantic Grounding & Rule Enforcement Engine.

Verifies that:
1. Grounder assigns semantic roles and schema isolation penalties to WorldModel nodes.
2. RuleEngine applies domain rules and hypotheses to CognitiveState.
3. Unsubstantiated or schema-violating candidates receive relevance penalties during retrieval.
"""

import unittest

from tahi.grounding import Grounder
from tahi.models import CognitiveState, EntityRef
from tahi.rules import RuleEngine
from tahi.world_state import WorldModel


class TestSemanticGrounding(unittest.TestCase):
    def setUp(self):
        self.grounder = Grounder()
        self.rule_engine = RuleEngine()

    def test_grounder_role_and_penalty_assignment(self):
        wm = WorldModel(domain="general")
        wm.upsert_node("bikeshare_trips", type="table", label="Bikeshare Trips")
        wm.upsert_node("crime_incidents", type="table", label="Crime Incidents")
        wm.upsert_node("trip_duration", type="column", label="duration")

        # Ground world with BIKESHARE instruction
        self.grounder.ground_world(wm, schema_context="Bikeshare DB", instruction="Count bikeshare trips and duration")

        # Crime table should receive schema isolation penalty
        self.assertEqual(wm.nodes["bikeshare_trips"].get("table_role"), "FACT_TABLE")
        self.assertEqual(wm.nodes["crime_incidents"].get("relevance_penalty"), 0.1)

        # Duration column should be assigned ROLE_DURATION
        self.assertEqual(wm.nodes["trip_duration"].get("semantic_role"), "ROLE_DURATION")

    def test_rule_engine_hypothesis_and_constraint_application(self):
        state = CognitiveState()
        state.entities.append(EntityRef(id="duration", label="duration", type="column"))
        state.entities.append(EntityRef(id="quantile", label="quantile", type="column"))
        state.constraints["db_id"] = "CHICAGO"

        state = self.rule_engine.apply(state)

        # Verify semantic roles populated
        self.assertEqual(state.entities[0].attributes.get("semantic_role"), "ROLE_DURATION")

        # Verify DB specific constraints applied
        self.assertEqual(state.constraints.get("query_intent"), "window_quantile")
        self.assertEqual(state.constraints.get("window_function"), "NTILE")


if __name__ == "__main__":
    unittest.main()
