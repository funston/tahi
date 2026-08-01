"""
Result formatting utilities for OCTO evaluations.

Produces:
  - Markdown summary with table and ASCII bar chart
  - SVG bar chart
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class EvalMetric:
    name: str
    rag_accuracy: float
    octo_accuracy: float
    rag_retrieval: float
    octo_retrieval: float


def _bar(value: float, width: int = 20, max_val: float = 1.0) -> str:
    filled = int(round(value / max_val * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def format_ascii_report(metrics: list[EvalMetric]) -> str:
    """Return an ASCII bar chart + table for one or more evals."""
    lines: list[str] = []
    lines.append("OCTO Evaluation Results")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{'Eval':<20} {'RAG Acc':<9} {'OCTO Acc':<9} {'Δ':<8}")
    lines.append("-" * 60)
    for m in metrics:
        delta = m.octo_accuracy - m.rag_accuracy
        delta_str = f"{delta:+.1%}"
        lines.append(
            f"{m.name:<20} {m.rag_accuracy:>7.1%}   {m.octo_accuracy:>7.1%}   {delta_str:>7}"
        )
        lines.append(
            f"  RAG  {_bar(m.rag_accuracy)} {m.rag_accuracy:>6.1%}"
        )
        lines.append(
            f"  OCTO {_bar(m.octo_accuracy)} {m.octo_accuracy:>6.1%}"
        )
        lines.append("")
    return "\n".join(lines)


def format_markdown_report(metrics: list[EvalMetric], meta: dict[str, Any] | None = None) -> str:
    """Return a Markdown table + ASCII chart for one or more evals."""
    lines: list[str] = []
    lines.append("# OCTO Evaluation Results")
    lines.append("")
    if meta:
        for key, value in meta.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")
    lines.append("| Eval | RAG Accuracy | OCTO Accuracy | Delta |")
    lines.append("|---|---:|---:|---:|")
    for m in metrics:
        delta = m.octo_accuracy - m.rag_accuracy
        lines.append(
            f"| {m.name} | {m.rag_accuracy:.1%} | {m.octo_accuracy:.1%} | {delta:+.1%} |"
        )
    lines.append("")
    lines.append("```")
    lines.append(format_ascii_report(metrics))
    lines.append("```")
    lines.append("")
    lines.append("## Retrieval Recall")
    lines.append("")
    lines.append("| Eval | RAG Recall | OCTO Recall |")
    lines.append("|---|---:|---:|")
    for m in metrics:
        lines.append(
            f"| {m.name} | {m.rag_retrieval:.1%} | {m.octo_retrieval:.1%} |"
        )
    return "\n".join(lines)


def format_svg_report(metrics: list[EvalMetric], width: int = 800, height: int = 400) -> str:
    """Return an SVG bar chart comparing RAG and OCTO accuracies."""
    margin_left = 120
    margin_right = 40
    margin_top = 60
    margin_bottom = 80
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom

    n = len(metrics)
    group_height = chart_height / n
    bar_height = group_height * 0.25
    max_val = 1.0

    def x(val: float) -> float:
        return margin_left + (val / max_val) * chart_width

    svg_parts: list[str] = []
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    svg_parts.append('<style>text { font-family: sans-serif; font-size: 14px; } .title { font-size: 20px; font-weight: bold; } .label { font-size: 12px; }</style>')
    svg_parts.append(f'<text x="{width/2}" y="30" text-anchor="middle" class="title">OCTO vs RAG Accuracy</text>')

    # Grid lines at 0%, 25%, 50%, 75%, 100%.
    for pct in [0.0, 0.25, 0.5, 0.75, 1.0]:
        gx = x(pct)
        svg_parts.append(f'<line x1="{gx}" y1="{margin_top}" x2="{gx}" y2="{height - margin_bottom}" stroke="#e0e0e0" stroke-width="1"/>')
        svg_parts.append(f'<text x="{gx}" y="{height - margin_bottom + 20}" text-anchor="middle" class="label">{pct:.0%}</text>')

    # Bars.
    for i, m in enumerate(metrics):
        y_base = margin_top + i * group_height
        label_y = y_base + group_height / 2
        svg_parts.append(f'<text x="{margin_left - 10}" y="{label_y}" text-anchor="end" dominant-baseline="middle">{m.name}</text>')

        rag_width = (m.rag_accuracy / max_val) * chart_width
        octo_width = (m.octo_accuracy / max_val) * chart_width

        svg_parts.append(f'<rect x="{margin_left}" y="{y_base + group_height*0.15}" width="{rag_width}" height="{bar_height}" fill="#94a3b8"/>')
        svg_parts.append(f'<rect x="{margin_left}" y="{y_base + group_height*0.55}" width="{octo_width}" height="{bar_height}" fill="#2563eb"/>')

        svg_parts.append(f'<text x="{margin_left + rag_width + 5}" y="{y_base + group_height*0.15 + bar_height/2}" dominant-baseline="middle" class="label">{m.rag_accuracy:.1%}</text>')
        svg_parts.append(f'<text x="{margin_left + octo_width + 5}" y="{y_base + group_height*0.55 + bar_height/2}" dominant-baseline="middle" class="label">{m.octo_accuracy:.1%}</text>')

    # Legend.
    legend_y = height - 30
    svg_parts.append(f'<rect x="{margin_left}" y="{legend_y}" width="15" height="15" fill="#94a3b8"/>')
    svg_parts.append(f'<text x="{margin_left + 22}" y="{legend_y + 12}" class="label">RAG</text>')
    svg_parts.append(f'<rect x="{margin_left + 80}" y="{legend_y}" width="15" height="15" fill="#2563eb"/>')
    svg_parts.append(f'<text x="{margin_left + 102}" y="{legend_y + 12}" class="label">OCTO</text>')

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def write_eval_artifacts(
    results_dir: Path,
    name: str,
    report: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Write JSON, Markdown, and SVG artifacts for a single eval."""
    results_dir.mkdir(parents=True, exist_ok=True)

    metric = EvalMetric(
        name=name,
        rag_accuracy=report["rag"]["accuracy"],
        octo_accuracy=report["octo"]["accuracy"],
        rag_retrieval=report["rag"]["retrieval_recall"],
        octo_retrieval=report["octo"]["retrieval_recall"],
    )

    json_path = results_dir / f"{name}.json"
    md_path = results_dir / f"{name}.md"
    svg_path = results_dir / f"{name}.svg"

    json_path.write_text(__import__("json").dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(format_markdown_report([metric], meta), encoding="utf-8")
    svg_path.write_text(format_svg_report([metric]), encoding="utf-8")

    return {"json": json_path, "md": md_path, "svg": svg_path}
