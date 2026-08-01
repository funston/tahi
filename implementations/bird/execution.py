"""
BIRD Execution Benchmark

This module implements end-to-end SQL execution benchmarking for BIRD tasks.

The execution benchmark measures:
- Execution accuracy (result set matches gold)
- Invalid SQL rate (parse/execution errors)
- Repair effectiveness (multi-candidate recovery)

Architecture:
- Uses OCTO coprocessor for grounding (candidate tables, constraints)
- Generates SQL candidates via LLM or heuristics
- Executes on SQLite
- Validates against gold result sets
- Supports repair loops

This is BIRD-specific. Generic SQL execution primitives live in src/octo/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from octo.benchmarking import BenchmarkCaseResult, benchmark_report_to_dict, summarize_system_results
from octo.repair.sql import SQLRepairLoop
from octo.validators.sql import SQLResultMatcher

from .bird import (
    BirdExecutionPacket,
    BirdSQLCandidate,
    BirdSQLCandidateGenerator,
    BirdSQLiteExecutionEngine,
    BirdTask,
    SQLSchemaSnapshot,
    _extract_sql,
    _infer_gold_tables_from_sql,
    _normalize_identifier,
)
from .sql_generator_coprocessor import (
    EnsembleSQLGeneratorCoprocessor,
    SQLGeneratorCoprocessor,
    as_coprocessor,
)


@dataclass
class BirdExecutionResult:
    """Result of executing SQL on a single BIRD task"""

    task_id: str
    db_id: str
    question: str
    evidence: str
    difficulty: str

    # Grounding (from OCTO coprocessor)
    candidate_tables: list[str]
    candidate_join_path: list[str]
    gold_tables: list[str]
    table_recall: float | None

    # Execution
    generated_sql: str
    execution_success: bool
    execution_error: str | None
    matched_gold: bool | None

    # Candidates and repair
    sql_candidates: list[dict[str, Any]] = field(default_factory=list)
    repair_attempts: list[dict[str, Any]] = field(default_factory=list)

    # Metadata
    strategy: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "db_id": self.db_id,
            "question": self.question,
            "evidence": self.evidence,
            "difficulty": self.difficulty,
            "candidate_tables": self.candidate_tables,
            "candidate_join_path": self.candidate_join_path,
            "gold_tables": self.gold_tables,
            "table_recall": self.table_recall,
            "generated_sql": self.generated_sql,
            "execution_success": self.execution_success,
            "execution_error": self.execution_error,
            "matched_gold": self.matched_gold,
            "sql_candidates": self.sql_candidates,
            "repair_attempts": self.repair_attempts,
            "strategy": self.strategy,
            "metadata": self.metadata,
        }


@dataclass
class BirdExecutionAdapter:
    """
    Adapter that runs OCTO grounding + SQL generation + execution for BIRD tasks.

    This combines:
    1. OCTO coprocessor (grounding)
    2. One or more SQL generator coprocessors (generation)
    3. SQLite execution engine (execution)
    4. Result validation (matching)

    Multiple SQL generator coprocessors can be composed into an ensemble,
    enabling "agent/tool" style generation where a heuristic, an LLM, and a
    repair coprocessor each contribute candidates.
    """

    snapshots_by_db: dict[str, SQLSchemaSnapshot]
    db_paths_by_db: dict[str, Path]
    grounding_adapter: Any  # BirdBenchmarkAdapter from bird.py
    sql_coprocessors: list[SQLGeneratorCoprocessor] = field(default_factory=list)
    sql_generator: BirdSQLCandidateGenerator | None = None  # deprecated, use sql_coprocessors
    use_repair: bool = False
    max_candidates: int = 1

    def __post_init__(self) -> None:
        # Backward compatibility: lift a legacy single generator into a single-item
        # coprocessor list. New code should pass sql_coprocessors directly.
        if self.sql_generator is not None:
            self.sql_coprocessors = [
                as_coprocessor(self.sql_generator),
                *self.sql_coprocessors,
            ]
            self.sql_generator = None
        if not self.sql_coprocessors:
            raise ValueError(
                "BirdExecutionAdapter requires at least one SQL generator coprocessor"
            )

    def _generation_strategy(self) -> str:
        if len(self.sql_coprocessors) == 1:
            return self.sql_coprocessors[0].name
        return EnsembleSQLGeneratorCoprocessor(self.sql_coprocessors).name

    def run_task(self, task: BirdTask) -> BirdExecutionResult:
        """Execute a single BIRD task end-to-end"""

        # Step 1: OCTO grounding
        grounding_result = self.grounding_adapter.run_task(task)
        candidate_tables = grounding_result.get("candidate_tables", [])
        candidate_join_path = grounding_result.get("candidate_join_path", [])
        table_recall = grounding_result.get("table_recall")
        gold_tables = grounding_result.get("gold_tables", [])

        # Step 2: Build execution packet
        snapshot = self.snapshots_by_db[task.db_id]
        packet = BirdExecutionPacket(
            task_id=task.task_id,
            db_id=task.db_id,
            question=task.question,
            evidence=task.evidence,
            candidate_tables=candidate_tables,
            snapshot=snapshot,
            include_evidence=self.grounding_adapter.include_evidence,
        )

        # Step 3: Generate SQL candidates via composed coprocessors
        if len(self.sql_coprocessors) == 1:
            candidates = self.sql_coprocessors[0].generate(
                packet, max_candidates=self.max_candidates
            )
        else:
            ensemble = EnsembleSQLGeneratorCoprocessor(self.sql_coprocessors)
            candidates = ensemble.generate(packet, max_candidates=self.max_candidates)

        if not candidates:
            return BirdExecutionResult(
                task_id=task.task_id,
                db_id=task.db_id,
                question=task.question,
                evidence=task.evidence,
                difficulty=task.difficulty,
                candidate_tables=candidate_tables,
                candidate_join_path=candidate_join_path,
                gold_tables=gold_tables,
                table_recall=table_recall,
                generated_sql="",
                execution_success=False,
                execution_error="No SQL candidates generated",
                matched_gold=None,
                strategy="no_candidates",
            )

        # Step 4: Execute first candidate
        primary_candidate = candidates[0]
        db_path = self.db_paths_by_db[task.db_id]
        engine = BirdSQLiteExecutionEngine(db_path)
        rows, execution_error = engine.execute(primary_candidate.sql)

        # Step 5: Validate against gold (if available)
        matched_gold = None
        if task.gold_sql and execution_error is None:
            # Execute gold SQL to get expected results
            gold_rows, gold_error = engine.execute(task.gold_sql)
            if gold_error is None:
                matched_gold = self._rows_match(rows, gold_rows)

        # Step 6: Repair loop (if enabled and needed)
        repair_attempts: list[dict[str, Any]] = []
        final_sql = primary_candidate.sql
        final_success = execution_error is None
        final_matched = matched_gold

        if self.use_repair and (not final_success or matched_gold is False):
            for i, candidate in enumerate(candidates[1:], start=1):
                rows, error = engine.execute(candidate.sql)
                success = error is None
                matched = None
                if success and task.gold_sql:
                    gold_rows, gold_error = engine.execute(task.gold_sql)
                    if gold_error is None:
                        matched = self._rows_match(rows, gold_rows)

                repair_attempts.append({
                    "candidate_index": i,
                    "sql": candidate.sql,
                    "strategy": candidate.strategy,
                    "execution_success": success,
                    "execution_error": error,
                    "matched_gold": matched,
                })

                # Stop if we found a working candidate
                if success and (matched is not False or matched is None):
                    final_sql = candidate.sql
                    final_success = success
                    final_matched = matched
                    break

        return BirdExecutionResult(
            task_id=task.task_id,
            db_id=task.db_id,
            question=task.question,
            evidence=task.evidence,
            difficulty=task.difficulty,
            candidate_tables=candidate_tables,
            candidate_join_path=candidate_join_path,
            gold_tables=gold_tables,
            table_recall=table_recall,
            generated_sql=final_sql,
            execution_success=final_success,
            execution_error=execution_error if not final_success else None,
            matched_gold=final_matched,
            sql_candidates=[
                {
                    "sql": c.sql,
                    "strategy": c.strategy,
                    "rationale": c.rationale,
                }
                for c in candidates
            ],
            repair_attempts=repair_attempts,
            strategy=self._generation_strategy(),
            metadata={
                **grounding_result.get("metadata", {}),
                "primary_candidate_strategy": primary_candidate.strategy,
                "candidate_coprocessors": [
                    c.metadata.get("coprocessor", "unknown") for c in candidates
                ],
            },
        )

    def _rows_match(self, actual: list[dict[str, Any]], gold: list[dict[str, Any]]) -> bool:
        """Simple result set matching"""
        if len(actual) != len(gold):
            return False
        if not actual and not gold:
            return True

        # Normalize keys to lowercase
        actual_normalized = [{k.lower(): v for k, v in row.items()} for row in actual]
        gold_normalized = [{k.lower(): v for k, v in row.items()} for row in gold]

        for actual_row, gold_row in zip(actual_normalized, gold_normalized):
            if set(actual_row.keys()) != set(gold_row.keys()):
                return False
            for key in actual_row:
                if not self._values_match(actual_row[key], gold_row[key]):
                    return False
        return True

    def _values_match(self, actual: Any, gold: Any) -> bool:
        """Value comparison with numeric tolerance"""
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


@dataclass
class BirdExecutionBenchmarkRunner:
    """
    Runs execution benchmark across multiple systems for A/B comparison.

    Compares:
    - naive_baseline: No OCTO, simple heuristic SQL
    - rag_baseline: Full schema, no OCTO grounding
    - octo_grounding: OCTO candidate tables, no evidence
    - octo_with_evidence: OCTO + task evidence
    - octo_with_repair: Above + multi-candidate repair
    """

    naive_adapter: BirdExecutionAdapter
    rag_adapter: BirdExecutionAdapter
    octo_adapter: BirdExecutionAdapter
    evidence_adapter: BirdExecutionAdapter | None = None
    repair_adapter: BirdExecutionAdapter | None = None

    def run(self, tasks: list[BirdTask]) -> dict[str, Any]:
        """Run execution benchmark across all systems"""

        systems: dict[str, list[BenchmarkCaseResult]] = {}

        print(f"Running execution benchmark on {len(tasks)} tasks...")

        # Run each system
        for system_name, adapter in [
            ("naive_baseline", self.naive_adapter),
            ("rag_baseline", self.rag_adapter),
            ("octo_grounding", self.octo_adapter),
        ]:
            print(f"\nRunning {system_name}...")
            results = []
            for i, task in enumerate(tasks, 1):
                if i % 10 == 0:
                    print(f" {i}/{len(tasks)} tasks...")
                try:
                    exec_result = adapter.run_task(task)
                    results.append(
                        BenchmarkCaseResult(
                            case_id=task.task_id,
                            system=system_name,
                            correct=bool(exec_result.matched_gold is True),
                            metrics={
                                "execution_success": exec_result.execution_success,
                                "matched_gold": exec_result.matched_gold,
                                "table_recall": exec_result.table_recall,
                                "has_sql": bool(exec_result.generated_sql),
                            },
                            detail=exec_result.to_dict(),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f" Error on {task.task_id}: {exc}")
                    results.append(
                        BenchmarkCaseResult(
                            case_id=task.task_id,
                            system=system_name,
                            correct=False,
                            metrics={
                                "execution_success": False,
                                "matched_gold": None,
                                "table_recall": None,
                                "has_sql": False,
                            },
                            detail={"error": str(exc)},
                        )
                    )
            systems[system_name] = results

        # Optional: evidence system
        if self.evidence_adapter:
            print("\nRunning octo_with_evidence...")
            results = []
            for i, task in enumerate(tasks, 1):
                if i % 10 == 0:
                    print(f" {i}/{len(tasks)} tasks...")
                try:
                    exec_result = self.evidence_adapter.run_task(task)
                    results.append(
                        BenchmarkCaseResult(
                            case_id=task.task_id,
                            system="octo_with_evidence",
                            correct=bool(exec_result.matched_gold is True),
                            metrics={
                                "execution_success": exec_result.execution_success,
                                "matched_gold": exec_result.matched_gold,
                                "table_recall": exec_result.table_recall,
                                "has_sql": bool(exec_result.generated_sql),
                            },
                            detail=exec_result.to_dict(),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        BenchmarkCaseResult(
                            case_id=task.task_id,
                            system="octo_with_evidence",
                            correct=False,
                            metrics={
                                "execution_success": False,
                                "matched_gold": None,
                                "table_recall": None,
                                "has_sql": False,
                            },
                            detail={"error": str(exc)},
                        )
                    )
            systems["octo_with_evidence"] = results

        # Optional: repair system
        if self.repair_adapter:
            print("\nRunning octo_with_repair...")
            results = []
            for i, task in enumerate(tasks, 1):
                if i % 10 == 0:
                    print(f" {i}/{len(tasks)} tasks...")
                try:
                    exec_result = self.repair_adapter.run_task(task)
                    results.append(
                        BenchmarkCaseResult(
                            case_id=task.task_id,
                            system="octo_with_repair",
                            correct=bool(exec_result.matched_gold is True),
                            metrics={
                                "execution_success": exec_result.execution_success,
                                "matched_gold": exec_result.matched_gold,
                                "table_recall": exec_result.table_recall,
                                "has_sql": bool(exec_result.generated_sql),
                                "repair_attempts": len(exec_result.repair_attempts),
                            },
                            detail=exec_result.to_dict(),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        BenchmarkCaseResult(
                            case_id=task.task_id,
                            system="octo_with_repair",
                            correct=False,
                            metrics={
                                "execution_success": False,
                                "matched_gold": None,
                                "table_recall": None,
                                "has_sql": False,
                                "repair_attempts": 0,
                            },
                            detail={"error": str(exc)},
                        )
                    )
            systems["octo_with_repair"] = results

        # Summarize results
        summaries = []
        for system_name, results in systems.items():
            metric_names = ["execution_success", "matched_gold", "table_recall"]
            if system_name == "octo_with_repair":
                metric_names.append("repair_attempts")
            summaries.append(
                summarize_system_results(system_name, results, metric_names=metric_names)
            )

        # Build report
        return benchmark_report_to_dict(
            benchmark_name="bird_execution",
            summaries=summaries,
            results_by_system=systems,
        )
