# Bender Architecture Diagrams

All diagrams are authored in [Mermaid](https://mermaid.js.org/) (`.mmd`) and rendered to SVG.

| Diagram | Source | Rendered SVG |
|---------|--------|--------------|
| Value Proposition | [bender_value_proposition.mmd](bender_value_proposition.mmd) | [bender_value_proposition.svg](bender_value_proposition.svg) |
| Component Overview | [bender_component_overview.mmd](bender_component_overview.mmd) | [bender_component_overview.svg](bender_component_overview.svg) |
| Cognitive Lifecycle | [bender_cognitive_lifecycle.mmd](bender_cognitive_lifecycle.mmd) | [bender_cognitive_lifecycle.svg](bender_cognitive_lifecycle.svg) |
| Coprocessor Architecture | [bender_coprocessor_architecture.mmd](bender_coprocessor_architecture.mmd) | [bender_coprocessor_architecture.svg](bender_coprocessor_architecture.svg) |
| Integration Levels | [bender_integration_levels.mmd](bender_integration_levels.mmd) | [bender_integration_levels.svg](bender_integration_levels.svg) |
| Joint Architecture with RelationalAI | [bender_relationalai_joint_architecture.mmd](bender_relationalai_joint_architecture.mmd) | [bender_relationalai_joint_architecture.svg](bender_relationalai_joint_architecture.svg) |
| Bender vs. Alternatives | [bender_vs_alternatives.mmd](bender_vs_alternatives.mmd) | [bender_vs_alternatives.svg](bender_vs_alternatives.svg) |
| KAA Inference Loop | [kaa_inference_loop.mmd](kaa_inference_loop.mmd) | [kaa_inference_loop.svg](kaa_inference_loop.svg) |

## HTML Gallery

A styled HTML overview page is available at:

- [`docs/bender_visual_overview.html`](../docs/bender_visual_overview.html)

Open it in a browser to view all diagrams in one place.

## Rendering locally

To regenerate the SVGs after editing a `.mmd` file:

```bash
for f in diagrams/*.mmd; do
  npm exec --package=@mermaid-js/mermaid-cli -- mmdc -i "$f" -o "${f%.mmd}.svg"
done
```
