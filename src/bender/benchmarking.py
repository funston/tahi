from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkCaseResult:
    case_id: str
    system: str
    correct: bool
    metrics: dict[str, float | int | bool | None] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkSystemSummary:
    system: str
    tasks_evaluated: int
    accuracy: float
    metrics: dict[str, float | int | bool | None] = field(default_factory=dict)


def summarize_system_results(
    system: str,
    results: list[BenchmarkCaseResult],
    *,
    metric_names: list[str] | None = None,
) -> BenchmarkSystemSummary:
    tasks_evaluated = len(results)
    accuracy = (sum(1 for result in results if result.correct) / tasks_evaluated) if tasks_evaluated else 0.0
    metric_names = metric_names or []
    metrics: dict[str, float | int | bool | None] = {}
    for metric_name in metric_names:
        values = [
            float(value)
            for result in results
            for key, value in result.metrics.items()
            if key == metric_name and isinstance(value, (int, float))
        ]
        metrics[f"avg_{metric_name}"] = (sum(values) / len(values)) if values else None
    return BenchmarkSystemSummary(
        system=system,
        tasks_evaluated=tasks_evaluated,
        accuracy=accuracy,
        metrics=metrics,
    )


def benchmark_report_to_dict(
    *,
    benchmark_name: str,
    summaries: list[BenchmarkSystemSummary],
    results_by_system: dict[str, list[BenchmarkCaseResult]],
    include_results: bool = True,
) -> dict[str, Any]:
    systems_payload = []
    for summary in summaries:
        systems_payload.append(
            {
                "system": summary.system,
                "tasks_evaluated": summary.tasks_evaluated,
                "accuracy": summary.accuracy,
                "metrics": dict(summary.metrics),
                "results": (
                    [
                        {
                            "case_id": result.case_id,
                            "system": result.system,
                            "correct": result.correct,
                            "metrics": dict(result.metrics),
                            "detail": dict(result.detail),
                        }
                        for result in results_by_system.get(summary.system, [])
                    ]
                    if include_results
                    else []
                ),
            }
        )
    return {
        "benchmark_name": benchmark_name,
        "systems": systems_payload,
    }


def render_markdown_summary_table(summaries: list[BenchmarkSystemSummary]) -> str:
    if not summaries:
        return ""
    metric_names = sorted({metric for summary in summaries for metric in summary.metrics})
    headers = ["System", "Tasks", "Accuracy", *metric_names]
    rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for summary in summaries:
        values = [
            summary.system,
            str(summary.tasks_evaluated),
            f"{summary.accuracy:.3f}",
            *[
                "" if summary.metrics.get(metric_name) is None else f"{float(summary.metrics[metric_name]):.3f}"
                for metric_name in metric_names
            ],
        ]
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)
