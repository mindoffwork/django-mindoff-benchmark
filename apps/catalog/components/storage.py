"""Persistence of benchmark results to the ``BenchmarkResultModel`` table.

Two functions, mirror images of each other: ``save_metrics`` writes a run's
metric dicts, ``latest_metrics`` reads the most recent ones back in the display
shape (the same keys ``as_dict`` produces) so a chart or CSV can be rebuilt from
stored history without re-running the benchmark.
"""

from __future__ import annotations

from django.db import connection

from apps.catalog.models import BenchmarkResultModel
from apps.catalog.components.config import (
    DEFAULT_BENCHMARK_ITERATIONS,
    DEFAULT_BENCHMARK_WARMUPS,
    _query_count_note,
)


def save_metrics(metrics: list[dict]) -> None:
    """Persist a run's metric dicts as ``BenchmarkResultModel`` rows."""
    BenchmarkResultModel.objects.bulk_create(
        [
            BenchmarkResultModel(
                scenario=metric["scenario"],
                approach=metric["approach"],
                row_count=metric["row_count"],
                time_ms=metric["time_ms"],
                memory_mb=metric["memory_mb"],
                query_count=metric["query_count"],
            )
            for metric in metrics
        ]
    )


def latest_metrics(limit: int = 200) -> list[dict]:
    """Return the most recent stored metrics in the display/export shape.

    Fields the table doesn't store (iterations, backend, notes) are reconstructed
    from the current config so the dict matches a freshly-measured one.
    """
    return [
        {
            "scenario": item.scenario,
            "approach": item.approach,
            "row_count": item.row_count,
            "time_ms": round(item.time_ms, 2),
            "time_seconds": round(item.time_ms / 1000, 2),
            "memory_mb": round(item.memory_mb, 2),
            "query_count": item.query_count,
            "iterations": DEFAULT_BENCHMARK_ITERATIONS,
            "warmup_iterations": DEFAULT_BENCHMARK_WARMUPS,
            "backend": connection.vendor,
            "memory_metric": "peak_rss_delta_mb",
            "query_count_note": _query_count_note(item.approach),
        }
        for item in BenchmarkResultModel.objects.order_by("-created_at")[:limit]
    ]

