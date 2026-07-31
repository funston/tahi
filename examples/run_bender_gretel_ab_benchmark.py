import argparse
import itertools
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

from bender import (  # noqa: E402
    BenchmarkCaseResult,
    BenchmarkSystemSummary,
    benchmark_report_to_dict,
    render_markdown_summary_table,
    snapshot_to_world_model,
)
from implementations.gretel import (  # noqa: E402
    GretelBenchmarkAdapter,
    GretelDatasetLoader,
    build_snapshot_from_sql_context,
    enrich_world_with_gretel_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="train")
    parser.add_argument("--input-json", default="")
    parser.add_argument("--hf-cache-dir", default=".local/huggingface")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-results", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    loader = GretelDatasetLoader()

    if args.input_json:
        tasks_iter = iter(loader.load_json(args.input_json))
    else:
        tasks_iter = loader.iter_huggingface(split=args.split, cache_dir=args.hf_cache_dir)
    if args.limit > 0:
        tasks_iter = itertools.islice(tasks_iter, args.limit)

    result_store: dict[str, list[BenchmarkCaseResult]] = {
        "naive_lexical": [],
        "schema_only": [],
        "bender": [],
    }
    counts = {name: 0 for name in result_store}
    correct_counts = {name: 0 for name in result_store}
    metric_sums = {name: {"table_recall": 0.0, "top1_hit": 0.0} for name in result_store}
    metric_counts = {name: {"table_recall": 0, "top1_hit": 0} for name in result_store}

    for task in tasks_iter:
        snapshot = build_snapshot_from_sql_context(task.sql_context, database_name=task.task_id)
        baseline_world = snapshot_to_world_model(snapshot)
        bender_world = enrich_world_with_gretel_metadata(snapshot_to_world_model(snapshot), task)
        baseline_adapter = GretelBenchmarkAdapter(
            snapshots_by_task={task.task_id: snapshot},
            worlds_by_task={task.task_id: baseline_world},
            top_k=8,
        )
        bender_adapter = GretelBenchmarkAdapter(
            snapshots_by_task={task.task_id: snapshot},
            worlds_by_task={task.task_id: bender_world},
            top_k=8,
            include_metadata_in_query=True,
        )
        baseline = baseline_adapter.run_task(task)
        bender = bender_adapter.run_task(task)
        naive = _run_gretel_naive_baseline(snapshot, task)
        system_payloads = {
            "naive_lexical": naive,
            "schema_only": baseline,
            "bender": bender,
        }
        for system_name, payload in system_payloads.items():
            case_result = BenchmarkCaseResult(
                case_id=task.task_id,
                system=system_name,
                correct=bool((payload.get("table_recall") or 0.0) >= 1.0),
                metrics={
                    "table_recall": payload.get("table_recall"),
                    "top1_hit": _top1_hit(payload),
                },
                detail=payload,
            )
            counts[system_name] += 1
            correct_counts[system_name] += int(case_result.correct)
            for metric_name, metric_value in case_result.metrics.items():
                if isinstance(metric_value, (int, float)):
                    metric_sums[system_name][metric_name] += float(metric_value)
                    metric_counts[system_name][metric_name] += 1
            if args.include_results:
                result_store[system_name].append(case_result)

    summaries: list[BenchmarkSystemSummary] = []
    for system_name in ["naive_lexical", "schema_only", "bender"]:
        tasks_evaluated = counts[system_name]
        metrics = {}
        for metric_name in ["table_recall", "top1_hit"]:
            count = metric_counts[system_name][metric_name]
            metrics[f"avg_{metric_name}"] = (metric_sums[system_name][metric_name] / count) if count else None
        summaries.append(
            BenchmarkSystemSummary(
                system=system_name,
                tasks_evaluated=tasks_evaluated,
                accuracy=(correct_counts[system_name] / tasks_evaluated) if tasks_evaluated else 0.0,
                metrics=metrics,
            )
        )

    report = benchmark_report_to_dict(
        benchmark_name="gretel_ab_grounding",
        summaries=summaries,
        results_by_system=result_store,
        include_results=args.include_results,
    )
    report["markdown_summary"] = render_markdown_summary_table(summaries)
    report["dataset_split"] = args.split if not args.input_json else "frozen_json"
    report["tasks_processed"] = counts["bender"]

    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "markdown_summary": report["markdown_summary"]}, indent=2))


def _normalize_identifier(value: str) -> str:
    import re

    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).replace("-", "_")
    return re.sub(r"[^a-z0-9_]+", "_", snake.lower()).strip("_")


def _top1_hit(result: dict) -> float:
    candidate_tables = result.get("candidate_tables", [])
    gold_tables = result.get("gold_tables", [])
    if not candidate_tables or not gold_tables:
        return 0.0
    predicted = _normalize_identifier(candidate_tables[0])
    gold = {_normalize_identifier(name) for name in gold_tables}
    return 1.0 if predicted in gold else 0.0


def _run_gretel_naive_baseline(snapshot, task):
    import re

    question_tokens = set(re.findall(r"[a-z0-9_]+", task.sql_prompt.lower()))
    scored = []
    for table in snapshot.tables:
        table_tokens = set(re.findall(r"[a-z0-9_]+", table.name.lower()))
        column_tokens = {
            token
            for column in table.columns
            for token in re.findall(r"[a-z0-9_]+", column.name.lower())
        }
        score = len(question_tokens & table_tokens) * 2.0 + len(question_tokens & column_tokens) * 0.5
        scored.append((score, table.name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    candidate_tables = [name for score, name in scored if score > 0.0][:3]
    gold_table_names = task.gold_tables
    table_recall = None
    if gold_table_names:
        gold_tables = {_normalize_identifier(name) for name in gold_table_names}
        predicted_tables = {_normalize_identifier(name) for name in candidate_tables}
        table_recall = len(gold_tables & predicted_tables) / len(gold_tables) if gold_tables else None
    return {
        "task_id": task.task_id,
        "domain": task.domain,
        "question": task.sql_prompt,
        "candidate_tables": candidate_tables,
        "table_recall": table_recall,
        "gold_tables": gold_table_names,
    }


if __name__ == "__main__":
    main()
