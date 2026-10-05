import re

from .models import CognitiveState


class Planner:
    def plan(self, query: str, state: CognitiveState) -> CognitiveState:
        lowered = query.lower()

        # 1. Analytic Planning: Decompose into logical solving steps
        analytic_plan = []

        # Concept Resolution
        analytic_plan.append({"action": "resolve_concept", "concept": "primary_subject"})

        # Pattern Application
        if any(token in lowered for token in ("quantile", "equal groups", "decile")):
            state.constraints["query_intent"] = "window_quantile"
            analytic_plan.append({"action": "apply_pattern", "pattern": "pattern:window_quantile"})

        elif any(token in lowered for token in ("consecutive", "increase in", "growth")):
            state.constraints["query_intent"] = "growth_analysis"
            analytic_plan.append({"action": "apply_pattern", "pattern": "self_join_on_temporal"})

        elif any(token in lowered for token in ("proportion", "share", "ratio")):
            state.constraints["query_intent"] = "share_of_total"
            analytic_plan.append({"action": "apply_pattern", "pattern": "pattern:share_of_total"})

        # Data Profiling Requirements
        analytic_plan.append({"action": "validate_schema", "requirement": "column_types"})

        state.planner_state["analytic_plan"] = analytic_plan

        # (Rest of previous plan logic ...)
        # 1. Identify Domain/DB ID
        db_id = None
        for item in state.retrievals:
            node_id = item.node_id
            if ":" in node_id:
                # Handle prefixes like 'table:' or 'column:'
                parts = node_id.split(":")
                payload = parts[-1]
                if "." in payload:
                    db_id = payload.split(".")[0]
                    break
            elif "." in node_id:
                db_id = node_id.split(".")[0]
                break

        if db_id:
            state.constraints["db_id"] = db_id.upper()

        # 2. Identify Semantic Frame Requirements (High Priority first)
        if any(token in lowered for token in ("quantile", "equal groups", "decile")):
            state.constraints["query_intent"] = "window_quantile"
            state.constraints["window_function"] = "NTILE"

        elif any(token in lowered for token in ("consecutive", "increase in", "growth")):
            state.constraints["query_intent"] = "growth_analysis"
            state.constraints["sql_pattern"] = "self_join_on_month"

        elif any(token in lowered for token in ("proportion", "share", "ratio")):
            state.constraints["query_intent"] = "share_of_total"
            state.constraints["requires_global_denominator"] = True

        elif any(token in lowered for token in ("top ", "highest", "largest", "most", "best")):
            state.constraints["query_intent"] = "ranking"

        elif any(token in lowered for token in ("count", "how many")):
            state.constraints["query_intent"] = "count"

        elif any(token in lowered for token in ("average", "mean")):
            state.constraints["query_intent"] = "average"

        elif any(token in lowered for token in ("sum", "total")):
            state.constraints["query_intent"] = "sum"
        else:
            state.constraints["query_intent"] = "selection"

        # 3. Constraint Extraction
        if "each" in lowered or "per " in lowered or "by " in lowered:
            state.constraints["group_by_hint"] = True

        if "year" in lowered or "202" in lowered or "19" in lowered:
            state.constraints["temporal_filter"] = True

        # Detect numeric ranges (e.g. between 0 and 60 minutes)
        range_match = re.search(r"between\s+(\d+)\s+and\s+(\d+)", lowered)
        if range_match:
            state.constraints["numeric_range"] = (int(range_match.group(1)), int(range_match.group(2)))
            analytic_plan.append({"action": "apply_filter", "filter": "numeric_range"})
        steps = [
            "capture semantic frame",
            f"retrieve {db_id or 'domain'} world-model neighborhood",
            "apply deterministic reasoning",
        ]

        if state.constraints.get("requires_global_denominator"):
            steps.append("plan proportion join path")

        if "ranking" in state.constraints.get("query_intent", ""):
            steps.append("rank schema entities")

        state.planner_state["steps"] = steps
        state.add_provenance("planner", "planner:spider_schema", "Planner tagged the request as Spider-style schema reasoning.")
        return state
