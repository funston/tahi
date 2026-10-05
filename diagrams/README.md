# Tahi Architecture Diagrams

All diagrams are authored in [Mermaid](https://mermaid.js.org/) (`.mmd`) and rendered to SVG.

| Diagram | Source | Rendered SVG |
|---------|--------|--------------|
| Value Proposition | [tahi_value_proposition.mmd](tahi_value_proposition.mmd) | [tahi_value_proposition.svg](tahi_value_proposition.svg) |
| Component Overview | [tahi_component_overview.mmd](tahi_component_overview.mmd) | [tahi_component_overview.svg](tahi_component_overview.svg) |
| Cognitive Lifecycle | [tahi_cognitive_lifecycle.mmd](tahi_cognitive_lifecycle.mmd) | [tahi_cognitive_lifecycle.svg](tahi_cognitive_lifecycle.svg) |
| Coprocessor Architecture | [tahi_coprocessor_architecture.mmd](tahi_coprocessor_architecture.mmd) | [tahi_coprocessor_architecture.svg](tahi_coprocessor_architecture.svg) |
| Integration Levels | [tahi_integration_levels.mmd](tahi_integration_levels.mmd) | [tahi_integration_levels.svg](tahi_integration_levels.svg) |
| Joint Architecture with RelationalAI | [tahi_relationalai_joint_architecture.mmd](tahi_relationalai_joint_architecture.mmd) | [tahi_relationalai_joint_architecture.svg](tahi_relationalai_joint_architecture.svg) |
| Tahi vs. Alternatives | [tahi_vs_alternatives.mmd](tahi_vs_alternatives.mmd) | [tahi_vs_alternatives.svg](tahi_vs_alternatives.svg) |
| KAA Inference Loop | [kaa_inference_loop.mmd](kaa_inference_loop.mmd) | [kaa_inference_loop.svg](kaa_inference_loop.svg) |

## HTML Gallery

A styled HTML overview page is available at:

- [`docs/tahi_visual_overview.html`](../docs/tahi_visual_overview.html)

Open it in a browser to view all diagrams in one place.

## Rendering locally

To regenerate the SVGs after editing a `.mmd` file:

```bash
for f in diagrams/*.mmd; do
 npm exec --package=@mermaid-js/mermaid-cli -- mmdc -i "$f" -o "${f%.mmd}.svg"
done
```
