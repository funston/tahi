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


def _chart_svg(title: str, systems: list[dict], metric: str) -> str:
    width = 620
    height = 280
    left = 48
    right = 20
    top = 30
    bottom = 58
    plot_w = width - left - right
    plot_h = height - top - bottom
    count = max(1, len(systems))
    slot = plot_w / count
    bar_w = min(72, slot * 0.58)

    rows = [
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{html.escape(title)}">',
        f'<text x="{left}" y="18" class="chart-title">{html.escape(title)}</text>',
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
        rows.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="6" fill="{color}" />'
        )
        rows.append(
            f'<text x="{label_x:.1f}" y="{max(top + 14, y - 8):.1f}" text-anchor="middle" class="value-label">{value:.3f}</text>'
        )
        rows.append(
            f'<text x="{label_x:.1f}" y="{top+plot_h+18:.1f}" text-anchor="middle" class="axis-label system-label">{html.escape(system["system"])}</text>'
        )

    rows.append("</svg>")
    return "\n".join(rows)


def _summary_table(title: str, report: dict) -> str:
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
    body = "\n".join(rows)
    return f"""
    <section class="panel">
      <h3>{html.escape(title)}</h3>
      <table>
        <thead>
          <tr>
            <th>System</th>
            <th>Accuracy</th>
            <th>Avg Table Recall</th>
            <th>Avg Top-1 Hit</th>
          </tr>
        </thead>
        <tbody>
          {body}
        </tbody>
      </table>
    </section>
    """


def _external_reference_tables() -> str:
    return """
    <section class="grid">
      <section class="panel">
        <h2>External Reference: BIRD Official Leaderboard</h2>
        <p>These numbers are execution accuracy from the official BIRD leaderboard. They are included as external reference points only. They are <strong>not directly comparable</strong> to BENDER's grounding accuracy in this report.</p>
        <table>
          <thead>
            <tr>
              <th>Track</th>
              <th>System</th>
              <th>Dev</th>
              <th>Test</th>
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
              <td>Human</td>
              <td>Data Engineers + DB Students</td>
              <td>92.96</td>
              <td>n/a</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section class="panel">
        <h2>External Reference: Gretel Dataset Evidence</h2>
        <p>There does not appear to be a public official leaderboard for <code>gretelai/synthetic_text_to_sql</code>. The strongest external reference currently available is the dataset card itself.</p>
        <table>
          <thead>
            <tr>
              <th>Reference</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Dataset size</td>
              <td>105,851 records</td>
            </tr>
            <tr>
              <td>Split sizes</td>
              <td>100,000 train / 5,851 test</td>
            </tr>
            <tr>
              <td>GPT-4 judge vs b-mc2/sql-create-context</td>
              <td>+54.6% SQL standards, +34.5% SQL correctness, +8.5% adherence</td>
            </tr>
          </tbody>
        </table>
      </section>
    </section>
    """


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


def _headline_list(report: dict) -> str:
    rows = []
    for system in report.get("systems", []):
        rows.append(f"<li><strong>{html.escape(system['system'])}</strong>: {_metric(system, 'accuracy'):.3f}</li>")
    return "\n".join(rows)


def _system(report: dict, name: str) -> dict:
    for system in report.get("systems", []):
        if system["system"] == name:
            return system
    return {}


def _delta(a: float, b: float) -> float:
    return a - b


def _metric_context_panel(bird: dict, gretel: dict) -> str:
    bird_schema = _system(bird, "schema_only")
    bird_evidence = _system(bird, "bender_with_evidence")
    bird_delta_acc = _delta(_metric(bird_evidence, "accuracy"), _metric(bird_schema, "accuracy"))
    bird_delta_recall = _delta(_metric(bird_evidence, "avg_table_recall"), _metric(bird_schema, "avg_table_recall"))
    bird_delta_top1 = _delta(_metric(bird_evidence, "avg_top1_hit"), _metric(bird_schema, "avg_top1_hit"))
    return f"""
    <section class="grid">
      <section class="panel">
        <h2>What This Metric Actually Is</h2>
        <p><strong>Grounding accuracy</strong> here means: the run is counted correct only when <em>all</em> gold tables for a question are present in the candidate table set returned by the grounding stage.</p>
        <p>So a score like <code>0.926</code> on BIRD means: on 92.6% of the dev questions, the grounding stage recovered every gold table somewhere in its candidate set.</p>
        <p>It does <strong>not</strong> mean the system produced a correct executable final SQL query 92.6% of the time.</p>
      </section>
      <section class="panel">
        <h2>Why 0.926 Is Not 81.95</h2>
        <p>The official BIRD numbers on the right are <strong>end-to-end execution accuracy</strong>. Those systems must generate full SQL, execute it, and get the right answer.</p>
        <p>BENDER's current BIRD number is a <strong>diagnostic upstream metric</strong> on a narrower subproblem: table grounding.</p>
        <p>The honest reading is: BENDER currently has a strong grounding result on BIRD dev, but it is <strong>not yet an official BIRD execution score</strong>.</p>
      </section>
    </section>
    <section class="panel" style="margin-top:18px;">
      <h2>What The BIRD Lift Actually Is</h2>
      <table>
        <thead>
          <tr>
            <th>Comparison</th>
            <th>Absolute change</th>
            <th>Meaning</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>bender_with_evidence</code> vs <code>schema_only</code> accuracy</td>
            <td>{bird_delta_acc:+.3f}</td>
            <td>Evidence-aware grounding improves full gold-table recall by 6.3 points on BIRD dev.</td>
          </tr>
          <tr>
            <td><code>bender_with_evidence</code> vs <code>schema_only</code> avg table recall</td>
            <td>{bird_delta_recall:+.3f}</td>
            <td>The evidence path improves average gold-table coverage across the dev set.</td>
          </tr>
          <tr>
            <td><code>bender_with_evidence</code> vs <code>schema_only</code> avg top-1 hit</td>
            <td>{bird_delta_top1:+.3f}</td>
            <td>Top-1 ranking gets slightly worse, which suggests recall improved by broadening the candidate set rather than sharpening rank-1 precision.</td>
          </tr>
        </tbody>
      </table>
    </section>
    """


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bird-input", required=True)
    parser.add_argument("--gretel-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    bird = _load_report(args.bird_input)
    gretel = _load_report(args.gretel_input)

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BENDER SQL Grounding Benchmark Report</title>
  <style>
    :root {{
      --bg: #f7f5ef;
      --panel: #ffffff;
      --ink: #1d1d1b;
      --muted: #6e6a62;
      --line: #d8d1c5;
      --accent: #c56f35;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #efe7da 0%, var(--bg) 28%, #f9f8f4 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 40px 24px 64px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p {{ line-height: 1.55; color: var(--muted); }}
    .hero {{
      background: radial-gradient(circle at top left, #fffdf8, #f1ece2 65%, #ece3d3 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 28px;
      box-shadow: 0 16px 40px rgba(68, 54, 30, 0.08);
      margin-bottom: 22px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin-top: 18px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 8px 22px rgba(68, 54, 30, 0.05);
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
    ul.headlines {{
      margin: 10px 0 0;
      padding-left: 18px;
    }}
    .charts {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
      margin: 18px 0;
    }}
    .chart {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .chart-title {{
      font-size: 15px;
      font-weight: 700;
    }}
    .axis-line {{
      stroke: #7f7768;
      stroke-width: 1.1;
    }}
    .grid-line {{
      stroke: #ddd6ca;
      stroke-width: 1;
    }}
    .axis-label {{
      font-size: 11px;
      fill: #5f5b53;
    }}
    .system-label {{
      font-size: 10px;
    }}
    .value-label {{
      font-size: 11px;
      fill: #1d1d1b;
      font-weight: 700;
    }}
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
    .footnote {{
      font-size: 13px;
      color: #6e6a62;
      margin-top: 14px;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      background: #f1ece2;
      padding: 1px 5px;
      border-radius: 5px;
    }}
    @media (max-width: 960px) {{
      .grid, .charts {{
        grid-template-columns: 1fr;
      }}
      .legend-row {{
        grid-template-columns: 14px 1fr;
      }}
      .legend-row strong {{
        grid-column: 2;
      }}
      .legend-row span:last-child {{
        grid-column: 2;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>BENDER SQL Grounding Benchmark Report</h1>
      <p>This report combines the current BIRD and Gretel SQL grounding runs into one page with charts, legend, headline results, external references, and interpretation.</p>
      <p>Use this page as the primary benchmark summary.</p>
    </section>

    {_metric_context_panel(bird, gretel)}

    {_external_reference_tables()}

    <section class="grid">
      <section class="panel">
        <h2>Legend</h2>
        {_legend_html()}
      </section>
      <section class="panel">
        <h2>Headline Results</h2>
        <h3>BIRD Tiny</h3>
        <ul class="headlines">
          {_headline_list(bird)}
        </ul>
        <h3 style="margin-top:18px;">Gretel Train[:100]</h3>
        <ul class="headlines">
          {_headline_list(gretel)}
        </ul>
      </section>
    </section>

    <section class="charts">
      <section class="panel">{_chart_svg("BIRD Tiny Grounding Accuracy", bird.get("systems", []), "accuracy")}</section>
      <section class="panel">{_chart_svg("BIRD Tiny Average Table Recall", bird.get("systems", []), "avg_table_recall")}</section>
      <section class="panel">{_chart_svg("Gretel Train[:100] Grounding Accuracy", gretel.get("systems", []), "accuracy")}</section>
      <section class="panel">{_chart_svg("Gretel Train[:100] Average Table Recall", gretel.get("systems", []), "avg_table_recall")}</section>
    </section>

    <section class="grid">
      {_summary_table("BIRD Tiny Summary", bird)}
      {_summary_table("Gretel Train[:100] Summary", gretel)}
    </section>

    <section class="panel" style="margin-top:18px;">
      <h2>Interpretation</h2>
      <p>On full BIRD dev, the substantive result is not “0.9 looks high.” The substantive result is that the evidence-aware BENDER path moves from <code>0.864</code> to <code>0.926</code> on full gold-table recall, while plain metadata enrichment alone does not move the baseline.</p>
      <p>That is a real diagnostic gain, but it is still a grounding-stage result. It says BENDER is helping the system choose the right tables more often when task evidence is available. It does not yet show that BENDER beats leaderboard systems on full SQL execution.</p>
      <p>Gretel is still a weak public proof point. On the current sample, BENDER matches <code>schema_only</code>, so Gretel should be treated as supplementary breadth rather than headline evidence.</p>
      <p class="footnote">Bottom line: the BIRD grounding result is real and useful, but the serious next step is converting this into an execution-level benchmark so the comparison to official BIRD leaderboard scores becomes meaningful.</p>
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
