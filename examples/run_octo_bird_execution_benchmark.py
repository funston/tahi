"""
BIRD Execution Benchmark Runner

Runs end-to-end SQL execution benchmark on BIRD tasks.

This measures execution accuracy (not just grounding accuracy).
Results are comparable to official BIRD leaderboard numbers.

Usage:
    # Run on 100 tasks with Ollama
    PYTHONPATH=src:. python examples/run_octo_bird_execution_benchmark.py \
      --source huggingface \
      --split dev \
      --limit 100 \
      --sql-backend ollama \
      --output benchmarks/bird/execution_100_report.json

    # Run on full dev with heuristic SQL (fast, establishes floor)
    PYTHONPATH=src:. python examples/run_octo_bird_execution_benchmark.py \
      --source huggingface \
      --split dev \
      --sql-backend heuristic \
      --output benchmarks/bird/execution_heuristic_full_dev.json

Architecture:
    1. OCTO grounding (candidate tables, constraints)
    2. SQL generation via one or more coprocessors (LLM or heuristic)
    3. SQLite execution
    4. Result validation

Systems compared:
    - naive_baseline: Heuristic SQL, no OCTO
    - rag_baseline: Full schema, no OCTO grounding
    - octo_grounding: OCTO candidate tables
    - octo_with_evidence: OCTO + task evidence
    - octo_with_repair: Above + multi-candidate repair
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

from octo import snapshot_to_world_model
from implementations.bird import (
    BirdBenchmarkAdapter,
    BirdExecutionAdapter,
    BirdExecutionBenchmarkRunner,
    BirdHFWorkspace,
    BirdSQLiteDatabaseLoader,
    BirdWorkspace,
    ClaudeSQLGeneratorCoprocessor,
    HeuristicSQLGeneratorCoprocessor,
    OllamaSQLGeneratorCoprocessor,
    TrainedSQLGeneratorCoprocessor,
    enrich_world_with_bird_metadata,
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
        choices=["heuristic", "ollama", "claude", "trained"],
        default="claude",
        help="SQL generation backend (default: claude for best SQL quality)",
    )
    parser.add_argument("--claude-model", default="claude-3-5-sonnet-20241022", help="Anthropic model for claude backend")
    parser.add_argument("--trained-model-path", default="", help="Path to local trained SQL coprocessor model (required when --sql-backend trained)")
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
    octo_worlds = {}

    print("Loading database schemas and world models...")
    for db_id in sorted({task.db_id for task in tasks}):
        db_path = workspace.resolve_local_sqlite_db(db_id, split=args.split)
        snapshot = loader.load(db_path, db_id=db_id)
        snapshots[db_id] = snapshot
        db_paths[db_id] = db_path
        baseline_worlds[db_id] = snapshot_to_world_model(snapshot)
        octo_worlds[db_id] = enrich_world_with_bird_metadata(
            snapshot_to_world_model(snapshot),
            db_id=db_id,
            metadata_documents=workspace.load_database_documents(db_id, split=args.split),
        )

    # Create SQL generator coprocessor(s)
    # Each backend is wrapped as a first-class OCTO coprocessor. Multiple
    # coprocessors can be composed into an ensemble in the execution adapter.
    if args.sql_backend == "claude":
        print(f"Using Claude SQL coprocessor: {args.claude_model}")
        sql_coprocessors = [
            ClaudeSQLGeneratorCoprocessor(model=args.claude_model, strict=False)
        ]
    elif args.sql_backend == "ollama":
        print(f"Using Ollama SQL coprocessor: {args.ollama_model}")
        sql_coprocessors = [
            OllamaSQLGeneratorCoprocessor(
                base_url=args.ollama_base_url,
                model=args.ollama_model,
                strict=False,
            )
        ]
    elif args.sql_backend == "trained":
        if not args.trained_model_path:
            raise SystemExit("--trained-model-path is required when --sql-backend trained")
        print(f"Using trained SQL coprocessor: {args.trained_model_path}")
        sql_coprocessors = [TrainedSQLGeneratorCoprocessor(model_path=args.trained_model_path)]
    else:
        print("Using heuristic SQL coprocessor")
        sql_coprocessors = [HeuristicSQLGeneratorCoprocessor()]

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

    octo_grounding = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=octo_worlds,  # Enriched world model
        top_k=8,
        include_evidence=False,
    )

    evidence_grounding = BirdBenchmarkAdapter(
        snapshots_by_db=snapshots,
        worlds_by_db=octo_worlds,
        top_k=8,
        include_evidence=True,  # Include task evidence
    )

    # Create execution adapters
    # naive_baseline always uses the heuristic SQL coprocessor so it does not
    # depend on OCTO grounding or any external LLM.
    naive_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_coprocessors=[HeuristicSQLGeneratorCoprocessor()],
        grounding_adapter=naive_grounding,
        use_repair=False,
        max_candidates=1,
    )

    rag_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_coprocessors=sql_coprocessors,
        grounding_adapter=rag_grounding,
        use_repair=False,
        max_candidates=1,
    )

    octo_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_coprocessors=sql_coprocessors,
        grounding_adapter=octo_grounding,
        use_repair=False,
        max_candidates=1,
    )

    evidence_adapter = BirdExecutionAdapter(
        snapshots_by_db=snapshots,
        db_paths_by_db=db_paths,
        sql_coprocessors=sql_coprocessors,
        grounding_adapter=evidence_grounding,
        use_repair=False,
        max_candidates=1,
    )

    repair_adapter = None
    if args.use_repair:
        repair_adapter = BirdExecutionAdapter(
            snapshots_by_db=snapshots,
            db_paths_by_db=db_paths,
            sql_coprocessors=sql_coprocessors,
            grounding_adapter=evidence_grounding,
            use_repair=True,
            max_candidates=args.max_candidates,
        )

    # Run benchmark
    runner = BirdExecutionBenchmarkRunner(
        naive_adapter=naive_adapter,
        rag_adapter=rag_adapter,
        octo_adapter=octo_adapter,
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
