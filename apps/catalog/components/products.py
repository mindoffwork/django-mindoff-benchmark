"""Catalog product component — public entry points.

This is the module API views and other apps import from. It exposes three
operations and delegates every detail to the sibling modules in ``components/``:

  import_products        Validate + benchmark + persist an inbound product upload.
  list_products_report   Mindoff-powered read + aggregate report.
  run_product_benchmarks Sweep one or more row counts, emit CSV + charts.
  run_product_benchmark  Single-count benchmark (the workhorse called by the above).

Reading order for contributors: start here to understand the flow, then open
whichever sibling covers the step you care about:

  config.py    — benchmark constants and methodology notes
  fixtures.py  — deterministic rows, Polars frames, Parquet source, IO helpers
  create.py    — CREATE implementations (DRF / pandas / mindoff)
  read.py      — READ implementations + cross-approach output parity check
  update.py    — UPDATE implementations (DRF / mindoff; pandas has no bulk-update)
  measure.py   — how every number is measured: time, memory, query count
  storage.py   — saving and reloading results from BenchmarkResultModel
  exports.py   — the deliverables: CSV table and line charts
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid

import polars as pl
from django_mindoff import mo_crud_kit

from apps.catalog.models import ProductModel
from apps.catalog.components.config import (
    BENCHMARK_LOCK_PATH,
    DEFAULT_BENCHMARK_ITERATIONS,
    DEFAULT_BENCHMARK_ROW_COUNT,
    MAX_BENCHMARK_ROW_COUNT,
    SCENARIO_APPROACHES,
)
from apps.catalog.components.fixtures import (
    _csv_safe_frame,
    _read_output_path,
    _source_parquet_path,
    deterministic_rows,
    ensure_source_parquet,
    validate_product_rows,
)
from apps.catalog.components.create import (
    drf_bulk_validated_create,
    drf_create_from_parquet,
    mindoff_create,
    mindoff_create_from_parquet,
    mindoff_lazy_create_from_parquet,
    pandas_create_from_parquet,
    standard_bulk_create,
)
from apps.catalog.components.read import (
    pandas_csv_export,
    polars_naive_csv_export,
    _validate_read_csv_parity,
)
from apps.catalog.components.update import (
    drf_bulk_validated_update,
    mindoff_lazy_update,
    mindoff_update,
)
from apps.catalog.components.measure import (
    Measurement,
    measure,
    _measure_scenario,
    _memory_probe_scenario_worker,  # re-exported: the subprocess imports it from here
)
from apps.catalog.components.storage import save_metrics
from apps.catalog.components.exports import (
    build_benchmark_csv,
    build_benchmark_charts,
    _cleanup_transient_outputs,
    _stringify_paths,
)


# ===========================================================================
# Cross-process run lock
# ===========================================================================
# Inlined here because it is used only by run_product_benchmarks below.
# On Windows: busy-poll with msvcrt.locking. On POSIX: blocking fcntl.flock.
@contextlib.contextmanager
def benchmark_file_lock():
    """Hold an exclusive lock on the benchmark lock file for the duration of a run.

    Serializes concurrent benchmark invocations so they don't fight over the
    shared database and ``output/`` directory.
    """
    BENCHMARK_LOCK_PATH.parent.mkdir(exist_ok=True)
    with BENCHMARK_LOCK_PATH.open("a+b") as lock_file:
        _lock_file(lock_file)
        try:
            yield
        finally:
            _unlock_file(lock_file)


def _lock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt
        if lock_file.seek(0, os.SEEK_END) == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        while True:
            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.25)
        return
    import fcntl
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


# ===========================================================================
# Application operations
# ===========================================================================
def import_products(rows: list[dict]) -> dict:
    """Validate, benchmark, and persist an inbound product upload.

    Valid rows are run through both the standard DRF create and the Mindoff
    create (each measured and logged, per AGENTS.md S6), then actually persisted
    via Mindoff. Returns an import summary with row counts, the first few
    rejection reasons, and the comparison metrics.
    """
    valid_rows, errors = validate_product_rows(rows)
    metrics = []
    if valid_rows:
        # The standard-path probe writes to a throwaway category namespace so it
        # doesn't collide with the real Mindoff insert that follows.
        probe = [
            dict(row, category=f"standard_probe_{row['category']}")
            for row in valid_rows
        ]
        metrics.append(
            measure(
                "django_bulk_validated",
                "import_products",
                len(probe),
                lambda: lambda: drf_bulk_validated_create(probe),
                cleanup=lambda: ProductModel.objects.filter(
                    category__startswith="standard_probe_"
                ).delete(),
            ).as_dict()
        )
        metrics.append(
            measure(
                "django_mindoff_polars",
                "import_products",
                len(valid_rows),
                lambda: lambda: mindoff_create(valid_rows),
                cleanup=lambda: ProductModel.objects.filter(
                    sku__in=[row["sku"] for row in valid_rows]
                ).delete(),
            ).as_dict()
        )
        mindoff_create(valid_rows)
        save_metrics(metrics)

    return {
        "total_rows": len(rows),
        "inserted_rows": len(valid_rows),
        "rejected_rows": len(errors),
        "errors": errors[:5],
        "metrics": metrics,
    }


def list_products_report() -> dict:
    """Read every product via Mindoff and return an aggregate summary.

    Demonstrates the Mindoff read path feeding straight into Polars aggregations
    (counts, totals, per-category breakdown) without a Python row loop.
    """
    frm, stats = mo_crud_kit.read(
        ProductModel.objects.all().values(),
        batch_size=500,
    )
    if frm.is_empty():
        return {
            "total_products": 0,
            "active_products": 0,
            "total_stock": 0,
            "average_price": 0,
            "by_category": [],
            "read_stats": stats,
        }

    active_products = frm.filter(pl.col("is_active") == True).height
    breakdown = (
        frm.group_by("category")
        .agg(
            pl.len().alias("count"),
            pl.col("stock").sum().alias("stock"),
        )
        .sort("category")
        .to_dicts()
    )
    return {
        "total_products": frm.height,
        "active_products": active_products,
        "total_stock": int(frm["stock"].sum()),
        "average_price": round(float(frm["price"].mean()), 2),
        "by_category": breakdown,
        "read_stats": stats,
    }


# ===========================================================================
# Benchmark orchestration
# ===========================================================================
def run_product_benchmarks(
    *,
    row_count: int | list[int] = DEFAULT_BENCHMARK_ROW_COUNT,
    iterations: int = DEFAULT_BENCHMARK_ITERATIONS,
) -> dict:
    """Sweep one or more row counts under a single lock; emit CSV + charts.

    This is the function the API view calls. It runs ``run_product_benchmark``
    per requested row count, exports the combined deliverables, then removes the
    transient scaffolding so ``output/`` holds only the CSV and the two charts.
    """
    with benchmark_file_lock():
        counts = _benchmark_counts(row_count=row_count)
        results = []
        parity_checks = []
        for count in counts:
            measurements, parity = run_product_benchmark(count, iterations=iterations)
            results.extend(measurements)
            parity_checks.append({"row_count": count, **parity})
        csv_path = build_benchmark_csv(metrics=results)
        chart_paths = build_benchmark_charts(metrics=results)
        # The read benchmark writes CSVs as its measured operation; parity
        # validation reads them before this cleanup removes the transient dir.
        _cleanup_transient_outputs()
        return {
            "metrics": results,
            "exports": {
                "csv": str(csv_path),
                **_stringify_paths(chart_paths),
            },
            "row_counts": counts,
            "max_row_count": max(counts),
            "csv_parity_checks": parity_checks,
        }


def run_product_benchmark(
    row_count: int = DEFAULT_BENCHMARK_ROW_COUNT,
    *,
    iterations: int = DEFAULT_BENCHMARK_ITERATIONS,
) -> tuple[list[dict], dict]:
    """Run the full create/read/update benchmark at a single row count.

    Returns ``(measurements, csv_parity)``. Each operation flows through the one
    ``_measure_scenario`` driver (shared timing loop + per-scenario memory
    subprocess + query pass):

    * **CREATE** — ingest a per-approach Parquet source and persist (realistic
      bulk create); the source is built once in setup, never timed.
    * **READ** — queryset → Polars frame → CSV (pandas / polars baseline /
      Mindoff eager / Mindoff stream), then a cross-approach parity check.
    * **UPDATE** — bulk upsert; rows are seeded once per approach and reused
      across timed iterations (re-running the update is equivalent work).
    """
    row_count = max(1, min(int(row_count), MAX_BENCHMARK_ROW_COUNT))
    iterations = max(DEFAULT_BENCHMARK_ITERATIONS, int(iterations))
    run_id = uuid.uuid4().hex[:8]
    results = []

    def delete_prefix(prefix: str) -> None:
        ProductModel.objects.filter(sku__startswith=prefix).delete()

    # ---- CREATE: ingest a Parquet source + persist (realistic bulk create) ----
    create_funcs = {
        "drf_serializer_many": drf_create_from_parquet,
        "pandas": pandas_create_from_parquet,
        "mindoff": mindoff_create_from_parquet,
        "mindoff_lazy": mindoff_lazy_create_from_parquet,
    }
    create_prefixes = {a: f"C-{a}-{run_id}" for a in create_funcs}

    def create_spec(approach: str):
        prefix = create_prefixes[approach]
        func = create_funcs[approach]

        def make_timed():
            # Parquet source built once (cached) in setup, never timed; the
            # measured func only ingests the file and persists.
            path = ensure_source_parquet(prefix, row_count)
            return lambda: func(path)

        return approach, make_timed, lambda: delete_prefix(prefix)

    create_specs = [create_spec(a) for a in SCENARIO_APPROACHES["serializer_create"]]
    create_measurements, _ = _measure_scenario(
        "serializer_create", row_count, create_specs, iterations=iterations
    )
    results.extend(create_measurements)
    for prefix in create_prefixes.values():
        with contextlib.suppress(OSError, PermissionError):
            _source_parquet_path(prefix, row_count).unlink(missing_ok=True)

    # ---- READ: queryset -> Polars frame -> CSV ----
    read_prefix = f"R-{run_id}"
    delete_prefix(read_prefix)
    standard_bulk_create(deterministic_rows(row_count, read_prefix))

    def pandas_read_export():
        pandas_csv_export(
            read_prefix, row_count, _read_output_path("pandas_read", row_count)
        )

    def polars_naive_read_export():
        polars_naive_csv_export(
            read_prefix, row_count, _read_output_path("polars_naive_read", row_count)
        )

    def mindoff_read_export():
        # Eager path: ConnectorX (DB → Arrow directly) when outside a
        # transaction, falling back to Django cursor otherwise.
        qs = _read_qs(read_prefix, row_count)
        frm, _ = mo_crud_kit.read(qs, batch_size=1000, is_lazy=False)
        _csv_safe_frame(frm).write_csv(_read_output_path("mindoff_read", row_count))

    def mindoff_lazy_read_export():
        # Streaming path: stream_batches via fetchmany — never holds the full
        # result set in memory at once.
        qs = _read_qs(read_prefix, row_count)
        lazy_frame, _ = mo_crud_kit.read(qs, batch_size=1000, is_lazy=True)
        _csv_safe_frame(lazy_frame).sink_csv(
            _read_output_path("mindoff_lazy_read", row_count)
        )

    read_funcs = {
        "pandas": pandas_read_export,
        "polars_naive": polars_naive_read_export,
        "mindoff": mindoff_read_export,
        "mindoff_lazy": mindoff_lazy_read_export,
    }
    read_approaches = list(SCENARIO_APPROACHES["serializer_read"])
    read_specs = [
        (a, (lambda f=read_funcs[a]: f), None) for a in read_approaches
    ]
    read_measurements, csv_parity = _measure_scenario(
        "serializer_read",
        row_count,
        read_specs,
        iterations=iterations,
        parity_fn=lambda: _validate_read_csv_parity(row_count, read_approaches),
    )
    results.extend(read_measurements)
    delete_prefix(read_prefix)

    # ---- UPDATE: bulk upsert (pandas has no idiomatic bulk update -> N/A) ----
    update_funcs = {
        "drf_serializer_many": lambda p: drf_bulk_validated_update(p),
        "mindoff": lambda p: mindoff_update(p, validation_level="full"),
        "mindoff_lazy": lambda p: mindoff_lazy_update(p),
    }
    update_prefixes = {a: f"U-{a}-{run_id}" for a in update_funcs}

    def update_spec(approach: str):
        # Seed once and reuse across timed iterations: re-running the update on
        # the same rows is equivalent work, so this avoids re-seeding (the main
        # cost at high row counts) on every pass.
        prefix = update_prefixes[approach]
        delete_prefix(prefix)
        standard_bulk_create(deterministic_rows(row_count, prefix))
        products = list(
            ProductModel.objects.filter(sku__startswith=prefix).order_by("sku")
        )
        func = update_funcs[approach]
        return approach, (lambda: lambda: func(products)), None

    update_specs = [update_spec(a) for a in SCENARIO_APPROACHES["serializer_update"]]
    update_measurements, _ = _measure_scenario(
        "serializer_update", row_count, update_specs, iterations=iterations
    )
    results.extend(update_measurements)
    for prefix in update_prefixes.values():
        delete_prefix(prefix)

    save_metrics(results)
    return results, csv_parity


def _read_qs(prefix: str, row_count: int):
    """The shared ``.values()`` queryset the timed Mindoff read closures consume."""
    return (
        ProductModel.objects.filter(sku__startswith=prefix)
        .order_by("sku")
        .values()
    )[:row_count]


def _benchmark_counts(*, row_count: int | list[int]) -> list[int]:
    """Normalize a single count or list into a sorted, deduped, clamped list."""
    raw_counts = row_count if isinstance(row_count, list) else [row_count]
    return sorted({max(1, min(int(c), MAX_BENCHMARK_ROW_COUNT)) for c in raw_counts})


# Re-export for compatibility (the subprocess in measure.py imports this from here)
__all__ = [
    "import_products",
    "list_products_report",
    "run_product_benchmark",
    "run_product_benchmarks",
    "benchmark_file_lock",
    "Measurement",
    "measure",
    "_memory_probe_scenario_worker",
    "DEFAULT_BENCHMARK_ROW_COUNT",
    "DEFAULT_BENCHMARK_ITERATIONS",
]
