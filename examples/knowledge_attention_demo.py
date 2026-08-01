from octo.knowledge_attention import KnowledgeAttention

layer = KnowledgeAttention(d_model=4)
q = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
]
k = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
]
v = [
    [0.9, 0.1, 0.0, 0.0],
    [0.2, 0.8, 0.0, 0.0],
]
kg = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
]
vg = [
    [0.0, 0.7, 0.3, 0.0],
    [0.1, 0.1, 0.8, 0.0],
]
context_gate = [0.35, 0.65]
out = layer.forward(q, k, v, kg, vg, context_gate)
print(out)
