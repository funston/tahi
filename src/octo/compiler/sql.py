from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..repair.sql import SQLRepairLoop, SQLRepairOutcome
from ..validators.sql import SQLExecutionEngine, SQLResultMatcher


class SQLCompilerPipeline:
    def __init__(self, *, engine: SQLExecutionEngine, matcher: SQLResultMatcher):
        self.engine = engine
        self.matcher = matcher
        self.repair_loop = SQLRepairLoop(engine=engine, matcher=matcher)

    def compile(
        self,
        *,
        initial_sql: str,
        gold_paths: list[Path] | None = None,
        repair_candidates: Iterable[tuple[str, str]] = (),
    ) -> SQLRepairOutcome:
        return self.repair_loop.run(
            initial_sql=initial_sql,
            gold_paths=gold_paths or [],
            repair_candidates=repair_candidates,
        )
