You are continuing development of the OCTO research repo.

Current direction:
- OCTO is a true cognitive coprocessor for LLMs.
- The base LLM is primarily a perception and language interface.
- World models, graph reasoning, and simulation run alongside inference.
- We want to avoid full retraining of the base model.

Immediate goals:
1. Clean up the mathematical notation in docs/kaa_math.md.
2. Expand the runtime to support a CognitiveState packet.
3. Add provenance tracking to all reasoning paths.
4. Add a legal reasoning example in examples/.
5. Add tests for the planner, rule engine, and knowledge attention prototype.
6. Propose a hidden-state fusion interface for open-weight models.

Be explicit about where the current code is only a placeholder versus where the architecture makes a real claim.
