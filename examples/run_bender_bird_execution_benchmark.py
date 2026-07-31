"""
BIRD Execution Benchmark Runner

Runs end-to-end SQL execution benchmark on BIRD tasks.

This measures execution accuracy (not just grounding accuracy).
Results are comparable to official BIRD leaderboard numbers.

Usage:
    # Run on 100 tasks with Ollama
    PYTHONPATH=src:. python examples/run_bender_bird_execution_benchmark.py \
      --source huggingface \
      --split dev \
      --limit 100 \
      --sql-backend ollama \
      --output benchmarks/bird/execution_100_report.json

    # Run on full dev with heuristic SQL (fast, establishes floor)
    PYTHONPATH=src:. python examples/run_bender_bird_execution_benchmark.py \
      --source huggingface \
      --split dev \
      --sql-backend heuristic \
      --output benchmarks/bird/execution_heuristic_full_dev.json

Architecture:
    1. BENDER grounding (candidate tables, constraints)
    2. SQL generation (LLM or heuristic)
    3. SQLite execution
    4. Result validation

Systems compared:
    - naive_baseline: Heuristic SQL, no BENDER
    - rag_baseline: Full schema, no BENDER filtering
    - bender_grounding: BENDER candidate tables
    - bender_with_evidence: BENDER + task evidence
    - bender_with_repair: Above + multi-candidate repair
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from bender import snapshot_to_world_model
from implementations.bird import (
    BirdBenchmarkAdapter,
    BirdHeuristicSQLCandidateGenerator,
    BirdHFWorkspace,
    BirdOllamaSQLCandidateGenerator,
    BirdSQLiteDatabaseLoader,
    BirdWorkspace,
    enrich_world_with_bird_metadata,
)
from implementations.bird.scalarlm_generator import BirdScalarLMSQLCandidateGenerator
from implementations.bird.claude_generator import BirdClaudeSQLCandidateGenerator
from implementations.bird.execution import (
    BirdExecutionAdapter,
    BirdExecutionBenchmarkRunner,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="BIRD Execution Benchmark")
    parser.add_argument("--source", choices=["local", "huggingface"], default="huggingface")
    parser.add_argument("--bird-root", default="")
    parser.add_argument("--split", default="dev")
    parser.add_argument("--hf-repo-id", default="Sudnya/bird-sql")
    parser.add_argument("--hf-cache-dir", default=".local/bird_hf")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--db", action="append", dest="db_ids")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 = all)")
    parser.add_argument(
        "--sql-backend",
        choices=["heuristic", "ollama", "scalarlm", "claude"],
        default="claude",
        help="SQL generation backend (default: claude for best SQL quality)",
    )
    parser.add_argument("--scalarlm-url", default="http://localhost:8000", help="ScalarLM API URL")
    parser.add_argument("--ollama-base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-model", default="qwen2.5-coder:latest")
    parser.add_argument("--max-candidates", type=int, default=1, help="SQL candidates to generate")
    parser.add_argument("--use-repair", action="store_true", help="Enable multi-candidate repair")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    # Load workspace
    if args.source == "local":
        if not args.bird_root:
            raise SystemExit("--bird-root is required when --source local")
        workspace = BirdWorkspace(args.bird_root)
    else:
        workspace = BirdHFWorkspace(
            repo_id=args.hf_repo_id,
            cache_dir=args.hf_cache_dir,
        )
        workspace.ensure_database_cache(split=args.split, force_download=args.force_download)

    # Load tasks
    tasks = workspace.load_tasks(split=args.split)
    if args.db_ids:
        allowed = set(args.db_ids)
        tasks = [task for task in tasks if task.db_id in allowed]
    if args.limit > 0:
        tasks = tasks[: args.limit]

    print(f"Loaded {len(tasks)} BIRD tasks")

    # Load schemas and databases
    loader = BirdSQLiteDatabaseLoader()
    snapshots = {}
    db_paths = {}
    baseline_worlds = {}
    bender_worlds = {}

    print("Loading database schemas and world models...")
    for db_id in sorted({task.db_id for task in tasks}):
        db_path = workspace.resolve_local_sqlite_db(db_id, split=args.split)
        snapshot = loader.load(db_path, db_id=db_id)
        snapshots[db_id] = snapshot
        db_paths[db_id] = db_path
        baseline_worlds[db_id] = snapshot_to_world_model(snapshot)
        bender_worlds[db_id] = enrich_world_with_bird_metadata(
            snapshot_to_world_model(snapshot),
            db_id=db_id,
            metadata_documents=workspace.load_database_documents(db_id, split=args.split),
        )

    # Create SQL generator
    if args.sql_backend == "claude":
        print("Using Claude 3.5 Sonnet SQL backend")
        sql_generator = BirdClaudeSQLCandidateGenerator(strict=False)
    elif args.sql_backend == "scalarlm":
        print(f"Using ScalarLM SQL backend: {args.scalarlm_url}")
        sql_generator = BirdScalarLMSQLCandidateGenerator(
            base_url=args.scalarlm_url,
            strict=False,
        )
    elif args.sql_backend == "ollama":
        print(f"Using Ollama SQL backend: {args.ollama_model}")
        sql_generator = BirdOllamaSQLCandidateGenerator(
            base_url=args.ollama_base_url,
            model=args.ollama_model,
            strict=False,
        )
    else:
        print("Using heuristic SQL backend")
        sql_generator = BirdHeuristicSQLCandidateGenerator()

    # Create grounding adapters
    naive_grounding = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=None,  # No world model for naive
        top_k=8,
        include_evidence=False,
    )

    rag_grounding = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=baseline_worlds,  # Schema-only world model
        top_k=8,
        include_evidence=False,
    )

    bender_grounding = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=bender_worlds,  # Enriched world model
        top_k=8,
        include_evidence=False,
    )

    evidence_grounding = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=bender_worlds,
        top_k=8,
        include_evidence=True,  # Include task evidence
    )

    # Create execution adapters
    naive_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_generator=sql_generator,
        grounding_adapter=naive_grounding,
        use_repair=False,
        max_candidates=1,
    )

    rag_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_generator=sql_generator,
        grounding_adapter=rag_grounding,
        use_repair=False,
        max_candidates=1,
    )

    bender_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_generator=sql_generator,
        grounding_adapter=bender_grounding,
        use_repair=False,
        max_candidates=1,
    )

    evidence_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_generator=sql_generator,
        grounding_adapter=evidence_grounding,
        use_repair=False,
        max_candidates=1,
    )

    repair_adapter = None
    if args.use_repair:
        repair_adapter = BirdExecutionAdapter(
            snapshots_by_db=snapshots,
            db_paths_by_db=db_paths,
            sql_generator=sql_generator,
            grounding_adapter=evidence_grounding,
            use_repair=True,
            max_candidates=args.max_candidates,
        )

    # Run benchmark
    runner = BirdExecutionBenchmarkRunner(
        naive_adapter=naive_adapter,
        rag_adapter=rag_adapter,
        bender_adapter=bender_adapter,
        evidence_adapter=evidence_adapter,
        repair_adapter=repair_adapter,
    )

    report = runner.run(tasks)

    # Add metadata
    report["metadata"] = {
        "split": args.split,
        "tasks_count": len(tasks),
        "sql_backend": args.sql_backend,
        "max_candidates": args.max_candidates,
        "use_repair": args.use_repair,
    }

    # Save report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Print summary
    print("\n" + "=" * 80)
    print("BIRD EXECUTION BENCHMARK RESULTS")
    print("=" * 80)
    print(f"\nTasks: {len(tasks)}")
    print(f"SQL Backend: {args.sql_backend}")
    print("\nExecution Accuracy (comparable to BIRD leaderboard):\n")

    for summary in report["systems"]:
        system = summary["system"]
        accuracy = summary.get("accuracy", 0.0)
        exec_success = summary.get("metrics", {}).get("avg_execution_success", 0.0)
        print(f"  {system:25s} {accuracy:6.2%}  (exec_success: {exec_success:6.2%})")

    print(f"\nReport saved to: {output_path}")
    print("\nNOTE: These are EXECUTION accuracy numbers, comparable to BIRD leaderboard.")
    print("See grounding report for table recall metrics.")


if __name__ == "__main__":
    main()
