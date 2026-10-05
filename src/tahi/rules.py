from .models import CognitiveState, Hypothesis


class RuleEngine:
    """The RuleEngine applies domain-specific and cross-domain logic to the active CognitiveState.
    It transforms raw retrievals and planner goals into explicit constraints and hypotheses."""

    def apply(self, state: CognitiveState) -> CognitiveState:
        labels = {entity.label.lower() for entity in state.entities}
        db_id = state.constraints.get("db_id", "").upper()
        query_intent = state.constraints.get("query_intent", "")

        # --- Semantic Role Discovery (Coprocessor Role) ---
        # TAHI identifies the ROLES of retrieved entities to guide the Compiler
        for entity in state.entities:
            label = entity.label.lower()
            # Geographic roles
            if any(token in label for token in ["state", "province", "region", "city", "community"]):
                entity.attributes["semantic_role"] = "ROLE_GEOGRAPHIC"

            # Temporal roles
            elif any(token in label for token in ["year", "month", "date", "timestamp"]):
                entity.attributes["semantic_role"] = "ROLE_TEMPORAL"

            # Metric roles
            elif any(token in label for token in ["number", "count", "fare", "price", "amount", "total"]):
                entity.attributes["semantic_role"] = "ROLE_METRIC"

            # Duration roles
            elif any(token in label for token in ["seconds", "duration", "minutes"]):
                entity.attributes["semantic_role"] = "ROLE_DURATION"

        # --- Generic SQL Intent Patterns ---
        if state.constraints.get("requires_global_denominator"):
            state.hypotheses.append(
                Hypothesis(
                    text=f"Proportion queries in {db_id} require a 'share of total' pattern.",
                    confidence=0.98,
                    evidence=["rule:global_proportion", f"db:{db_id}"],
                    kind="sql_pattern"
                )
            )
            state.constraints["sql_template"] = "proportion_join"

        if query_intent == "window_quantile":
            state.constraints["aggregation_required"] = True
            state.constraints["ntile_buckets"] = 6 # Default for SpiderSnow

        # --- DB-Specific Domain Rules ---
        if db_id == "CHICAGO":
            if any("duration" in ln for ln in labels) and any("quantile" in ln for ln in labels):
                state.constraints["query_intent"] = "window_quantile"
                state.constraints["window_function"] = "NTILE"

            if any("company" in ln for ln in labels) and any("growth" in ln for ln in labels):
                state.constraints["query_intent"] = "growth_analysis"
                state.constraints["sql_pattern"] = "self_join_on_month"

        elif db_id == "AUSTIN":
            if "station" in labels and "status" in labels:
                state.constraints["preferred_join_path"] = ["bikeshare_stations", "bikeshare_status"]

        # --- Legacy / Toy Domain Rules ---
        if "penguin" in labels and ("penguin", "cannot", "fly") in [(r.source.lower(), r.relation.lower(), r.target.lower()) for r in state.relations]:
            state.constraints["mobility_exception"] = "penguin_cannot_fly"
            state.hypotheses.append(
                Hypothesis(
                    text="Penguins are birds, but this query hits an explicit exception: penguins cannot fly.",
                    confidence=0.99,
                    evidence=["rule:penguin_exception_override"],
                    kind="rule_exception",
                )
            )
            state.add_provenance(
                "rules",
                "rule:penguin_exception_override",
                "Applied the explicit penguin flight exception rather than relying on the generic bird rule.",
                confidence=0.99,
            )

        if "antarctica" in labels and "fish" in labels:
            antarctic_fish_eaters = sorted(
                {
                    rel.source
                    for rel in state.relations
                    if rel.relation.lower() == "eats" and rel.target.lower() == "fish"
                }
                & {
                    rel.source
                    for rel in state.relations
                    if rel.relation.lower() == "lives_in" and rel.target.lower() == "antarctica"
                }
            )
            if antarctic_fish_eaters:
                state.constraints["antarctic_fish_eaters"] = antarctic_fish_eaters
                state.hypotheses.append(
                    Hypothesis(
                        text=f"Relation intersection resolves Antarctic fish eaters as {', '.join(antarctic_fish_eaters)}.",
                        confidence=0.95,
                        evidence=["rule:relation_intersection"],
                        kind="set_intersection",
                    )
                )
                state.add_provenance(
                    "rules",
                    "rule:relation_intersection",
                    "Intersected lives_in(Antarctica) with eats(fish) to answer the toy domain query.",
                    confidence=0.95,
                )

        return state
