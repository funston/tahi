import math
from typing import List, Sequence


Matrix = List[List[float]]


def _transpose(matrix: Sequence[Sequence[float]]) -> Matrix:
    return [list(column) for column in zip(*matrix)]


def _matmul(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]) -> Matrix:
    right_t = _transpose(right)
    return [
        [sum(left_value * right_value for left_value, right_value in zip(row, column)) for column in right_t]
        for row in left
    ]


def _softmax(row: Sequence[float]) -> List[float]:
    if not row:
        return []
    max_value = max(row)
    exps = [math.exp(value - max_value) for value in row]
    total = sum(exps)
    if total == 0.0:
        return [0.0 for _ in exps]
    return [value / total for value in exps]


def _weighted_sum(weights: Sequence[Sequence[float]], values: Sequence[Sequence[float]]) -> Matrix:
    output: Matrix = []
    for row in weights:
        mixed_row = [0.0 for _ in range(len(values[0]))]
        for weight, value_row in zip(row, values):
            for index, value in enumerate(value_row):
                mixed_row[index] += weight * value
        output.append(mixed_row)
    return output


class KnowledgeAttention:
    """Dependency-free KAA prototype for small examples and tests."""

    def __init__(self, d_model: int):
        self.scale = d_model ** -0.5

    def forward(
        self,
        q: Sequence[Sequence[float]],
        k: Sequence[Sequence[float]],
        v: Sequence[Sequence[float]],
        kg: Sequence[Sequence[float]],
        vg: Sequence[Sequence[float]],
        context_gate: Sequence[float],
    ) -> Matrix:
        token_scores = _matmul(q, _transpose(k))
        graph_scores = _matmul(q, _transpose(kg))
        token_weights = [_softmax([value * self.scale for value in row]) for row in token_scores]
        graph_weights = [_softmax([value * self.scale for value in row]) for row in graph_scores]
        a_tok = _weighted_sum(token_weights, v)
        a_graph = _weighted_sum(graph_weights, vg)

        gate_logits = _softmax(context_gate[:2] if len(context_gate) >= 2 else [1.0, 1.0])
        rho_t, rho_g = gate_logits[0], gate_logits[1]
        return [
            [
                rho_t * token_value + rho_g * graph_value
                for token_value, graph_value in zip(token_row, graph_row)
            ]
            for token_row, graph_row in zip(a_tok, a_graph)
        ]
