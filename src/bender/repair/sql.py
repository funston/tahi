from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from ..validators.sql import SQLExecutionEngine, SQLResultMatcher, SQLValidationResult


@dataclass
class SQLRepairAttempt:
    label: str
    sql: str
    execution_error: str | None
    matched_gold: bool | None
    rows_preview: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SQLRepairOutcome:
    sql: str
    validation: SQLValidationResult
    attempts: list[SQLRepairAttempt]


class SQLRepairLoop:
    def __init__(self, *, engine: SQLExecutionEngine, matcher: SQLResultMatcher):
        self.engine = engine
        self.matcher = matcher

    def run(
        self,
        *,
        initial_sql: str,
        gold_paths: list[Path],
        repair_candidates: Iterable[tuple[str, str]],
    ) -> SQLRepairOutcome:
        rows, execution_error = self.engine.execute(initial_sql)
        validation = self.matcher.validate(
            rows=rows,
            execution_error=execution_error,
            gold_paths=gold_paths,
        )
        attempts: list[SQLRepairAttempt] = []
        if validation.execution_success and (not gold_paths or validation.matched_gold is not False):
            return SQLRepairOutcome(sql=initial_sql, validation=validation, attempts=attempts)

        final_sql = initial_sql
        final_validation = validation
        for attempt_sql, label in repair_candidates:
            rows, execution_error = self.engine.execute(attempt_sql)
            attempt_validation = self.matcher.validate(
                rows=rows,
                execution_error=execution_error,
                gold_paths=gold_paths,
            )
            attempts.append(
                SQLRepairAttempt(
                    label=label,
                    sql=attempt_sql,
                    execution_error=attempt_validation.execution_error,
                    matched_gold=attempt_validation.matched_gold,
                    rows_preview=attempt_validation.rows[:5],
                )
            )
            if attempt_validation.execution_success and (
                not gold_paths or attempt_validation.matched_gold is not False
            ):
                final_sql = attempt_sql
                final_validation = attempt_validation
                break
        return SQLRepairOutcome(sql=final_sql, validation=final_validation, attempts=attempts)
