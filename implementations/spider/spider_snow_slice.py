from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .spider_lite import SpiderLiteTask


def _db_bucket(task_count: int) -> str:
    if task_count >= 10:
        return "large"
    if task_count >= 5:
        return "medium"
    if task_count >= 2:
        return "small"
    return "singleton"


def _task_source(task_id: str) -> str:
    lowered = task_id.lower()
    if lowered.startswith("sf_local"):
        return "local"
    if lowered.startswith("sf_bq"):
        return "bq"
    return "other"


@dataclass(frozen=True)
class SpiderSnowSliceSelection:
    task_ids: tuple[str, ...]
    db_ids: tuple[str, ...]
    metadata: dict[str, object]


def select_stratified_spider_snow_tasks(
    tasks: list[SpiderLiteTask],
    *,
    slice_size: int = 32,
    per_db_limit: int = 1,
) -> SpiderSnowSliceSelection:
    if slice_size <= 0:
        return SpiderSnowSliceSelection(task_ids=(), db_ids=(), metadata={"slice_size": 0})
    counts_by_db: dict[str, int] = defaultdict(int)
    for task in tasks:
        counts_by_db[task.db_id] += 1

    grouped: dict[tuple[str, str], list[SpiderLiteTask]] = defaultdict(list)
    for task in sorted(tasks, key=lambda item: (item.db_id, item.task_id)):
        grouped[(_db_bucket(counts_by_db[task.db_id]), _task_source(task.task_id))].append(task)

    ordered_groups = [
        ("large", "bq"),
        ("large", "local"),
        ("medium", "bq"),
        ("medium", "local"),
        ("small", "bq"),
        ("small", "local"),
        ("singleton", "bq"),
        ("singleton", "local"),
        ("large", "other"),
        ("medium", "other"),
        ("small", "other"),
        ("singleton", "other"),
    ]

    selected: list[SpiderLiteTask] = []
    selected_ids: set[str] = set()
    db_usage: dict[str, int] = defaultdict(int)
    while len(selected) < slice_size:
        progressed = False
        for group_key in ordered_groups:
            pool = grouped[group_key]
            while pool and (pool[0].task_id in selected_ids or db_usage[pool[0].db_id] >= per_db_limit):
                pool.pop(0)
            if not pool:
                continue
            task = pool.pop(0)
            selected.append(task)
            selected_ids.add(task.task_id)
            db_usage[task.db_id] += 1
            progressed = True
            if len(selected) >= slice_size:
                break
        if not progressed:
            break

    if len(selected) < slice_size:
        remaining = sorted(tasks, key=lambda item: (counts_by_db[item.db_id], item.db_id, item.task_id))
        for task in remaining:
            if task.task_id in selected_ids or db_usage[task.db_id] >= per_db_limit:
                continue
            selected.append(task)
            selected_ids.add(task.task_id)
            db_usage[task.db_id] += 1
            if len(selected) >= slice_size:
                break

    db_ids = sorted({task.db_id for task in selected})
    by_bucket: dict[str, int] = defaultdict(int)
    by_source: dict[str, int] = defaultdict(int)
    for task in selected:
        by_bucket[_db_bucket(counts_by_db[task.db_id])] += 1
        by_source[_task_source(task.task_id)] += 1
    return SpiderSnowSliceSelection(
        task_ids=tuple(task.task_id for task in selected),
        db_ids=tuple(db_ids),
        metadata={
            "slice_size": len(selected),
            "per_db_limit": per_db_limit,
            "bucket_counts": dict(sorted(by_bucket.items())),
            "source_counts": dict(sorted(by_source.items())),
        },
    )
