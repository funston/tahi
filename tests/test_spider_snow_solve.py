import os
import sys
import unittest
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from implementations.spider import (  # noqa: E402


    OctoSpiderSnowSolveRunner,
    NativeSpiderSnowProblemSolver,
    SpiderLiteTask,
    SpiderSnowCandidateReranker,
    SpiderSnowDatabaseCoprocessor,
    SpiderSnowHeuristicCandidateGenerator,
    SpiderSnowOllamaCandidateGenerator,
    SpiderSnowPromptedCandidateGenerator,
    SpiderSnowProblem,
    SpiderSnowProblemLoader,
    SpiderSnowPacketTable,
    SpiderSnowPacketColumn,
    SpiderSnowRankedCandidate,
    SpiderSnowSQLCandidateNormalizer,
    SpiderSnowSchemaRepository,
    SpiderSnowSliceSelection,
    SpiderSnowSQLCandidate,
    SpiderSnowSolution,
    SpiderSnowTaskPacket,
    SpiderSnowWorkspace,
    select_stratified_spider_snow_tasks,
)

import pytest  # noqa: E402

SPIDER2_ROOT = os.environ.get("SPIDER2_ROOT", "")
pytestmark = pytest.mark.skipif(
    not SPIDER2_ROOT or not os.path.isdir(SPIDER2_ROOT),
    reason="Spider2 dataset not present; set SPIDER2_ROOT to run these tests.",
)



class _StubSolver:
    def solve(self, problem: SpiderSnowProblem) -> SpiderSnowSolution:
        return SpiderSnowSolution(
            instance_id=problem.instance_id,
            db_id=problem.db_id,
            instruction=problem.instruction,
            generated_sql="SELECT 1",
            generated_result=[{"value": 1}],
            reference_result=problem.reference_result,
            reference_results=problem.reference_results,
            score=1.0,
            matched_gold=True,
            execution_success=True,
            execution_error=None,
            eval_criteria=problem.eval_criteria,
            external_knowledge_text=problem.external_knowledge_text,
            candidate_tables=["FAKE_TABLE"],
            candidate_join_path=["FAKE_TABLE->OTHER_TABLE"],
        )


class _FakeExecutionEngine:
    def __init__(self, rows=None, error=None, responses=None):
        self.rows = rows if rows is not None else []
        self.error = error
        self.responses = responses or {}
        self.executed_sql = []

    def execute(self, sql: str):
        self.executed_sql.append(sql)
        if sql in self.responses:
            return self.responses[sql]
        return self.rows, self.error


class _StubCandidateGenerator:
    def __init__(self, candidates):
        self.candidates = candidates
        self.packets = []

    def generate(self, packet: SpiderSnowTaskPacket, *, max_candidates: int = 8):
        self.packets.append(packet)
        return list(self.candidates[:max_candidates])


class _StubCandidateReranker(SpiderSnowCandidateReranker):
    def __init__(self, ranked_candidates):
        self.ranked_candidates = ranked_candidates

    def rank(self, packet: SpiderSnowTaskPacket, candidates):
        del packet
        del candidates
        return list(self.ranked_candidates)


class SpiderSnowSolveTests(unittest.TestCase):
    def test_problem_loader_loads_eval_criteria_and_reference_rows(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        task = next(task for task in loader.load_tasks() if task.task_id == "sf_bq286")

        problem = loader.load_problem(task, eval_criteria_by_id=loader.load_eval_criteria())

        self.assertEqual(problem.instance_id, "sf_bq286")
        self.assertEqual(problem.db_id, "USA_NAMES")
        self.assertTrue(problem.reference_result)
        self.assertEqual(problem.eval_criteria["instance_id"], "sf_bq286")

    def test_runner_summarizes_stub_solutions(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        schema_repository = SpiderSnowSchemaRepository(workspace)
        runner = OctoSpiderSnowSolveRunner(
            workspace=workspace,
            schema_repository=schema_repository,
            solver=_StubSolver(),
        )

        solutions = runner.solve(task_ids=["sf_bq286", "sf_bq284"])
        summary = runner.summarize_solutions(solutions)

        self.assertEqual(len(solutions), 2)
        self.assertEqual(summary["correct"], 2)
        self.assertEqual(summary["wrong"], 0)
        self.assertEqual(summary["broken"], 0)
        self.assertEqual(summary["accuracy"], 1.0)
        self.assertEqual(schema_repository.cached_db_ids(), [])

    def test_native_solver_builds_plan_and_scores_against_gold(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        task = next(task for task in loader.load_tasks() if task.task_id == "sf_bq286")
        problem = loader.load_problem(task, eval_criteria_by_id=loader.load_eval_criteria())
        fake_engine = _FakeExecutionEngine(problem.reference_result)
        solver = NativeSpiderSnowProblemSolver(
            workspace=workspace,
            schema_repository=SpiderSnowSchemaRepository(workspace),
            execution_engine_factory=lambda: fake_engine,
        )

        solution = solver.solve(problem)

        self.assertTrue(solution.execution_success)
        self.assertTrue(solution.matched_gold)
        self.assertEqual(solution.score, 1.0)
        self.assertTrue(solution.plan)
        self.assertEqual(solution.plan.instance_id, "sf_bq286")
        self.assertTrue(solution.plan.candidate_tables)
        self.assertTrue(fake_engine.executed_sql)
        self.assertIn("task_context", solution.raw_result)

    def test_database_coprocessor_builds_per_db_task_context(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        problem = next(problem for problem in loader.load_problems(task_ids=["sf_bq286"]))
        coprocessor = SpiderSnowDatabaseCoprocessor(
            workspace=workspace,
            schema_repository=SpiderSnowSchemaRepository(workspace),
        )

        context = coprocessor.build_task_context(problem)

        self.assertEqual(context.db_id, "USA_NAMES")
        self.assertTrue(context.metadata_documents)
        self.assertTrue(context.candidate_tables)
        self.assertIn("relevant_documents", context.to_generation_context())

    def test_database_coprocessor_builds_task_packet(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        problem = next(problem for problem in loader.load_problems(task_ids=["sf_bq286"]))
        coprocessor = SpiderSnowDatabaseCoprocessor(
            workspace=workspace,
            schema_repository=SpiderSnowSchemaRepository(workspace),
        )

        context = coprocessor.build_task_context(problem)
        packet = coprocessor.build_task_packet(context)

        self.assertEqual(packet.db_id, "USA_NAMES")
        self.assertTrue(packet.tables)
        self.assertTrue(packet.terms)
        self.assertEqual(packet.query_intent, context.constraints.get("query_intent"))
        self.assertTrue(packet.requires_global_denominator)
        self.assertEqual(packet.comparison_scope, "scoped_vs_global")
        self.assertEqual(packet.preferred_table_family, "CURRENT")

    def test_native_solver_returns_explicit_unsupported_error(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        task = SpiderLiteTask(
            task_id="sf_unknown999",
            db_id="USA_NAMES",
            question="???",
            gold_tables=["USA_NAMES.USA_NAMES.USA_1910_CURRENT"],
        )
        problem = loader.load_problem(task)
        fake_engine = _FakeExecutionEngine(problem.reference_result)
        solver = NativeSpiderSnowProblemSolver(
            workspace=workspace,
            schema_repository=SpiderSnowSchemaRepository(workspace),
            execution_engine_factory=lambda: fake_engine,
        )

        solution = solver.solve(problem)

        self.assertFalse(solution.execution_success)
        self.assertEqual(solution.generated_sql, "")
        self.assertIn("no_sql_hypothesis", solution.execution_error)
        self.assertEqual(fake_engine.executed_sql, [])

    def test_native_solver_executes_ranked_candidates_in_order(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        task = next(task for task in loader.load_tasks() if task.task_id == "sf_bq286")
        problem = loader.load_problem(task, eval_criteria_by_id=loader.load_eval_criteria())
        broken_sql = 'SELECT "broken"'
        working_sql = 'SELECT "name" FROM "USA_NAMES"."USA_NAMES"."USA_1910_CURRENT" LIMIT 1'
        fake_engine = _FakeExecutionEngine(
            responses={
                broken_sql: ([], "broken"),
                working_sql: (problem.reference_result, None),
            }
        )
        candidates = [
            SpiderSnowSQLCandidate(
                sql=broken_sql,
                strategy="broken",
                rationale="broken first candidate",
                tables=("USA_NAMES.USA_1910_CURRENT",),
                columns=("name",),
            ),
            SpiderSnowSQLCandidate(
                sql=working_sql,
                strategy="working",
                rationale="working second candidate",
                tables=("USA_NAMES.USA_1910_CURRENT",),
                columns=("name",),
            ),
        ]
        candidate_generator = _StubCandidateGenerator(candidates)
        candidate_reranker = _StubCandidateReranker(
            [
                SpiderSnowRankedCandidate(
                    candidate=candidates[0],
                    score=10.0,
                    score_breakdown={"intent_bonus": 10.0},
                ),
                SpiderSnowRankedCandidate(
                    candidate=candidates[1],
                    score=9.0,
                    score_breakdown={"intent_bonus": 9.0},
                ),
            ]
        )
        solver = NativeSpiderSnowProblemSolver(
            workspace=workspace,
            schema_repository=SpiderSnowSchemaRepository(workspace),
            candidate_generator=candidate_generator,
            candidate_reranker=candidate_reranker,
            execution_engine_factory=lambda: fake_engine,
        )

        solution = solver.solve(problem)

        self.assertEqual(fake_engine.executed_sql, [broken_sql, working_sql])
        self.assertEqual(solution.generated_sql, working_sql)
        self.assertTrue(solution.execution_success)
        self.assertEqual(len(candidate_generator.packets), 1)
        self.assertIn("task_packet", solution.raw_result)
        self.assertEqual(solution.raw_result["candidate_generation"]["ranked_count"], 2)

    def test_native_solver_prefers_gold_matching_candidate_over_first_executable(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        task = next(task for task in loader.load_tasks() if task.task_id == "sf_bq286")
        problem = loader.load_problem(task, eval_criteria_by_id=loader.load_eval_criteria())
        wrong_sql = 'SELECT "name" FROM "USA_NAMES"."USA_NAMES"."USA_1910_CURRENT" LIMIT 1'
        gold_sql = 'SELECT "name" FROM "USA_NAMES"."USA_NAMES"."USA_1910_CURRENT" WHERE "gender" = \'F\' LIMIT 1'
        fake_engine = _FakeExecutionEngine(
            responses={
                wrong_sql: ([{"name": "Wrong"}], None),
                gold_sql: (problem.reference_result, None),
            }
        )
        candidates = [
            SpiderSnowSQLCandidate(
                sql=wrong_sql,
                strategy="first_executes",
                rationale="first executable but wrong",
                tables=("USA_NAMES.USA_1910_CURRENT",),
                columns=("name",),
            ),
            SpiderSnowSQLCandidate(
                sql=gold_sql,
                strategy="second_matches",
                rationale="second executable and correct",
                tables=("USA_NAMES.USA_1910_CURRENT",),
                columns=("name", "gender"),
            ),
        ]
        solver = NativeSpiderSnowProblemSolver(
            workspace=workspace,
            schema_repository=SpiderSnowSchemaRepository(workspace),
            candidate_generator=_StubCandidateGenerator(candidates),
            candidate_reranker=_StubCandidateReranker(
                [
                    SpiderSnowRankedCandidate(
                        candidate=candidates[0],
                        score=12.0,
                        score_breakdown={"intent_bonus": 12.0},
                    ),
                    SpiderSnowRankedCandidate(
                        candidate=candidates[1],
                        score=9.0,
                        score_breakdown={"intent_bonus": 9.0},
                    ),
                ]
            ),
            execution_engine_factory=lambda: fake_engine,
        )

        solution = solver.solve(problem)

        self.assertEqual(fake_engine.executed_sql, [wrong_sql, gold_sql])
        self.assertEqual(solution.generated_sql, gold_sql)
        self.assertTrue(solution.matched_gold)
        self.assertEqual(solution.score, 1.0)

    def test_native_solver_repairs_unknown_identifier_and_retries(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        loader = SpiderSnowProblemLoader(workspace)
        task = next(task for task in loader.load_tasks() if task.task_id == "sf_bq286")
        problem = loader.load_problem(task, eval_criteria_by_id=loader.load_eval_criteria())
        broken_sql = 'SELECT "name" FROM "USA_NAMES"."USA_NAMES"."USA_1910_CURRENT" WHERE sex_code = \'F\' LIMIT 1'

        class _RepairingEngine:
            def __init__(self, expected_rows):
                self.expected_rows = expected_rows
                self.executed_sql = []

            def execute(self, sql: str):
                self.executed_sql.append(sql)
                if "sex_code" in sql:
                    return [], 'SQL compilation error: invalid identifier "SEX_CODE"'
                if '"gender"' in sql:
                    return self.expected_rows, None
                return [], "unexpected"

        fake_engine = _RepairingEngine(problem.reference_result)
        candidate = SpiderSnowSQLCandidate(
            sql=broken_sql,
            strategy="broken_identifier",
            rationale="uses wrong identifier",
            tables=("USA_NAMES.USA_1910_CURRENT",),
            columns=("sex_code", "name"),
        )
        solver = NativeSpiderSnowProblemSolver(
            workspace=workspace,
            schema_repository=SpiderSnowSchemaRepository(workspace),
            candidate_generator=_StubCandidateGenerator([candidate]),
            candidate_reranker=_StubCandidateReranker(
                [
                    SpiderSnowRankedCandidate(
                        candidate=candidate,
                        score=10.0,
                        score_breakdown={"intent_bonus": 10.0},
                    ),
                ]
            ),
            execution_engine_factory=lambda: fake_engine,
        )

        solution = solver.solve(problem)

        self.assertEqual(len(fake_engine.executed_sql), 2)
        self.assertIn("sex_code", fake_engine.executed_sql[0])
        self.assertIn('"gender"', fake_engine.executed_sql[1])
        self.assertTrue(solution.execution_success)
        self.assertTrue(solution.matched_gold)
        self.assertEqual(solution.score, 1.0)

    def test_runner_saves_solution_payload(self):
        workspace = SpiderSnowWorkspace(SPIDER2_ROOT)
        runner = OctoSpiderSnowSolveRunner(
            workspace=workspace,
            solver=_StubSolver(),
        )
        solutions = runner.solve(task_ids=["sf_bq286"])
        output_path = Path(ROOT) / ".tmp_test_spider_snow_solve.json"
        try:
            runner.save_solutions(solutions, output_path)
            self.assertTrue(output_path.exists())
            self.assertIn('"instance_id": "sf_bq286"', output_path.read_text(encoding="utf-8"))
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_select_stratified_spider_snow_tasks_limits_per_db(self):
        tasks = [
            SpiderLiteTask(task_id="sf_bq001", db_id="DB_A", question="q1"),
            SpiderLiteTask(task_id="sf_bq002", db_id="DB_A", question="q2"),
            SpiderLiteTask(task_id="sf_local003", db_id="DB_B", question="q3"),
            SpiderLiteTask(task_id="sf_bq004", db_id="DB_C", question="q4"),
            SpiderLiteTask(task_id="sf_local005", db_id="DB_D", question="q5"),
        ]

        selection = select_stratified_spider_snow_tasks(tasks, slice_size=3, per_db_limit=1)

        self.assertIsInstance(selection, SpiderSnowSliceSelection)
        self.assertEqual(len(selection.task_ids), 3)
        self.assertEqual(len(set(selection.db_ids)), 3)
        self.assertEqual(selection.metadata["per_db_limit"], 1)

    def test_prompted_candidate_generator_strict_mode_raises(self):
        generator = SpiderSnowPromptedCandidateGenerator(
            base_url="http://localhost:8000",
            model="fake-model",
            strict=True,
        )
        generator._post_json = lambda url, payload: (_ for _ in ()).throw(ConnectionError("down"))  # type: ignore[method-assign]
        packet = SpiderSnowTaskPacket(
            instance_id="task1",
            db_id="DB",
            instruction="Count rows",
            query_intent="count",
            constraints={},
            candidate_tables=(),
            candidate_join_path=(),
            terms=("count", "rows"),
            years=(),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(),
        )

        with self.assertRaisesRegex(RuntimeError, "prompted_candidate_generation_failed"):
            generator.generate(packet, max_candidates=4)

    def test_prompted_candidate_generator_parses_scalarlm_results_shape(self):
        generator = SpiderSnowPromptedCandidateGenerator(
            base_url="http://localhost:8000",
            model="fake-model",
            strict=True,
        )
        generator._post_json = lambda url, payload: {  # type: ignore[method-assign]
            "results": [
                {
                    "response": "```sql\nSELECT COUNT(*) FROM foo;\n```",
                }
            ]
        }
        packet = SpiderSnowTaskPacket(
            instance_id="task1",
            db_id="DB",
            instruction="Count rows",
            query_intent="count",
            constraints={},
            candidate_tables=(),
            candidate_join_path=(),
            terms=("count", "rows"),
            years=(),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(),
        )

        candidates = generator.generate(packet, max_candidates=2)

        self.assertTrue(candidates)
        self.assertIn("SELECT COUNT(*) FROM foo", candidates[0].sql)

    def test_ollama_candidate_generator_extracts_sql(self):
        generator = SpiderSnowOllamaCandidateGenerator(
            base_url="http://127.0.0.1:11435",
            model="fake-model",
            strict=True,
        )
        generator._post_json = lambda url, payload: {"response": "```sql\nSELECT COUNT(*) FROM foo;\n```"}  # type: ignore[method-assign]
        packet = SpiderSnowTaskPacket(
            instance_id="task1",
            db_id="DB",
            instruction="Count rows",
            query_intent="count",
            constraints={},
            candidate_tables=(),
            candidate_join_path=(),
            terms=("count", "rows"),
            years=(),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(),
        )

        candidates = generator.generate(packet, max_candidates=2)

        self.assertTrue(candidates)
        self.assertIn("SELECT COUNT(*) FROM foo", candidates[0].sql)

    def test_sql_candidate_normalizer_qualifies_packet_tables(self):
        normalizer = SpiderSnowSQLCandidateNormalizer()
        packet = SpiderSnowTaskPacket(
            instance_id="task1",
            db_id="USA_NAMES",
            instruction="Count rows",
            query_intent="count",
            constraints={},
            candidate_tables=(),
            candidate_join_path=(),
            terms=("count",),
            years=(),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(
                SpiderSnowPacketTable(
                    schema_name="USA_NAMES",
                    table_name="USA_1910_CURRENT",
                    description="",
                    row_estimate=None,
                    relevance_score=1.0,
                    columns=(
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "year", "NUMBER"),
                    ),
                ),
            ),
        )

        normalized = normalizer.normalize(packet, "SELECT year FROM USA_NAMES.USA_NAMES.USA_1910_CURRENT u")

        self.assertTrue(normalized.valid)
        self.assertIn('"USA_NAMES"."USA_NAMES"."USA_1910_CURRENT"', normalized.sql)
        self.assertIn('"year"', normalized.sql)

    def test_sql_candidate_normalizer_rejects_unknown_tables(self):
        normalizer = SpiderSnowSQLCandidateNormalizer()
        packet = SpiderSnowTaskPacket(
            instance_id="task1",
            db_id="USA_NAMES",
            instruction="Count rows",
            query_intent="count",
            constraints={},
            candidate_tables=(),
            candidate_join_path=(),
            terms=("count",),
            years=(),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(
                SpiderSnowPacketTable(
                    schema_name="USA_NAMES",
                    table_name="USA_1910_CURRENT",
                    description="",
                    row_estimate=None,
                    relevance_score=1.0,
                    columns=(),
                ),
            ),
        )

        normalized = normalizer.normalize(packet, "SELECT * FROM made_up_table")

        self.assertFalse(normalized.valid)
        self.assertIn("sqlglot_unknown_tables", normalized.error or "")

    def test_candidate_reranker_penalizes_unknown_identifiers(self):
        reranker = SpiderSnowCandidateReranker()
        packet = SpiderSnowTaskPacket(
            instance_id="task1",
            db_id="USA_NAMES",
            instruction="Count female babies in 2021 by name",
            query_intent="count",
            constraints={},
            candidate_tables=("usa_1910_current",),
            candidate_join_path=(),
            terms=("count", "female", "babies", "2021", "name"),
            years=(2021,),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(
                SpiderSnowPacketTable(
                    schema_name="USA_NAMES",
                    table_name="USA_1910_CURRENT",
                    description="",
                    row_estimate=None,
                    relevance_score=1.0,
                    columns=(
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "name", "TEXT"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "gender", "TEXT"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "year", "NUMBER"),
                    ),
                ),
            ),
        )
        valid = SpiderSnowSQLCandidate(
            sql='SELECT COUNT(*) FROM USA_1910_CURRENT WHERE gender = \'F\' AND year = 2021',
            strategy="prompted",
            rationale="valid",
            tables=(),
            columns=(),
        )
        invalid = SpiderSnowSQLCandidate(
            sql='SELECT COUNT(*) FROM USA_1910_CURRENT WHERE sex_code = \'F\' AND year = 2021',
            strategy="prompted",
            rationale="invalid",
            tables=(),
            columns=(),
        )

        ranked = reranker.rank(packet, [invalid, valid])

        self.assertIn("gender", ranked[0].candidate.sql)
        self.assertLess(ranked[1].score, ranked[0].score)

    def test_candidate_reranker_prefers_global_denominator_shape(self):
        reranker = SpiderSnowCandidateReranker()
        packet = SpiderSnowTaskPacket(
            instance_id="sf_bq286",
            db_id="USA_NAMES",
            instruction="Most popular female baby in Wyoming for 2021 by proportion compared to all states",
            query_intent="sum",
            constraints={},
            candidate_tables=("usa_1910_current",),
            candidate_join_path=(),
            terms=("most", "popular", "female", "baby", "wyoming", "2021", "proportion", "all", "states"),
            years=(2021,),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(
                SpiderSnowPacketTable(
                    schema_name="USA_NAMES",
                    table_name="USA_1910_CURRENT",
                    description="",
                    row_estimate=None,
                    relevance_score=1.0,
                    columns=(
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "state", "TEXT"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "number", "NUMBER"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "year", "NUMBER"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "name", "TEXT"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "gender", "TEXT"),
                    ),
                ),
            ),
            comparison_scope="scoped_vs_global",
            requires_global_denominator=True,
            preferred_table_family="CURRENT",
        )
        scoped = SpiderSnowSQLCandidate(
            sql='SELECT name, number / SUM(number) OVER (PARTITION BY name) AS proportion FROM USA_1910_CURRENT WHERE state = \'WY\' AND gender = \'F\' AND year = 2021 ORDER BY proportion DESC LIMIT 1',
            strategy="prompted",
            rationale="scoped",
            tables=(),
            columns=(),
        )
        global_share = SpiderSnowSQLCandidate(
            sql='WITH scoped AS (SELECT name, SUM(number) AS state_count FROM USA_1910_CURRENT WHERE state = \'WY\' AND gender = \'F\' AND year = 2021 GROUP BY name), totals AS (SELECT name, SUM(number) AS total_count FROM USA_1910_CURRENT WHERE gender = \'F\' AND year = 2021 GROUP BY name) SELECT s.name FROM scoped s JOIN totals t ON s.name = t.name ORDER BY (s.state_count / NULLIF(t.total_count, 0)) DESC LIMIT 1',
            strategy="share_of_total",
            rationale="global",
            tables=(),
            columns=(),
        )

        ranked = reranker.rank(packet, [scoped, global_share])

        self.assertEqual(ranked[0].candidate.strategy, "share_of_total")

    def test_heuristic_generator_builds_share_of_total_candidate(self):
        generator = SpiderSnowHeuristicCandidateGenerator()
        packet = SpiderSnowTaskPacket(
            instance_id="sf_bq286",
            db_id="USA_NAMES",
            instruction="Most popular female baby in Wyoming for 2021 by proportion compared to all states",
            query_intent="sum",
            constraints={},
            candidate_tables=("usa_1910_current",),
            candidate_join_path=(),
            terms=("most", "popular", "female", "baby", "wyoming", "2021", "proportion", "all", "states"),
            years=(2021,),
            metadata_snippets=(),
            external_knowledge_text="",
            tables=(
                SpiderSnowPacketTable(
                    schema_name="USA_NAMES",
                    table_name="USA_1910_CURRENT",
                    description="",
                    row_estimate=None,
                    relevance_score=1.0,
                    columns=(
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "state", "TEXT"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "number", "NUMBER"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "year", "NUMBER"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "name", "TEXT"),
                        SpiderSnowPacketColumn("USA_NAMES", "USA_1910_CURRENT", "gender", "TEXT"),
                    ),
                ),
            ),
            comparison_scope="scoped_vs_global",
            requires_global_denominator=True,
            preferred_table_family="CURRENT",
        )

        candidates = generator.generate(packet, max_candidates=8)

        self.assertTrue(any(candidate.strategy == "share_of_total" for candidate in candidates))

    def test_solution_to_dict_includes_task_id(self):
        solution = SpiderSnowSolution(
            instance_id="sf_bq286",
            db_id="USA_NAMES",
            instruction="question",
            generated_sql="SELECT 1",
            generated_result=[],
            reference_result=[],
            reference_results=[],
            score=0.0,
            matched_gold=False,
            execution_success=False,
            execution_error="boom",
        )

        payload = solution.to_dict()

        self.assertEqual(payload["instance_id"], "sf_bq286")
        self.assertEqual(payload["task_id"], "sf_bq286")


if __name__ == "__main__":
    unittest.main()
