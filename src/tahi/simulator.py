from .models import CognitiveState


class Simulator:
    """The Simulator performs lightweight 'mental simulation' to test hypotheses or predict outcomes.
    For SQL tasks, it simulates the validity of the planned query structure against the retrieved schema."""

    def run(self, state: CognitiveState) -> CognitiveState:
        if not state.retrievals:
            state.simulation_state["status"] = "skipped"
            state.simulation_state["reason"] = "no_retrievals"
            return state

        simulation_checks = []
        confidence_score = 1.0

        # 1. Simulate Join Path Validity
        if state.constraints.get("sql_pattern") == "self_join_on_month":
            # Simulate if we have a month/date column to join on
            has_date = any("month" in item.label.lower() or "date" in item.label.lower() for item in state.retrievals)
            if not has_date:
                simulation_checks.append("Self-join on month proposed but no date column found in retrievals.")
                confidence_score *= 0.5
            else:
                simulation_checks.append("Self-join on month appears structurally valid.")

        # 2. Simulate Proportional Join Integrity
        if state.constraints.get("sql_template") == "proportion_join":
            # Check if we have both the metric (number) and the grouping key (name)
            has_metric = any("number" in item.label.lower() or "count" in item.label.lower() for item in state.retrievals)
            has_key = any("name" in item.label.lower() for item in state.retrievals)
            if not (has_metric and has_key):
                simulation_checks.append("Proportion join requested but missing metric or grouping key.")
                confidence_score *= 0.4
            else:
                simulation_checks.append("Proportion join schema alignment confirmed.")

        # 3. Simulate Aggregation Requirements
        if state.constraints.get("aggregation_required"):
            # Check if we have at least one numeric column for aggregation
            has_numeric = any(item.attributes.get("data_type", "").upper() in ["NUMBER", "INTEGER", "FLOAT"] for item in state.retrievals)
            if not has_numeric:
                # If no numeric columns found, check if labels suggest them
                has_numeric = any("number" in item.label.lower() or "value" in item.label.lower() for item in state.retrievals)

            if not has_numeric:
                simulation_checks.append("Query requires aggregation but no numeric columns identified.")
                confidence_score *= 0.7
            else:
                simulation_checks.append("Aggregation target confirmed.")

        state.simulation_state["status"] = "completed"
        state.simulation_state["checks"] = simulation_checks
        state.simulation_state["structural_confidence"] = round(confidence_score, 3)
        state.add_provenance(
            "simulation",
            "sim:structural_validator",
            f"Simulated query structure against retrieved schema. Confidence: {confidence_score}",
            confidence=confidence_score,
        )
        return state
