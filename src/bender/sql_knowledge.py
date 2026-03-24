from typing import List, Dict, Any, Optional
from .world_state import WorldModel
from .models import RetrievedMemory

class SQLKnowledgeModel(WorldModel):
    """A specialized World Model for SQL Syntax, Dialects, and Solving Patterns.
    This acts as the 'How' coprocessor, storing the collective knowledge of SQL solving."""
    
    def __init__(self, dialect: str = "snowflake"):
        super().__init__(domain=f"SQL-{dialect}")
        self.dialect = dialect
        self._bootstrap_knowledge()

    def _bootstrap_knowledge(self):
        """Seed the model with proven SQL solving trajectories (Analytic Patterns)."""
        
        # 1. Analytic Pattern: Proportions/Shares (The USA_NAMES solution)
        self.upsert_node(
            "pattern:share_of_total",
            label="Share of Total Query",
            summary="To calculate a share/proportion, use a JOIN between a scoped CTE and a global CTE.",
            template="""
            WITH scoped AS (SELECT {group}, SUM({metric}) as s FROM {table} WHERE {filters} GROUP BY 1),
                 totals AS (SELECT {group}, SUM({metric}) as t FROM {table} GROUP BY 1)
            SELECT s.{group} FROM scoped s JOIN totals t ON s.{group} = t.{group} ORDER BY (s.s / NULLIF(t.t, 0)) DESC
            """,
            data_type="analytic_pattern"
        )

        # 2. Analytic Pattern: Quantiles (The CHICAGO solution)
        self.upsert_node(
            "pattern:window_quantile",
            label="Quantile Analysis",
            summary="Use NTILE(N) OVER (ORDER BY metric) to divide data into equal groups.",
            template="SELECT NTILE({buckets}) OVER (ORDER BY {metric}) as quantile FROM {table}",
            data_type="analytic_pattern"
        )

        # 3. Dialect Knowledge: Snowflake Specifics
        self.upsert_node(
            "dialect:snowflake_casting",
            label="Snowflake Type Casting",
            summary="Numeric columns used in DATE_TRUNC or string functions must be explicitly cast.",
            fix="TO_TIMESTAMP({col}) or {col}::string",
            data_type="syntax_rule"
        )
        
        # 4. Domain-Specific SQL Knowledge: CHICAGO TAXI
        self.upsert_node(
            "dialect:chicago_timestamp",
            label="Chicago Timestamp Logic",
            summary="In CHICAGO_TAXI_TRIPS, timestamps are in microseconds. Divide by 1000000 to get seconds.",
            fix="TO_TIMESTAMP({col} / 1000000)",
            data_type="syntax_rule"
        )
        
        # 5. Enhanced Pattern Guidance: Quantile Filter
        self.upsert_node(
            "pattern:quantile_filter",
            label="Quantile with Filter",
            summary="Always apply duration filters (e.g., between 0 and 60 mins) BEFORE NTILE to ensure accurate buckets.",
            fix="WITH filtered AS (SELECT * FROM t WHERE val BETWEEN x AND y), q AS (SELECT NTILE(6) OVER (...) FROM filtered)",
            data_type="analytic_pattern"
        )

    def get_solving_guidance(self, intent: str) -> List[RetrievedMemory]:
        """Retrieve relevant syntax guidance and analytic patterns."""
        return self.retrieve(intent, top_k=3)
