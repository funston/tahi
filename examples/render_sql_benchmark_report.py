import argparse
import json
import os
from pathlib import Path


def _load_report(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metric(system: dict, name: str) -> float:
    if name == "accuracy":
        return float(system.get("accuracy") or 0.0)
    return float((system.get("metrics") or {}).get(name) or 0.0)


def _render_summary(ax, title: str, report: dict) -> None:
    ax.axis("off")
    lines = [title]
    for system in report.get("systems", []):
        lines.append(
            f"{system['system']}: accuracy={_metric(system, 'accuracy'):.3f}, "
            f"avg_table_recall={_metric(system, 'avg_table_recall'):.3f}, "
            f"avg_top1_hit={_metric(system, 'avg_top1_hit'):.3f}"
        )
    ax.text(0.0, 1.0, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=10)


def _render_legend(ax) -> None:
    ax.axis("off")
    lines = [
        "Legend",
        "naive_lexical: simple lexical table matching baseline with no world model.",
        "schema_only: BENDER schema coprocessor over parsed schema only, with no enriched world metadata.",
        "bender: BENDER world-model grounding with enriched metadata/documents, but no extra task evidence injected.",
        "bender_with_evidence: BENDER world-model grounding plus the dataset's task evidence field injected into the query path.",
    ]
    ax.text(0.0, 1.0, "\n".join(lines), va="top", ha="left", fontsize=10)


def _render_bar(ax, title: str, report: dict, metric: str) -> None:
    systems = report.get("systems", [])
    labels = [system["system"] for system in systems]
    values = [_metric(system, metric) for system in systems]
    colors = ["#8c8c8c", "#4c78a8", "#f58518", "#54a24b", "#e45756"]
    bars = ax.bar(labels, values, color=colors[: len(values)])
    ax.set_ylim(0.0, max(1.0, max(values) * 1.15 if values else 1.0))
    ax.set_title(title)
    ax.set_ylabel(metric)
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.015, f"{value:.3f}", ha="center", va="bottom")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bird-input", required=True)
    parser.add_argument("--gretel-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.environ.setdefault("MPLCONFIGDIR", str(Path(".local/mplconfig").resolve()))
    os.environ.setdefault("XDG_CACHE_HOME", str(Path(".local/xdg-cache").resolve()))

    import matplotlib.pyplot as plt

    bird = _load_report(args.bird_input)
    gretel = _load_report(args.gretel_input)

    fig = plt.figure(figsize=(14, 13))
    grid = fig.add_gridspec(4, 2, height_ratios=[0.55, 1.0, 1.0, 0.9])

    ax0 = fig.add_subplot(grid[0, :])
    ax1 = fig.add_subplot(grid[1, 0])
    ax2 = fig.add_subplot(grid[1, 1])
    ax3 = fig.add_subplot(grid[2, 0])
    ax4 = fig.add_subplot(grid[2, 1])
    ax5 = fig.add_subplot(grid[3, 0])
    ax6 = fig.add_subplot(grid[3, 1])

    _render_legend(ax0)
    _render_bar(ax1, "BIRD Tiny Grounding Accuracy", bird, "accuracy")
    _render_bar(ax2, "BIRD Tiny Average Table Recall", bird, "avg_table_recall")
    _render_bar(ax3, "Gretel Train[:100] Grounding Accuracy", gretel, "accuracy")
    _render_bar(ax4, "Gretel Train[:100] Average Table Recall", gretel, "avg_table_recall")
    _render_summary(ax5, "BIRD Summary", bird)
    _render_summary(ax6, "Gretel Summary", gretel)

    fig.suptitle("BENDER SQL Grounding Benchmark Report", fontsize=18, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.985])

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format=output_path.suffix.lstrip("."))
    print(json.dumps({"output": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
