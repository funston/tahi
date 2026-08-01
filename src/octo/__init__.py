from ._version import __version__
from .adapter import wrap_llm
from .benchmarking import (
    BenchmarkCaseResult,
    BenchmarkSystemSummary,
    benchmark_report_to_dict,
    render_markdown_summary_table,
    summarize_system_results,
)
from .compiler.sql import SQLCompilerPipeline
from .database import (
    DatabaseSchemaSnapshot,
    PostgresColumnProfile,
    PostgresForeignKey,
    PostgresSchemaIntrospector,
    PostgresTableProfile,
    SQLColumnProfile,
    SQLForeignKey,
    SQLSchemaIntrospector,
    SQLSchemaSnapshot,
    SQLTableProfile,
    build_pagila_fixture_snapshot,
    format_connection_help,
    snapshot_to_world_model,
    summarize_snapshot,
)
from .evaluation import (
    ComparisonCase,
    comparison_suite_to_dict,
    evaluate_comparison_suite,
)
from .fusion import FusionModule, WeightedBlendFusion
from .integration import (
    BlackBoxIntegration,
    ModelIntegration,
    NativeIntegration,
)
from .runtime import OctoRuntime
from .repair.sql import SQLRepairAttempt, SQLRepairLoop, SQLRepairOutcome
from .schema_compression import (
    SchemaCompressionPlan,
    SchemaFamily,
    SchemaFamilyMember,
    build_schema_compression_plan,
    score_schema_families,
)
# SQL coprocessor moved to implementations/sql/
# from .sql_coprocessor import SQLSchemaCoprocessor, SQLSchemaPlanner, SQLSchemaRuleEngine
from .validators.sql import SQLExecutionEngine, SQLResultMatcher, SQLValidationResult
from .world_state import WorldModel
from .world_model_store import WorldModelStore, WorldModelManifest

__all__ = [
    "OctoRuntime",
    "BenchmarkCaseResult",
    "BenchmarkSystemSummary",
    "BlackBoxIntegration",
    "ComparisonCase",
    "FusionModule",
    "ModelIntegration",
    "NativeIntegration",
    "DatabaseSchemaSnapshot",
    "PostgresColumnProfile",
    "PostgresForeignKey",
    "PostgresSchemaIntrospector",
    "PostgresTableProfile",
    "SQLColumnProfile",
    "SQLCompilerPipeline",
    "SQLExecutionEngine",
    "SQLForeignKey",
    "SQLRepairAttempt",
    "SQLRepairLoop",
    "SQLRepairOutcome",
    "SQLSchemaIntrospector",
    "SQLSchemaSnapshot",
    "SQLTableProfile",
    "SQLResultMatcher",
    "SQLValidationResult",
    "SchemaCompressionPlan",
    "SchemaFamily",
    "SchemaFamilyMember",
    "build_schema_compression_plan",
    "score_schema_families",
    "WeightedBlendFusion",
    "WorldModel",
    "WorldModelManifest",
    "WorldModelStore",
    "__version__",
    "benchmark_report_to_dict",
    "build_pagila_fixture_snapshot",
    "comparison_suite_to_dict",
    "evaluate_comparison_suite",
    "format_connection_help",
    "render_markdown_summary_table",
    "summarize_system_results",
    "snapshot_to_world_model",
    "summarize_snapshot",
    "wrap_llm",
]
