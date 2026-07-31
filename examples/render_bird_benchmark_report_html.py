import argparse
import html
import json
from pathlib import Path


COLORS = {
    "naive_lexical": "#8c8c8c",
    "schema_only": "#4c78a8",
    "bender": "#f58518",
    "bender_with_evidence": "#54a24b",
}


def _load_report(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metric(system: dict, name: str) -> float:
    if name == "accuracy":
        return float(system.get("accuracy") or 0.0)
    return float((system.get("metrics") or {}).get(name) or 0.0)


def _system(report: dict, name: str) -> dict:
    for system in report.get("systems", []):
        if system["system"] == name:
            return system
    return {}


def _chart_svg(title: str, systems: list[dict], metric: str) -> str:
    width = 760
    height = 320
    left = 52
    right = 24
    top = 34
    bottom = 68
    plot_w = width - left - right
    plot_h = height - top - bottom
    slot = plot_w / max(1, len(systems))
    bar_w = min(86, slot * 0.62)

    rows = [
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{html.escape(title)}">',
        f'<text x="{left}" y="20" class="chart-title">{html.escape(title)}</text>',
    ]
    for tick in range(6):
        value = tick / 5
        y = top + plot_h - (plot_h * value)
        rows.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid-line" />')
        rows.append(f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" class="axis-label">{value:.1f}</text>')
    rows.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}" class="axis-line" />')

    for index, system in enumerate(systems):
        value = max(0.0, min(1.0, _metric(system, metric)))
        x = left + (slot * index) + (slot - bar_w) / 2
        bar_h = plot_h * value
        y = top + plot_h - bar_h
        label_x = x + bar_w / 2
        color = COLORS.get(system["system"], "#999999")
        rows.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="6" fill="{color}" />')
        rows.append(f'<text x="{label_x:.1f}" y="{max(top + 14, y - 8):.1f}" text-anchor="middle" class="value-label">{value:.3f}</text>')
        rows.append(f'<text x="{label_x:.1f}" y="{top+plot_h+18:.1f}" text-anchor="middle" class="axis-label system-label">{html.escape(system["system"])}</text>')
    rows.append("</svg>")
    return "\n".join(rows)


def _legend_html() -> str:
    items = [
        ("naive_lexical", "Simple lexical table matching baseline with no world model."),
        ("schema_only", "BENDER schema coprocessor over parsed schema only, with no enriched world metadata."),
        ("bender", "BENDER world-model grounding with enriched metadata/documents, but no extra task evidence injected."),
        ("bender_with_evidence", "BENDER world-model grounding plus the dataset's task evidence field injected into the query path."),
    ]
    rows = []
    for key, description in items:
        color = COLORS.get(key, "#999999")
        rows.append(
            f'<div class="legend-row"><span class="swatch" style="background:{color}"></span><strong>{html.escape(key)}</strong><span>{html.escape(description)}</span></div>'
        )
    return "\n".join(rows)


def _summary_table(report: dict) -> str:
    rows = []
    for system in report.get("systems", []):
        rows.append(
            "<tr>"
            f"<td>{html.escape(system['system'])}</td>"
            f"<td>{_metric(system, 'accuracy'):.3f}</td>"
            f"<td>{_metric(system, 'avg_table_recall'):.3f}</td>"
            f"<td>{_metric(system, 'avg_top1_hit'):.3f}</td>"
            "</tr>"
        )
    return f"""
    <section class="panel">
      <h2>BENDER BIRD Dev Grounding Summary</h2>
      <table>
        <thead>
          <tr>
            <th>System</th>
            <th>Grounding Accuracy</th>
            <th>Avg Table Recall</th>
            <th>Avg Top-1 Hit</th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows)}
        </tbody>
      </table>
    </section>
    """


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bird-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    bird = _load_report(args.bird_input)
    schema_only = _system(bird, "schema_only")
    evidence = _system(bird, "bender_with_evidence")
    delta_acc = _metric(evidence, "accuracy") - _metric(schema_only, "accuracy")
    delta_recall = _metric(evidence, "avg_table_recall") - _metric(schema_only, "avg_table_recall")
    delta_top1 = _metric(evidence, "avg_top1_hit") - _metric(schema_only, "avg_top1_hit")

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BENDER BIRD Benchmark Report</title>
  <style>
    :root {{
      --bg: #f7f5ef;
      --panel: #ffffff;
      --ink: #1d1d1b;
      --muted: #666055;
      --line: #d8d1c5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #efe7da 0%, var(--bg) 32%, #faf8f4 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 36px 24px 64px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p {{ line-height: 1.55; color: var(--muted); }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 10px 24px rgba(68, 54, 30, 0.06);
    }}
    .hero {{ padding: 28px; margin-bottom: 18px; }}
    .panel {{ padding: 18px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-top: 18px;
    }}
    .charts {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-top: 18px;
    }}
    .legend-row {{
      display: grid;
      grid-template-columns: 14px 180px 1fr;
      gap: 10px;
      align-items: start;
      margin: 10px 0;
      font-size: 14px;
      line-height: 1.45;
    }}
    .swatch {{
      width: 14px;
      height: 14px;
      border-radius: 999px;
      margin-top: 4px;
    }}
    .callout {{
      font-size: 15px;
      line-height: 1.55;
    }}
    .metric-boxes {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 12px;
    }}
    .metric-box {{
      border: 1px solid #e7e0d4;
      border-radius: 14px;
      padding: 14px;
      background: #fbfaf7;
    }}
    .metric-box strong {{
      display: block;
      font-size: 26px;
      margin-bottom: 6px;
    }}
    .chart {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .chart-title {{ font-size: 15px; font-weight: 700; }}
    .axis-line {{ stroke: #7f7768; stroke-width: 1.1; }}
    .grid-line {{ stroke: #ddd6ca; stroke-width: 1; }}
    .axis-label {{ font-size: 11px; fill: #5f5b53; }}
    .system-label {{ font-size: 10px; }}
    .value-label {{ font-size: 11px; fill: #1d1d1b; font-weight: 700; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid #ece6db;
    }}
    th {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #6e6a62;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      background: #f1ece2;
      padding: 1px 5px;
      border-radius: 5px;
    }}
    @media (max-width: 960px) {{
      .grid, .charts, .metric-boxes {{
        grid-template-columns: 1fr;
      }}
      .legend-row {{
        grid-template-columns: 14px 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>BENDER BIRD Benchmark Report</h1>
      <p>This page is only about BIRD. It shows BENDER's current full-dev grounding result, the actual lift from the evidence-aware path, and the current official BIRD leaderboard context.</p>
      <p class="callout"><strong>Read this correctly:</strong> BENDER's current <code>0.926</code> is a <strong>grounding accuracy</strong> result on BIRD dev. The official BIRD leaderboard numbers like <code>81.95</code> are <strong>end-to-end execution accuracy</strong>. They are not the same metric.</p>
    </section>

    <section class="grid">
      <section class="panel">
        <h2>What The BENDER Number Means</h2>
        <p>Grounding accuracy here means a question counts as correct only when all gold tables are present in the candidate table set produced by the grounding stage.</p>
        <p>So <code>0.926</code> means that on 92.6% of BIRD dev questions, the evidence-aware BENDER path recovered every gold table somewhere in its candidate set.</p>
        <p>It does <strong>not</strong> mean BENDER solved 92.6% of BIRD end to end.</p>
      </section>
      <section class="panel">
        <h2>Why This Still Matters</h2>
        <p>If grounding is wrong, SQL generation is usually dead on arrival. BENDER is currently strongest as an upstream world-coprocessor that improves recall of the right schema objects before generation.</p>
        <p>The meaningful current claim is not “we beat the BIRD leaderboard.” The meaningful claim is “we improve the grounding stage on full BIRD dev when evidence is available.”</p>
      </section>
    </section>

    <section class="panel" style="margin-top:18px;">
      <h2>Actual Lift Over The Baseline</h2>
      <div class="metric-boxes">
        <div class="metric-box">
          <strong>{delta_acc:+.3f}</strong>
          <span>Absolute grounding accuracy lift for <code>bender_with_evidence</code> over <code>schema_only</code>.</span>
        </div>
        <div class="metric-box">
          <strong>{delta_recall:+.3f}</strong>
          <span>Absolute average table recall lift over <code>schema_only</code>.</span>
        </div>
        <div class="metric-box">
          <strong>{delta_top1:+.3f}</strong>
          <span>Absolute top-1 hit change. This got slightly worse, which suggests broader recall rather than better rank-1 precision.</span>
        </div>
      </div>
    </section>

    <section class="charts">
      <section class="panel">{_chart_svg("BIRD Dev Grounding Accuracy", bird.get("systems", []), "accuracy")}</section>
      <section class="panel">{_chart_svg("BIRD Dev Average Table Recall", bird.get("systems", []), "avg_table_recall")}</section>
    </section>

    <section class="grid">
      {_summary_table(bird)}
      <section class="panel">
        <h2>Legend</h2>
        {_legend_html()}
      </section>
    </section>

    <section class="grid">
      <section class="panel">
        <h2>Current Official BIRD Leaderboard Context</h2>
        <p>These are execution-accuracy reference points from the current official BIRD leaderboard. They belong here for context, but they are not apples-to-apples comparisons with the grounding metrics above.</p>
        <table>
          <thead>
            <tr>
              <th>Track</th>
              <th>System</th>
              <th>Dev EX</th>
              <th>Test EX</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Overall</td>
              <td>AskData + GPT-4o</td>
              <td>77.64</td>
              <td>81.95</td>
            </tr>
            <tr>
              <td>Single-Model</td>
              <td>Q-SQL</td>
              <td>72.99</td>
              <td>76.47</td>
            </tr>
            <tr>
              <td>Single-Model</td>
              <td>Gemini-SQL</td>
              <td>72.62</td>
              <td>76.63</td>
            </tr>
            <tr>
              <td>Baseline</td>
              <td>GPT-4</td>
              <td>46.35</td>
              <td>54.89</td>
            </tr>
            <tr>
              <td>Human</td>
              <td>Data Engineers + DB Students</td>
              <td>92.96</td>
              <td>n/a</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section class="panel">
        <h2>Bottom-Line Reading</h2>
        <p><strong>Good news:</strong> BENDER has a real full-dev BIRD result. The evidence-aware path moves grounding accuracy from <code>0.864</code> to <code>0.926</code> across 1534 dev tasks.</p>
        <p><strong>Weak news:</strong> plain metadata enrichment alone does nothing here; <code>bender</code> equals <code>schema_only</code>.</p>
        <p><strong>Serious next step:</strong> convert this grounding lift into an end-to-end SQL execution benchmark. Until then, this report should be read as evidence that BENDER improves schema grounding, not as proof that it beats the current BIRD leaderboard.</p>
      </section>
    </section>
  </main>
</body>
</html>
"""

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")
    print(json.dumps({"output": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
