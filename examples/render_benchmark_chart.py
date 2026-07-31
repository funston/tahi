import argparse
import json
import os
from pathlib import Path


def _collect_metric(system: dict, metric: str) -> float:
    if metric == "accuracy":
        return float(system.get("accuracy") or 0.0)
    return float((system.get("metrics") or {}).get(metric) or 0.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--metric", default="accuracy")
    parser.add_argument("--title", default="")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.environ.setdefault("MPLCONFIGDIR", str(Path(".local/mplconfig").resolve()))
    os.environ.setdefault("XDG_CACHE_HOME", str(Path(".local/xdg-cache").resolve()))

    import matplotlib.pyplot as plt

    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    systems = report.get("systems", [])
    labels = [system["system"] for system in systems]
    values = [_collect_metric(system, args.metric) for system in systems]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    colors = ["#8c8c8c", "#4c78a8", "#f58518", "#54a24b", "#e45756"]
    bars = ax.bar(labels, values, color=colors[: len(values)])
    ax.set_ylim(0.0, max(1.0, max(values) * 1.15 if values else 1.0))
    ax.set_ylabel(args.metric)
    ax.set_title(args.title or f"{report.get('benchmark_name', 'benchmark')} - {args.metric}")
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.015, f"{value:.3f}", ha="center", va="bottom")
    fig.tight_layout()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, format=output_path.suffix.lstrip("."))
    print(json.dumps({"output": str(output_path), "metric": args.metric}, indent=2))


if __name__ == "__main__":
    main()
