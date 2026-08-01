# Octo Architecture Diagrams

All diagrams are authored in [Mermaid](https://mermaid.js.org/) (`.mmd`) and rendered to SVG.

| Diagram | Source | Rendered SVG |
|---------|--------|--------------|
| Value Proposition | [octo_value_proposition.mmd](octo_value_proposition.mmd) | [octo_value_proposition.svg](octo_value_proposition.svg) |
| Component Overview | [octo_component_overview.mmd](octo_component_overview.mmd) | [octo_component_overview.svg](octo_component_overview.svg) |
| Cognitive Lifecycle | [octo_cognitive_lifecycle.mmd](octo_cognitive_lifecycle.mmd) | [octo_cognitive_lifecycle.svg](octo_cognitive_lifecycle.svg) |
| Coprocessor Architecture | [octo_coprocessor_architecture.mmd](octo_coprocessor_architecture.mmd) | [octo_coprocessor_architecture.svg](octo_coprocessor_architecture.svg) |
| Integration Levels | [octo_integration_levels.mmd](octo_integration_levels.mmd) | [octo_integration_levels.svg](octo_integration_levels.svg) |
| Joint Architecture with RelationalAI | [octo_relationalai_joint_architecture.mmd](octo_relationalai_joint_architecture.mmd) | [octo_relationalai_joint_architecture.svg](octo_relationalai_joint_architecture.svg) |
| Octo vs. Alternatives | [octo_vs_alternatives.mmd](octo_vs_alternatives.mmd) | [octo_vs_alternatives.svg](octo_vs_alternatives.svg) |
| KAA Inference Loop | [kaa_inference_loop.mmd](kaa_inference_loop.mmd) | [kaa_inference_loop.svg](kaa_inference_loop.svg) |

## HTML Gallery

A styled HTML overview page is available at:

- [`docs/octo_gardens_visual_overview.html`](../docs/octo_gardens_visual_overview.html)

Open it in a browser to view all diagrams in one place.

## Rendering locally

To regenerate the SVGs after editing a `.mmd` file:

```bash
for f in diagrams/*.mmd; do
 npm exec --package=@mermaid-js/mermaid-cli -- mmdc -i "$f" -o "${f%.mmd}.svg"
done
```
