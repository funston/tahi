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

from implementations.spider import (
    BenderSpiderSnowSolveRunner,
    NativeSpiderSnowProblemSolver,
    SpiderSnowCandidateReranker,
    SpiderSnowHeuristicCandidateGenerator,
    SpiderSnowOllamaCandidateGenerator,
    SpiderSnowProblemLoader,
    SpiderSnowPromptedCandidateGenerator,
    SpiderSnowSchemaRepository,
    SpiderSnowWorkspace,
    select_stratified_spider_snow_tasks,
)


def _load_existing_solutions(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return list(payload)
    return list(payload.get("solutions", []))


def _write_payload(path: Path, selected_task_ids: list[str], solutions: list[dict], metadata: dict) -> dict:
    total = len(solutions)
    correct = sum(1 for solution in solutions if solution.get("score", 0.0) >= 1.0)
    broken = sum(1 for solution in solutions if not solution.get("execution_success", False))
    wrong = total - correct - broken
    summary = {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "broken": broken,
        "accuracy": (correct / total) if total else 0.0,
    }
    payload = {
        "selection": {
            "task_ids": selected_task_ids,
            "metadata": metadata,
        },
        "summary": summary,
        "solutions": solutions,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", default="/Users/richiek/work/Spider2")
    parser.add_argument("--credentials-path", default="/Users/richiek/work/bender/snowflake_creds.json")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--slice-size", type=int, default=32)
    parser.add_argument("--per-db-limit", type=int, default=1)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--candidate-generator", choices=("heuristic", "prompted", "ollama"), default="ollama")
    parser.add_argument("--base-url", default="http://127.0.0.1:11435")
    parser.add_argument("--model", default="qwen2.5-coder:latest")
    parser.add_argument("--strict-prompted", action="store_true")
    parser.add_argument("--emit-task-ids", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    workspace = SpiderSnowWorkspace(args.spider2_root)
    loader = SpiderSnowProblemLoader(workspace)
    tasks = loader.load_tasks()
    selection = select_stratified_spider_snow_tasks(
        tasks,
        slice_size=args.slice_size,
        per_db_limit=args.per_db_limit,
    )

    if args.emit_task_ids:
        print(json.dumps({"task_ids": list(selection.task_ids), "metadata": selection.metadata}, indent=2))
        return

    output_path = Path(args.output)
    existing_solutions = _load_existing_solutions(output_path) if args.resume else []
    completed_ids = {str(solution.get("instance_id", "")) for solution in existing_solutions}

    schema_repository = SpiderSnowSchemaRepository(workspace)
    if args.candidate_generator == "prompted":
        candidate_generator = SpiderSnowPromptedCandidateGenerator(
            base_url=args.base_url,
            model=args.model,
            strict=args.strict_prompted,
            fallback=SpiderSnowHeuristicCandidateGenerator(),
        )
    elif args.candidate_generator == "ollama":
        candidate_generator = SpiderSnowOllamaCandidateGenerator(
            base_url=args.base_url,
            model=args.model,
            strict=True,
        )
    else:
        candidate_generator = SpiderSnowHeuristicCandidateGenerator()
    solver = NativeSpiderSnowProblemSolver(
        workspace=workspace,
        schema_repository=schema_repository,
        credentials_path=args.credentials_path,
        top_k=args.top_k,
        max_candidates=args.max_candidates,
        candidate_generator=candidate_generator,
        candidate_reranker=SpiderSnowCandidateReranker(),
    )
    runner = BenderSpiderSnowSolveRunner(
        workspace=workspace,
        schema_repository=schema_repository,
        solver=solver,
    )
    problems = runner.load_problems(task_ids=list(selection.task_ids))
    pending_problems = [problem for problem in problems if problem.instance_id not in completed_ids]
    solutions = list(existing_solutions)

    if solutions:
        summary = _write_payload(output_path, list(selection.task_ids), solutions, dict(selection.metadata))
        print(
            json.dumps(
                {
                    "status": "resumed",
                    "completed": len(solutions),
                    "remaining": len(pending_problems),
                    "summary": summary,
                    "output": args.output,
                },
                indent=2,
            )
        )

    for problem in pending_problems:
        solution = runner.solver.solve(problem).to_dict()
        solutions.append(solution)
        summary = _write_payload(output_path, list(selection.task_ids), solutions, dict(selection.metadata))
        print(
            json.dumps(
                {
                    "status": "progress",
                    "task_id": problem.instance_id,
                    "db_id": problem.db_id,
                    "completed": len(solutions),
                    "remaining": len(pending_problems) - (len(solutions) - len(existing_solutions)),
                    "summary": summary,
                    "output": args.output,
                },
                indent=2,
            )
        )

    summary = _write_payload(output_path, list(selection.task_ids), solutions, dict(selection.metadata))
    print(
        json.dumps(
            {
                "selection": {
                    "task_ids": list(selection.task_ids),
                    "metadata": selection.metadata,
                },
                "summary": summary,
                "output": args.output,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
