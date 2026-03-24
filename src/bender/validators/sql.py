from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol


class SQLExecutionEngine(Protocol):
    def execute(self, sql: str) -> tuple[list[dict[str, Any]], str | None]:
        ...


@dataclass
class SQLValidationResult:
    rows: list[dict[str, Any]]
    execution_error: str | None
    matched_gold: bool | None

    @property
    def execution_success(self) -> bool:
        return self.execution_error is None


class SQLResultMatcher:
    def __init__(self, *, gold_loader: Callable[[Path], list[dict[str, Any]]]):
        self.gold_loader = gold_loader

    def validate(
        self,
        *,
        rows: list[dict[str, Any]],
        execution_error: str | None,
        gold_paths: list[Path],
    ) -> SQLValidationResult:
        matched_gold = None
        if execution_error is None and gold_paths:
            matched_gold = self.matches_any_gold(rows, gold_paths)
        return SQLValidationResult(
            rows=rows,
            execution_error=execution_error,
            matched_gold=matched_gold,
        )

    def matches_any_gold(self, rows: list[dict[str, Any]], gold_paths: list[Path]) -> bool:
        actual = [{key.lower(): value for key, value in row.items()} for row in rows]
        for path in gold_paths:
            gold = [{key.lower(): value for key, value in row.items()} for row in self.gold_loader(path)]
            if self.rows_match(actual, gold):
                return True
        return False

    def rows_match(self, actual: list[dict[str, Any]], gold: list[dict[str, Any]]) -> bool:
        if len(actual) != len(gold):
            return False
        if not actual and not gold:
            return True
        for actual_row, gold_row in zip(actual, gold):
            if set(actual_row.keys()) != set(gold_row.keys()):
                return False
            for key in actual_row:
                if not self.values_match(actual_row[key], gold_row[key]):
                    return False
        return True

    def values_match(self, actual: Any, gold: Any) -> bool:
        if actual is None and (gold is None or gold == ""):
            return True
        actual_text = str(actual).strip()
        gold_text = str(gold).strip()
        if actual_text == gold_text:
            return True
        try:
            return abs(float(actual_text) - float(gold_text)) <= 1e-5
        except Exception:  # noqa: BLE001
            return False
