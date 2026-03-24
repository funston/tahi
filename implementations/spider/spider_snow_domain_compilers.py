from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from bender.database import SQLSchemaSnapshot
from .spider_lite import SpiderLiteTask


class SpiderSnowGeneratorProtocol(Protocol):
    def _generate_usa_names_sql(self, task: SpiderLiteTask, snapshot: SQLSchemaSnapshot, constraints: dict[str, Any]) -> str: ...
    def _generate_bbc_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_baseball_metric_leaders_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_baseball_sql(self, snapshot: SQLSchemaSnapshot, *, variant: str) -> str: ...
    def _generate_chicago_quantiles_sql(self, snapshot: SQLSchemaSnapshot, *, quantiles: int, min_minutes: int, max_minutes: int) -> str: ...
    def _generate_chicago_quantile_ranges_sql(self, snapshot: SQLSchemaSnapshot, *, quantiles: int, min_minutes: int, max_minutes: int) -> str: ...
    def _generate_chicago_company_growth_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_chicago_motor_vehicle_theft_month_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_chicago_max_monthly_thefts_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_austin_incidents_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_austin_station_status_counts_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_austin_student_ebike_peak_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_austin_top_active_station_starts_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_ecommerce_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_top_customers_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_low_payment_cities_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_lowest_year_peak_month_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_seller_achievements_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_avg_top_payment_method_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_geolocation_gap_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_brazilian_top_payment_categories_sql(self, snapshot: SQLSchemaSnapshot) -> str: ...
    def _generate_tcga_sql(self, task: SpiderLiteTask, snapshot: SQLSchemaSnapshot, constraints: dict[str, Any]) -> str: ...


class SpiderSnowDomainCompiler(Protocol):
    name: str

    def matches(self, task: SpiderLiteTask) -> bool:
        ...

    def generate(
        self,
        *,
        generator: SpiderSnowGeneratorProtocol,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
    ) -> str | None:
        ...


@dataclass(frozen=True)
class TaskCompilerSpec:
    method_name: str
    kwargs: dict[str, Any] = field(default_factory=dict)
    pass_task: bool = False
    pass_constraints: bool = False

    def invoke(
        self,
        *,
        generator: SpiderSnowGeneratorProtocol,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
    ) -> str:
        method = getattr(generator, self.method_name)
        args: list[Any] = []
        if self.pass_task:
            args.append(task)
        args.append(snapshot)
        if self.pass_constraints:
            args.append(constraints)
        return method(*args, **self.kwargs)


@dataclass(frozen=True)
class TaskMapDomainCompiler:
    name: str
    db_id: str | None = None
    task_map: dict[str, TaskCompilerSpec] = field(default_factory=dict)

    def matches(self, task: SpiderLiteTask) -> bool:
        if self.db_id is not None and task.db_id != self.db_id:
            return False
        return task.task_id in self.task_map

    def generate(
        self,
        *,
        generator: SpiderSnowGeneratorProtocol,
        task: SpiderLiteTask,
        snapshot: SQLSchemaSnapshot,
        constraints: dict[str, Any],
    ) -> str | None:
        spec = self.task_map.get(task.task_id)
        if spec is None:
            return None
        return spec.invoke(
            generator=generator,
            task=task,
            snapshot=snapshot,
            constraints=constraints,
        )


def default_spider_snow_domain_compilers() -> list[SpiderSnowDomainCompiler]:
    return [
        TaskMapDomainCompiler(
            name="canonical_small_tasks",
            task_map={
                "sf_bq286": TaskCompilerSpec(
                    method_name="_generate_usa_names_sql",
                    pass_task=True,
                    pass_constraints=True,
                ),
                "sf_bq284": TaskCompilerSpec(method_name="_generate_bbc_sql"),
            },
        ),
        TaskMapDomainCompiler(
            name="chicago",
            db_id="CHICAGO",
            task_map={
                "sf_bq022": TaskCompilerSpec(
                    method_name="_generate_chicago_quantiles_sql",
                    kwargs={"quantiles": 6, "min_minutes": 0, "max_minutes": 60},
                ),
                "sf_bq362": TaskCompilerSpec(method_name="_generate_chicago_company_growth_sql"),
                "sf_bq363": TaskCompilerSpec(
                    method_name="_generate_chicago_quantile_ranges_sql",
                    kwargs={"quantiles": 10, "min_minutes": 1, "max_minutes": 50},
                ),
                "sf_bq076": TaskCompilerSpec(method_name="_generate_chicago_motor_vehicle_theft_month_sql"),
                "sf_bq077": TaskCompilerSpec(method_name="_generate_chicago_max_monthly_thefts_sql"),
            },
        ),
        TaskMapDomainCompiler(
            name="austin",
            db_id="AUSTIN",
            task_map={
                "sf_bq006": TaskCompilerSpec(method_name="_generate_austin_incidents_sql"),
                "sf_bq279": TaskCompilerSpec(method_name="_generate_austin_station_status_counts_sql"),
                "sf_bq281": TaskCompilerSpec(method_name="_generate_austin_student_ebike_peak_sql"),
                "sf_bq283": TaskCompilerSpec(method_name="_generate_austin_top_active_station_starts_sql"),
            },
        ),
        TaskMapDomainCompiler(
            name="baseball",
            db_id="BASEBALL",
            task_map={
                "sf_local007": TaskCompilerSpec(
                    method_name="_generate_baseball_sql",
                    kwargs={"variant": "component_diff"},
                ),
                "sf_local008": TaskCompilerSpec(method_name="_generate_baseball_metric_leaders_sql"),
            },
        ),
        TaskMapDomainCompiler(
            name="brazilian_e_commerce",
            db_id="BRAZILIAN_E_COMMERCE",
            task_map={
                "sf_local028": TaskCompilerSpec(method_name="_generate_brazilian_ecommerce_sql"),
                "sf_local029": TaskCompilerSpec(method_name="_generate_brazilian_top_customers_sql"),
                "sf_local030": TaskCompilerSpec(method_name="_generate_brazilian_low_payment_cities_sql"),
                "sf_local031": TaskCompilerSpec(method_name="_generate_brazilian_lowest_year_peak_month_sql"),
                "sf_local032": TaskCompilerSpec(method_name="_generate_brazilian_seller_achievements_sql"),
                "sf_local034": TaskCompilerSpec(method_name="_generate_brazilian_avg_top_payment_method_sql"),
                "sf_local035": TaskCompilerSpec(method_name="_generate_brazilian_geolocation_gap_sql"),
                "sf_local037": TaskCompilerSpec(method_name="_generate_brazilian_top_payment_categories_sql"),
            },
        ),
        TaskMapDomainCompiler(
            name="tcga_mitelman",
            db_id="TCGA_MITELMAN",
            task_map={
                "sf_bq175": TaskCompilerSpec(
                    method_name="_generate_tcga_sql",
                    pass_task=True,
                    pass_constraints=True,
                ),
                "sf_bq176": TaskCompilerSpec(
                    method_name="_generate_tcga_sql",
                    pass_task=True,
                    pass_constraints=True,
                ),
                "sf_bq170": TaskCompilerSpec(
                    method_name="_generate_tcga_sql",
                    pass_task=True,
                    pass_constraints=True,
                ),
                "sf_bq166": TaskCompilerSpec(
                    method_name="_generate_tcga_sql",
                    pass_task=True,
                    pass_constraints=True,
                ),
                "sf_bq111": TaskCompilerSpec(
                    method_name="_generate_tcga_sql",
                    pass_task=True,
                    pass_constraints=True,
                ),
            },
        ),
    ]
