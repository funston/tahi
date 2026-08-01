from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass
class EvalCase:
    name: str
    query: str
    mode: str = "coprocessor"
    trace: bool = True
    hidden_state: Optional[Sequence[float]] = None
    decode_step: int = 0
    expected_entities: Sequence[str] = field(default_factory=tuple)
    expected_relations: Sequence[tuple[str, str, str]] = field(default_factory=tuple)
    expected_constraints: Mapping[str, Any] = field(default_factory=dict)
    expected_hypothesis_substrings: Sequence[str] = field(default_factory=tuple)
    expected_retrievals: Sequence[str] = field(default_factory=tuple)
    expected_provenance_refs: Sequence[str] = field(default_factory=tuple)
    expected_integration: Optional[str] = None
    min_graph_weight: Optional[float] = None


@dataclass
class EvalCheck:
    name: str
    passed: bool
    detail: str


@dataclass
class EvalCaseResult:
    case_name: str
    passed: bool
    wall_time_ms: float
    checks: List[EvalCheck]
    raw_result: Dict[str, Any]


@dataclass
class EvalSuiteResult:
    suite_name: str
    passed: bool
    pass_rate: float
    total_cases: int
    passed_cases: int
    total_checks: int
    passed_checks: int
    avg_wall_time_ms: float
    cases: List[EvalCaseResult]


@dataclass
class ComparisonCase:
    name: str
    query: str
    mode: str = "coprocessor"
    trace: bool = True
    hidden_state: Optional[Sequence[float]] = None
    decode_step: int = 0
    expected_entity_gain: Optional[int] = None
    expected_retrieval_gain: Optional[int] = None
    expected_provenance_gain: Optional[int] = None
    required_with_octo_constraints: Mapping[str, Any] = field(default_factory=dict)
    required_with_octo_hypothesis_substrings: Sequence[str] = field(default_factory=tuple)
    forbidden_without_octo_hypothesis_substrings: Sequence[str] = field(default_factory=tuple)
    expected_with_octo_integration: Optional[str] = None


@dataclass
class ComparisonCaseResult:
    case_name: str
    passed: bool
    checks: List[EvalCheck]
    with_octo_wall_time_ms: float
    without_octo_wall_time_ms: float
    with_octo_result: Dict[str, Any]
    without_octo_result: Dict[str, Any]


@dataclass
class ComparisonSuiteResult:
    suite_name: str
    passed: bool
    pass_rate: float
    total_cases: int
    passed_cases: int
    total_checks: int
    passed_checks: int
    cases: List[ComparisonCaseResult]


def _normalize_strings(values: Iterable[str]) -> set[str]:
    return {value.strip().lower() for value in values}


def _contains_substrings(texts: Iterable[str], substrings: Iterable[str]) -> list[EvalCheck]:
    joined = "\n".join(texts).lower()
    checks: list[EvalCheck] = []
    for substring in substrings:
        needle = substring.lower()
        checks.append(
            EvalCheck(
                name=f"hypothesis_contains:{substring}",
                passed=needle in joined,
                detail=f"Expected hypothesis text containing '{substring}'.",
            )
        )
    return checks


def evaluate_case(model: Any, case: EvalCase) -> EvalCaseResult:
    started = time.perf_counter()
    raw_result = model.ask(
        case.query,
        mode=case.mode,
        trace=case.trace,
        hidden_state=case.hidden_state,
        decode_step=case.decode_step,
    )
    wall_time_ms = (time.perf_counter() - started) * 1000.0

    checks: list[EvalCheck] = []

    if case.expected_entities:
        actual_entities = _normalize_strings(raw_result.get("entities", []))
        for entity in case.expected_entities:
            checks.append(
                EvalCheck(
                    name=f"entity:{entity}",
                    passed=entity.lower() in actual_entities,
                    detail=f"Expected entity '{entity}' in active entity set.",
                )
            )

    if case.expected_relations:
        actual_relations = {
            (
                item.get("source", "").lower(),
                item.get("relation", "").lower(),
                item.get("target", "").lower(),
            )
            for item in raw_result.get("relations", [])
        }
        for source, relation, target in case.expected_relations:
            checks.append(
                EvalCheck(
                    name=f"relation:{source}:{relation}:{target}",
                    passed=(source.lower(), relation.lower(), target.lower()) in actual_relations,
                    detail=f"Expected relation ({source}, {relation}, {target}).",
                )
            )

    if case.expected_constraints:
        actual_constraints = raw_result.get("constraints", {})
        for key, expected_value in case.expected_constraints.items():
            checks.append(
                EvalCheck(
                    name=f"constraint:{key}",
                    passed=actual_constraints.get(key) == expected_value,
                    detail=f"Expected constraint '{key}' to equal {expected_value!r}.",
                )
            )

    if case.expected_hypothesis_substrings:
        hypothesis_texts = [item.get("text", "") for item in raw_result.get("hypotheses", [])]
        checks.extend(_contains_substrings(hypothesis_texts, case.expected_hypothesis_substrings))

    if case.expected_retrievals:
        actual_retrievals = _normalize_strings(
            item.get("node_id", "") for item in raw_result.get("retrievals", [])
        )
        for node_id in case.expected_retrievals:
            checks.append(
                EvalCheck(
                    name=f"retrieval:{node_id}",
                    passed=node_id.lower() in actual_retrievals,
                    detail=f"Expected retrieval '{node_id}'.",
                )
            )

    if case.expected_provenance_refs:
        actual_refs = _normalize_strings(
            item.get("reference", "") for item in raw_result.get("provenance", [])
        )
        for reference in case.expected_provenance_refs:
            checks.append(
                EvalCheck(
                    name=f"provenance:{reference}",
                    passed=reference.lower() in actual_refs,
                    detail=f"Expected provenance reference '{reference}'.",
                )
            )

    if case.expected_integration is not None:
        actual_integration = raw_result.get("control_packet", {}).get("integration")
        checks.append(
            EvalCheck(
                name="integration",
                passed=actual_integration == case.expected_integration,
                detail=f"Expected integration '{case.expected_integration}', got '{actual_integration}'.",
            )
        )

    if case.min_graph_weight is not None:
        actual_graph_weight = raw_result.get("fusion", {}).get("graph_weight")
        passed = actual_graph_weight is not None and actual_graph_weight >= case.min_graph_weight
        checks.append(
            EvalCheck(
                name="min_graph_weight",
                passed=passed,
                detail=(
                    f"Expected graph weight >= {case.min_graph_weight}, "
                    f"got {actual_graph_weight}."
                ),
            )
        )

    passed = all(check.passed for check in checks) if checks else True
    return EvalCaseResult(
        case_name=case.name,
        passed=passed,
        wall_time_ms=wall_time_ms,
        checks=checks,
        raw_result=raw_result,
    )


def evaluate_suite(suite_name: str, model: Any, cases: Sequence[EvalCase]) -> EvalSuiteResult:
    results = [evaluate_case(model, case) for case in cases]
    total_checks = sum(len(case.checks) for case in results)
    passed_checks = sum(sum(1 for check in case.checks if check.passed) for case in results)
    passed_cases = sum(1 for case in results if case.passed)
    avg_wall_time_ms = (
        sum(case.wall_time_ms for case in results) / len(results) if results else 0.0
    )
    pass_rate = (passed_cases / len(results)) if results else 1.0
    return EvalSuiteResult(
        suite_name=suite_name,
        passed=passed_cases == len(results),
        pass_rate=pass_rate,
        total_cases=len(results),
        passed_cases=passed_cases,
        total_checks=total_checks,
        passed_checks=passed_checks,
        avg_wall_time_ms=avg_wall_time_ms,
        cases=results,
    )


def suite_to_dict(result: EvalSuiteResult) -> Dict[str, Any]:
    return {
        "suite_name": result.suite_name,
        "passed": result.passed,
        "pass_rate": result.pass_rate,
        "total_cases": result.total_cases,
        "passed_cases": result.passed_cases,
        "total_checks": result.total_checks,
        "passed_checks": result.passed_checks,
        "avg_wall_time_ms": round(result.avg_wall_time_ms, 3),
        "cases": [
            {
                "case_name": case.case_name,
                "passed": case.passed,
                "wall_time_ms": round(case.wall_time_ms, 3),
                "checks": [
                    {
                        "name": check.name,
                        "passed": check.passed,
                        "detail": check.detail,
                    }
                    for check in case.checks
                ],
                "raw_result": case.raw_result,
            }
            for case in result.cases
        ],
    }


def evaluate_comparison_case(
    with_octo_model: Any,
    without_octo_model: Any,
    case: ComparisonCase,
) -> ComparisonCaseResult:
    with_started = time.perf_counter()
    with_result = with_octo_model.ask(
        case.query,
        mode=case.mode,
        trace=case.trace,
        hidden_state=case.hidden_state,
        decode_step=case.decode_step,
    )
    with_wall_time_ms = (time.perf_counter() - with_started) * 1000.0

    without_started = time.perf_counter()
    without_result = without_octo_model.ask(
        case.query,
        mode=case.mode,
        trace=case.trace,
        hidden_state=case.hidden_state,
        decode_step=case.decode_step,
    )
    without_wall_time_ms = (time.perf_counter() - without_started) * 1000.0

    checks: list[EvalCheck] = []

    if case.expected_entity_gain is not None:
        entity_gain = len(with_result.get("entities", [])) - len(without_result.get("entities", []))
        checks.append(
            EvalCheck(
                name="entity_gain",
                passed=entity_gain >= case.expected_entity_gain,
                detail=f"Expected entity gain >= {case.expected_entity_gain}, got {entity_gain}.",
            )
        )

    if case.expected_retrieval_gain is not None:
        retrieval_gain = len(with_result.get("retrievals", [])) - len(
            without_result.get("retrievals", [])
        )
        checks.append(
            EvalCheck(
                name="retrieval_gain",
                passed=retrieval_gain >= case.expected_retrieval_gain,
                detail=(
                    f"Expected retrieval gain >= {case.expected_retrieval_gain}, "
                    f"got {retrieval_gain}."
                ),
            )
        )

    if case.expected_provenance_gain is not None:
        provenance_gain = len(with_result.get("provenance", [])) - len(
            without_result.get("provenance", [])
        )
        checks.append(
            EvalCheck(
                name="provenance_gain",
                passed=provenance_gain >= case.expected_provenance_gain,
                detail=(
                    f"Expected provenance gain >= {case.expected_provenance_gain}, "
                    f"got {provenance_gain}."
                ),
            )
        )

    if case.required_with_octo_constraints:
        with_constraints = with_result.get("constraints", {})
        for key, expected_value in case.required_with_octo_constraints.items():
            checks.append(
                EvalCheck(
                    name=f"with_octo_constraint:{key}",
                    passed=with_constraints.get(key) == expected_value,
                    detail=(
                        f"Expected with-BENDER constraint '{key}' to equal "
                        f"{expected_value!r}."
                    ),
                )
            )

    if case.required_with_octo_hypothesis_substrings:
        with_hypotheses = [item.get("text", "") for item in with_result.get("hypotheses", [])]
        checks.extend(
            _contains_substrings(
                with_hypotheses, case.required_with_octo_hypothesis_substrings
            )
        )

    if case.forbidden_without_octo_hypothesis_substrings:
        without_joined = "\n".join(
            item.get("text", "") for item in without_result.get("hypotheses", [])
        ).lower()
        for substring in case.forbidden_without_octo_hypothesis_substrings:
            checks.append(
                EvalCheck(
                    name=f"without_octo_absent:{substring}",
                    passed=substring.lower() not in without_joined,
                    detail=f"Expected baseline output to omit '{substring}'.",
                )
            )

    if case.expected_with_octo_integration is not None:
        integration = with_result.get("control_packet", {}).get("integration")
        checks.append(
            EvalCheck(
                name="with_octo_integration",
                passed=integration == case.expected_with_octo_integration,
                detail=(
                    f"Expected with-BENDER integration '{case.expected_with_octo_integration}', "
                    f"got '{integration}'."
                ),
            )
        )

    passed = all(check.passed for check in checks) if checks else True
    return ComparisonCaseResult(
        case_name=case.name,
        passed=passed,
        checks=checks,
        with_octo_wall_time_ms=with_wall_time_ms,
        without_octo_wall_time_ms=without_wall_time_ms,
        with_octo_result=with_result,
        without_octo_result=without_result,
    )


def evaluate_comparison_suite(
    suite_name: str,
    with_octo_model: Any,
    without_octo_model: Any,
    cases: Sequence[ComparisonCase],
) -> ComparisonSuiteResult:
    results = [
        evaluate_comparison_case(with_octo_model, without_octo_model, case)
        for case in cases
    ]
    total_checks = sum(len(case.checks) for case in results)
    passed_checks = sum(sum(1 for check in case.checks if check.passed) for case in results)
    passed_cases = sum(1 for case in results if case.passed)
    pass_rate = (passed_cases / len(results)) if results else 1.0
    return ComparisonSuiteResult(
        suite_name=suite_name,
        passed=passed_cases == len(results),
        pass_rate=pass_rate,
        total_cases=len(results),
        passed_cases=passed_cases,
        total_checks=total_checks,
        passed_checks=passed_checks,
        cases=results,
    )


def comparison_suite_to_dict(result: ComparisonSuiteResult) -> Dict[str, Any]:
    return {
        "suite_name": result.suite_name,
        "passed": result.passed,
        "pass_rate": result.pass_rate,
        "total_cases": result.total_cases,
        "passed_cases": result.passed_cases,
        "total_checks": result.total_checks,
        "passed_checks": result.passed_checks,
        "cases": [
            {
                "case_name": case.case_name,
                "passed": case.passed,
                "with_octo_wall_time_ms": round(case.with_octo_wall_time_ms, 3),
                "without_octo_wall_time_ms": round(case.without_octo_wall_time_ms, 3),
                "checks": [
                    {
                        "name": check.name,
                        "passed": check.passed,
                        "detail": check.detail,
                    }
                    for check in case.checks
                ],
                "with_octo_result": case.with_octo_result,
                "without_octo_result": case.without_octo_result,
            }
            for case in result.cases
        ],
    }
