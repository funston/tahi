from octo import snapshot_to_world_model
from implementations.gretel import (
    GretelABBenchmarkRunner,
    GretelBenchmarkAdapter,
    GretelTask,
    build_snapshot_from_sql_context,
    enrich_world_with_gretel_metadata,
)


def test_build_snapshot_from_sql_context_extracts_tables_and_columns() -> None:
    snapshot = build_snapshot_from_sql_context(
        """
        CREATE TABLE salesperson (salesperson_id INT, name TEXT, region TEXT);
        CREATE TABLE timber_sales (sales_id INT, salesperson_id INT, volume REAL);
        INSERT INTO salesperson (salesperson_id, name, region) VALUES (1, 'John Doe', 'North');
        """,
        database_name="demo",
    )

    assert snapshot.database_name == "demo"
    assert [table.name for table in snapshot.tables] == ["salesperson", "timber_sales"]
    assert [column.name for column in snapshot.tables[0].columns] == ["salesperson_id", "name", "region"]


def test_gretel_benchmark_runner_returns_report() -> None:
    task = GretelTask(
        task_id="demo_1",
        domain="forestry",
        domain_description="Forestry sales and inventory analytics.",
        sql_prompt="What is the total volume of timber sold by each salesperson?",
        sql_context="""
        CREATE TABLE salesperson (salesperson_id INT, name TEXT, region TEXT);
        CREATE TABLE timber_sales (sales_id INT, salesperson_id INT, volume REAL);
        """,
        gold_sql="""
        SELECT salesperson.name, SUM(timber_sales.volume)
        FROM timber_sales
        JOIN salesperson ON timber_sales.salesperson_id = salesperson.salesperson_id
        GROUP BY salesperson.name
        """,
        sql_task_type="analytics and reporting",
        sql_task_type_description="Generate analytical sales reports.",
        sql_explanation="Join timber sales to salespeople and aggregate volume.",
    )
    snapshot = build_snapshot_from_sql_context(task.sql_context, database_name=task.task_id)
    report = GretelABBenchmarkRunner(
        baseline_adapter=GretelBenchmarkAdapter(
            snapshots_by_task={task.task_id: snapshot},
            worlds_by_task={task.task_id: snapshot_to_world_model(snapshot)},
        ),
        octo_adapter=GretelBenchmarkAdapter(
            snapshots_by_task={task.task_id: snapshot},
            worlds_by_task={task.task_id: enrich_world_with_gretel_metadata(snapshot_to_world_model(snapshot), task)},
            include_metadata_in_query=True,
        ),
    ).run([task])

    assert report["benchmark_name"] == "gretel_ab_grounding"
    assert [system["system"] for system in report["systems"]] == ["naive_lexical", "schema_only", "octo"]
