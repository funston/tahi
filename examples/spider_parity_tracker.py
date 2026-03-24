import argparse
import json
import re
from pathlib import Path


def load_prior_stats(path: str | Path) -> dict[str, dict[str, object]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    stats: dict[str, dict[str, object]] = {}
    pattern = re.compile(
        r"^\|\s*(?P<db>.+?)\s*\|\s*(?P<questions>\d+)\s*\|\s*(?P<correct>\d+)\s*\|\s*(?P<acc>[0-9.]+%)\s*\|$"
    )
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        db = match.group("db").strip()
        if db.startswith("***"):
            continue
        stats[db] = {
            "questions": int(match.group("questions")),
            "correct": int(match.group("correct")),
            "accuracy": match.group("acc"),
        }
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-stats", required=True)
    parser.add_argument("--current-results", required=True)
    parser.add_argument("--db", action="append", dest="dbs")
    args = parser.parse_args()

    prior = load_prior_stats(args.prior_stats)
    current = json.loads(Path(args.current_results).read_text(encoding="utf-8"))
    allowed = {db.upper() for db in (args.dbs or [])}

    rows = []
    for task in current.get("tasks", []):
        db = str(task.get("db_id", "")).upper()
        if allowed and db not in allowed:
            continue
        prior_row = prior.get(db)
        rows.append(
            {
                "db": db,
                "task_id": task.get("task_id"),
                "current_gold_match": task.get("matched_gold"),
                "current_execution_success": task.get("execution_success"),
                "prior_accuracy": None if prior_row is None else prior_row["accuracy"],
                "prior_questions": None if prior_row is None else prior_row["questions"],
            }
        )

    print(json.dumps({"rows": rows}, indent=2))


if __name__ == "__main__":
    main()
