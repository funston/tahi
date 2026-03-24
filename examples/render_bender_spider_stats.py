import argparse
import json
from pathlib import Path


def _load_rows(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            rows.extend(payload)
            continue
        rows.extend(payload.get("tasks", []))
        rows.extend(payload.get("solutions", []))
    return rows


def _task_is_correct(row: dict) -> bool | None:
    if row.get("matched_gold") is True:
        return True
    if row.get("matched_gold") is False:
        return False
    if row.get("execution_error") or row.get("error"):
        return False
    return None


def _format_percent(value: float) -> str:
    return f"{value:.2f}%"


def _render_table(rows: list[dict]) -> str:
    per_db: dict[str, dict[str, object]] = {}
    skipped = 0
    for row in rows:
        correct = _task_is_correct(row)
        if correct is None:
            skipped += 1
            continue
        db = str(row.get("db_id", "")).upper()
        bucket = per_db.setdefault(
            db,
            {
                "questions": 0,
                "correct": 0,
            },
        )
        bucket["questions"] = int(bucket["questions"]) + 1
        bucket["correct"] = int(bucket["correct"]) + (1 if correct else 0)

    ordered = sorted(
        (
            (
                db,
                int(bucket["questions"]),
                int(bucket["correct"]),
                (100.0 * int(bucket["correct"]) / int(bucket["questions"])) if int(bucket["questions"]) else 0.0,
            )
            for db, bucket in per_db.items()
        ),
        key=lambda item: (-item[3], -item[1], item[0]),
    )

    total_questions = sum(item[1] for item in ordered)
    total_correct = sum(item[2] for item in ordered)
    grand_accuracy = (100.0 * total_correct / total_questions) if total_questions else 0.0

    lines = [
        "| Database |   Total Questions |   Total Correct Responses | Accuracy   |",
        "|--------------------------------------------------|-------------------|---------------------------|------------|",
    ]
    for db, questions, correct, accuracy in ordered:
        lines.append(
            f"| {db:<48} | {questions:>17} | {correct:>25} | {_format_percent(accuracy):<10} |"
        )
    lines.append(
        f"| {'***GRAND TOTAL***':<48} | {total_questions:>17} | {total_correct:>25} | {_format_percent(grand_accuracy):<10} |"
    )
    lines.append("")
    lines.append(f"TOTAL NUMBER OF DATABASES: {len(ordered)}")
    lines.append(f"Databases with at least 3 questions: {sum(1 for _, questions, _, _ in ordered if questions >= 3)}")
    if skipped:
        lines.append(f"Skipped tasks without definitive correctness field: {skipped}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", action="append", required=True, help="Path to cached baseline JSON. Repeat for multiple files.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = _load_rows([Path(path) for path in args.results])
    rendered = _render_table(rows)
    Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
