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
    TahiSpiderSnowSolveRunner,
    NativeSpiderSnowProblemSolver,
    SpiderSnowCandidateReranker,
    SpiderSnowHeuristicCandidateGenerator,
    SpiderSnowOllamaCandidateGenerator,
    SpiderSnowPromptedCandidateGenerator,
    SpiderSnowSchemaRepository,
    SpiderSnowWorkspace,
)


def _load_existing_solutions(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return list(payload)
    return list(payload.get("solutions", []))


def _write_payload(path: Path, solutions: list[dict]) -> dict:
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
        "summary": summary,
        "solutions": solutions,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spider2-root", default="/Users/richiek/work/Spider2")
    parser.add_argument("--credentials-path", default="/Users/richiek/work/tahi/snowflake_creds.json")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--candidate-generator", choices=("heuristic", "prompted", "ollama"), default="heuristic")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--model", default="google/gemma-3-270m-it")
    parser.add_argument("--strict-prompted", action="store_true")
    parser.add_argument("--db", action="append", dest="db_ids")
    parser.add_argument("--task-id", action="append", dest="task_ids")
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    output_path = Path(args.output)
    existing_solutions = _load_existing_solutions(output_path) if args.resume else []
    completed_ids = {str(solution.get("instance_id", "")) for solution in existing_solutions}

    workspace = SpiderSnowWorkspace(args.spider2_root)
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
    runner = TahiSpiderSnowSolveRunner(
        workspace=workspace,
        schema_repository=schema_repository,
        solver=solver,
    )
    problems = runner.load_problems(db_ids=args.db_ids, task_ids=args.task_ids)
    pending_problems = [problem for problem in problems if problem.instance_id not in completed_ids]

    solutions = list(existing_solutions)
    total_target = len(problems)

    if solutions:
        summary = _write_payload(output_path, solutions)
        print(
            json.dumps(
                {
                    "status": "resumed",
                    "completed": len(solutions),
                    "remaining": len(pending_problems),
                    "summary": summary,
                    "output": str(output_path),
                },
                indent=2,
                default=str,
            )
        )

    for index, problem in enumerate(pending_problems, start=1):
        solution = runner.solver.solve(problem)
        solutions.append(solution.to_dict())
        summary = _write_payload(output_path, solutions)
        print(
            json.dumps(
                {
                    "status": "progress",
                    "task_id": problem.instance_id,
                    "db_id": problem.db_id,
                    "completed": len(solutions),
                    "remaining": total_target - len(solutions),
                    "summary": summary,
                    "output": str(output_path),
                },
                indent=2,
                default=str,
            )
        )

    summary = _write_payload(output_path, solutions)
    print(json.dumps({"status": "done", "summary": summary, "output": str(output_path)}, indent=2, default=str))


if __name__ == "__main__":
    main()
