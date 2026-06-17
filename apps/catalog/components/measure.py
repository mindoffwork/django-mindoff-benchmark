"""How every benchmark number is measured — time, memory, and query count.

If ``create``, ``read``, and ``update`` answer "is the compared work equivalent?",
this module answers "is the *measurement* unbiased?". The guarantees it enforces
(per AGENTS.md S6):

* **Separate passes.** Wall time, memory, and query count run in independent
  passes so instrumentation for one never taxes another.
* **Warmup + median.** Every metric runs at least one warmup then >= 5 measured
  iterations and reports the median, smoothing out cold-cache and OS-scheduling
  noise.
* **Real RSS.** Memory is peak resident-set-size *delta*, sampled by a background
  thread, so native Polars/Arrow allocations (invisible to Python's own allocator
  stats) are counted.
* **Warm heavy libs out of the delta.** ConnectorX (the eager Mindoff read
  engine) loads its Rust runtime + Arrow memory pools on first import — a
  one-time tens-of-MB RSS jump. ``_warm_heavy_libs`` triggers that *before* the
  memory baseline is taken, so it lands in the baseline, not in Mindoff's read
  delta (pandas/polars are already imported at module load and pay nothing
  comparable). Without this the read-memory number is dominated by import cost,
  not data.

**One subprocess per scenario.** Outside pytest the memory pass runs in a fresh
subprocess for an uncontaminated RSS baseline. To keep 100k-row runs fast, a
*single* subprocess now measures every approach for a scenario: it seeds the
shared fixture once, warms the heavy libs once, then self-measures each
approach's peak-RSS delta from a fresh local baseline (``gc`` + re-baseline
between approaches). This collapses ~10 subprocess spawns + reseeds per row count
down to 3, the single biggest speedup for large runs.

Reading order: ``Measurement`` (the result schema) → ``_measure_scenario`` (the
unified time+memory+query driver every scenario flows through) → the subprocess
memory-probe plumbing below it.
"""

from __future__ import annotations

import contextlib
import gc
import json
import os
import statistics
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path

import psutil
from django.db import close_old_connections, connection
from django.test.utils import CaptureQueriesContext
from django_mindoff import mo_crud_kit

from apps.catalog.models import ProductModel
from apps.catalog.components.config import (
    DEFAULT_BENCHMARK_ITERATIONS,
    DEFAULT_BENCHMARK_WARMUPS,
    _query_count_note,
)
from apps.catalog.components.fixtures import (
    _csv_safe_frame,
    _read_output_path,
    _source_parquet_path,
    deterministic_rows,
    ensure_source_parquet,
)
from apps.catalog.components.create import (
    drf_create_from_parquet,
    mindoff_create_from_parquet,
    mindoff_lazy_create_from_parquet,
    pandas_create_from_parquet,
    standard_bulk_create,
)
from apps.catalog.components.read import (
    pandas_csv_export,
    polars_naive_csv_export,
)
from apps.catalog.components.update import (
    drf_bulk_validated_update,
    mindoff_lazy_update,
    mindoff_update,
)


# ---------------------------------------------------------------------------
# Result schema
# ---------------------------------------------------------------------------
@dataclass
class Measurement:
    """One approach's result for one scenario at one row count.

    ``as_dict`` is the serialized shape persisted, charted, and returned to API
    callers — it rounds for display and derives ``time_seconds`` from ``time_ms``.
    """

    approach: str
    scenario: str
    row_count: int
    time_ms: float
    memory_mb: float
    query_count: int
    iterations: int = 5
    warmup_iterations: int = 1
    backend: str = ""
    memory_metric: str = "peak_rss_delta_mb"
    query_count_note: str = ""

    def as_dict(self) -> dict:
        return {
            "approach": self.approach,
            "scenario": self.scenario,
            "row_count": self.row_count,
            "time_ms": round(self.time_ms, 2),
            "time_seconds": round(self.time_ms / 1000, 2),
            "memory_mb": round(self.memory_mb, 2),
            "query_count": self.query_count,
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "backend": self.backend,
            "memory_metric": self.memory_metric,
            "query_count_note": self.query_count_note,
        }


# ---------------------------------------------------------------------------
# Single-operation measurement (used by import_products)
# ---------------------------------------------------------------------------
def measure(
    approach: str,
    scenario: str,
    row_count: int,
    func_factory,
    *,
    cleanup=None,
    iterations: int = DEFAULT_BENCHMARK_ITERATIONS,
    warmup_iterations: int = DEFAULT_BENCHMARK_WARMUPS,
) -> Measurement:
    """Time, memory- and query-profile one operation in three separate passes.

    ``func_factory`` is a *factory of factories*: calling it returns the callable
    to time, so each iteration gets a freshly-prepared operation (and its own
    fixture state) without setup leaking into the timed region. ``cleanup`` runs
    after each call to keep iterations independent.

    Memory is measured in-process here (this entry point is used by the small
    ``import_products`` probe); the row-count sweep uses ``_measure_scenario``,
    which isolates memory in a per-scenario subprocess.
    """
    iterations = max(DEFAULT_BENCHMARK_ITERATIONS, int(iterations))
    warmup_iterations = max(1, int(warmup_iterations))
    timings = []

    # --- Pass 1: wall time (warmup iterations discarded) ---
    for index in range(warmup_iterations + iterations):
        _release_db_connections()
        func = func_factory()
        start = time.perf_counter()
        func()
        elapsed_ms = (time.perf_counter() - start) * 1000
        if cleanup:
            cleanup()
        _release_db_connections()
        if index >= warmup_iterations:
            timings.append(elapsed_ms)

    # --- Pass 2: peak RSS delta (in-process) ---
    _release_db_connections()
    memory_func = func_factory()
    memory_mb = _measure_peak_rss_delta_mb(memory_func)
    if cleanup:
        cleanup()
    _release_db_connections()

    # --- Pass 3: query count (diagnostic only — see config._query_count_note) ---
    query_func = func_factory()
    with CaptureQueriesContext(connection) as ctx:
        query_func()
    if cleanup:
        cleanup()
    _release_db_connections()

    return Measurement(
        approach=approach,
        scenario=scenario,
        row_count=row_count,
        time_ms=statistics.median(timings),
        memory_mb=memory_mb,
        query_count=len(ctx.captured_queries),
        iterations=iterations,
        warmup_iterations=warmup_iterations,
        backend=connection.vendor,
        query_count_note=_query_count_note(approach),
    )


# ---------------------------------------------------------------------------
# Unified per-scenario measurement (create / read / update)
# ---------------------------------------------------------------------------
def _measure_scenario(
    scenario: str,
    row_count: int,
    specs: list,
    *,
    iterations: int = DEFAULT_BENCHMARK_ITERATIONS,
    warmup_iterations: int = DEFAULT_BENCHMARK_WARMUPS,
    parity_fn=None,
) -> tuple[list[dict], dict | None]:
    """Drive time + memory + query passes for every approach in one scenario.

    ``specs`` is a list of ``(approach, make_timed, after_iter)`` where
    ``make_timed()`` returns the callable to time (fresh per iteration) and
    ``after_iter`` (or ``None``) runs after each call to keep iterations
    independent. All approaches are timed in one shared loop (one warmup then N
    measured) so timing happens under identical OS conditions.

    Memory is isolated per scenario: a single subprocess outside pytest
    (uncontaminated baseline, seeded once), in-process under pytest. Query count
    is captured per approach in a final pass. ``parity_fn`` (read only) runs
    after the timing loop, while the output CSVs still exist, and is returned
    alongside the measurements.
    """
    iterations = max(DEFAULT_BENCHMARK_ITERATIONS, int(iterations))
    warmup_iterations = max(1, int(warmup_iterations))
    approaches = [approach for approach, _, _ in specs]

    # --- Pass 1: wall time, shared loop across approaches ---
    timings: dict[str, list[float]] = {approach: [] for approach in approaches}
    for pass_i in range(warmup_iterations + iterations):
        _release_db_connections()
        for approach, make_timed, after_iter in specs:
            func = make_timed()
            start = time.perf_counter()
            func()
            elapsed_ms = (time.perf_counter() - start) * 1000
            if after_iter:
                after_iter()
            if pass_i >= warmup_iterations:
                timings[approach].append(elapsed_ms)
        _release_db_connections()

    # Parity (read): output CSVs are on disk after the last timing pass.
    parity = parity_fn() if parity_fn else None

    # --- Pass 2: peak RSS delta ---
    if os.environ.get("PYTEST_CURRENT_TEST"):
        _warm_heavy_libs(scenario)
        memory_mb: dict[str, float] = {}
        for approach, make_timed, after_iter in specs:
            memory_mb[approach] = _measure_peak_rss_delta_mb(make_timed())
            if after_iter:
                after_iter()
            _release_db_connections()
    else:
        memory_mb = _measure_scenario_peak_rss_delta_mb(
            scenario, row_count, approaches
        )

    # --- Pass 3: query count (diagnostic only) ---
    measurements = []
    for approach, make_timed, after_iter in specs:
        query_func = make_timed()
        with CaptureQueriesContext(connection) as ctx:
            query_func()
        if after_iter:
            after_iter()
        _release_db_connections()
        measurements.append(
            Measurement(
                approach=approach,
                scenario=scenario,
                row_count=row_count,
                time_ms=statistics.median(timings[approach]),
                memory_mb=memory_mb.get(approach, 0.0),
                query_count=len(ctx.captured_queries),
                iterations=iterations,
                warmup_iterations=warmup_iterations,
                backend=connection.vendor,
                query_count_note=_query_count_note(approach),
            ).as_dict()
        )
    return measurements, parity


# ---------------------------------------------------------------------------
# DB connection hygiene between passes
# ---------------------------------------------------------------------------
def _release_db_connections() -> None:
    """Drop pooled/idle connections so each pass starts from a clean DB state."""
    close_old_connections()
    if connection.vendor == "sqlite":
        connection.close()


# ---------------------------------------------------------------------------
# Warming heavy lazily-imported deps out of the memory delta
# ---------------------------------------------------------------------------
def _warm_heavy_libs(scenario: str) -> None:
    """Import + initialize ConnectorX BEFORE the memory baseline is taken.

    ConnectorX loads its Rust runtime and Arrow memory pools on first import — a
    one-time RSS jump of tens of MB. If that landed inside the measured region it
    would be charged entirely to Mindoff's eager read (pandas/polars are imported
    at module load and pay nothing comparable), making the read-memory number a
    measure of import cost rather than data. Warming it here folds that fixed
    cost into the baseline. Best-effort: any failure leaves the cold path intact.
    """
    with contextlib.suppress(Exception):
        import connectorx  # noqa: F401
    with contextlib.suppress(Exception):
        # A 1-row real read drives ConnectorX's DB->Arrow path + pool allocation
        # (a no-op when no rows exist yet, e.g. the create scenario).
        qs = ProductModel.objects.all().values()[:1]
        mo_crud_kit.read(qs, is_lazy=False, with_stats=False)


# ---------------------------------------------------------------------------
# Per-scenario memory runners (shared by the subprocess worker)
# ---------------------------------------------------------------------------
def _read_runner(approach: str, prefix: str, row_count: int):
    """Build the measured read operation for one approach (queryset → frame → CSV)."""
    def out(name: str) -> Path:
        return _read_output_path(name, row_count)

    def qs():
        return (
            ProductModel.objects.filter(sku__startswith=prefix)
            .order_by("sku")
            .values()
        )[:row_count]

    if approach == "pandas":
        return lambda: pandas_csv_export(prefix, row_count, out("pandas_read_memory"))
    if approach == "polars_naive":
        return lambda: polars_naive_csv_export(
            prefix, row_count, out("polars_naive_read_memory")
        )
    if approach == "mindoff":
        def run() -> None:
            frm, _ = mo_crud_kit.read(qs(), batch_size=1000, is_lazy=False)
            _csv_safe_frame(frm).write_csv(out("mindoff_read_memory"))
        return run
    if approach == "mindoff_lazy":
        def run() -> None:
            lazy_frame, _ = mo_crud_kit.read(qs(), batch_size=1000, is_lazy=True)
            _csv_safe_frame(lazy_frame).sink_csv(out("mindoff_lazy_read_memory"))
        return run
    raise ValueError(f"Unsupported read approach: {approach}")


def _update_runner(approach: str, products: list):
    if approach == "drf_serializer_many":
        return lambda: drf_bulk_validated_update(products)
    if approach == "mindoff":
        return lambda: mindoff_update(products, validation_level="full")
    if approach == "mindoff_lazy":
        return lambda: mindoff_lazy_update(products)
    raise ValueError(f"Unsupported update approach: {approach}")


_CREATE_FUNCS = {
    "drf_serializer_many": drf_create_from_parquet,
    "pandas": pandas_create_from_parquet,
    "mindoff": mindoff_create_from_parquet,
    "mindoff_lazy": mindoff_lazy_create_from_parquet,
}


def _prepare_scenario_runners(
    scenario: str, prefix: str, row_count: int, approaches: list
) -> list:
    """Seed the shared fixture once and return ``(approach, runner, cleanup)`` per approach.

    * read/update seed one prefix of ``row_count`` rows and reuse it (reads don't
      mutate; re-running an update is equivalent work).
    * create gives each approach its own prefix-scoped Parquet source and a
      cleanup that deletes its inserted rows, so the next approach starts clean
      (the Parquet ids/SKUs are fixed, so without per-approach prefixes they'd
      collide on the primary key).
    """
    if scenario == "serializer_read":
        standard_bulk_create(deterministic_rows(row_count, prefix))
        return [(a, _read_runner(a, prefix, row_count), None) for a in approaches]

    if scenario == "serializer_update":
        standard_bulk_create(deterministic_rows(row_count, prefix))
        products = list(
            ProductModel.objects.filter(sku__startswith=prefix).order_by("sku")
        )
        return [(a, _update_runner(a, products), None) for a in approaches]

    if scenario == "serializer_create":
        runners = []
        for a in approaches:
            ap_prefix = f"{prefix}-{a}"
            path = ensure_source_parquet(ap_prefix, row_count)
            runners.append(
                (
                    a,
                    (lambda func=_CREATE_FUNCS[a], p=path: lambda: func(p))(),
                    (lambda pre=ap_prefix: lambda: ProductModel.objects.filter(
                        sku__startswith=pre
                    ).delete())(),
                )
            )
        return runners

    raise ValueError(f"Unsupported scenario: {scenario}")


# ---------------------------------------------------------------------------
# Memory measurement — in-process (test suite) and subprocess (real runs)
# ---------------------------------------------------------------------------
def _measure_peak_rss_delta_mb(func) -> float:
    """In-process peak-RSS delta: sample RSS on a background thread while ``func`` runs.

    The sampler polls every 1 ms so short native allocations are still caught.
    Used under pytest and as the per-approach measurement inside the subprocess
    worker (which re-baselines + ``gc`` between approaches).
    """
    gc.collect()
    baseline = _current_rss_bytes()
    peak = baseline
    stop_event = threading.Event()

    def sample_rss() -> None:
        nonlocal peak
        while not stop_event.is_set():
            peak = max(peak, _current_rss_bytes())
            time.sleep(0.001)

    sampler = threading.Thread(target=sample_rss, daemon=True)
    sampler.start()
    try:
        func()
        peak = max(peak, _current_rss_bytes())
    finally:
        stop_event.set()
        sampler.join(timeout=1)
    gc.collect()
    return max(0, peak - baseline) / (1024 * 1024)


def _measure_scenario_peak_rss_delta_mb(
    scenario: str, row_count: int, approaches: list
) -> dict[str, float]:
    """Measure every approach's peak-RSS delta for a scenario in one subprocess.

    A fresh subprocess gives an identical, uncontaminated baseline; measuring all
    approaches in it (seed once, warm once, self-measure each from a re-taken
    local baseline) is the big win for large runs over spawning one subprocess
    per approach. The child writes a ``ready`` file once it has seeded + warmed,
    then a ``done`` file carrying ``{approach: peak_delta_mb}``. The handshake
    uses files rather than pipes to stay deadlock-free on Windows.
    """
    probe_dir = Path("output") / "memory_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_id = uuid.uuid4().hex
    ready_path = probe_dir / f"{probe_id}.ready.json"
    done_path = probe_dir / f"{probe_id}.done.json"
    case = json.dumps(
        {"scenario": scenario, "row_count": row_count, "approaches": list(approaches)}
    )
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings"}
    command = [
        sys.executable,
        "-c",
        (
            "import os, django; "
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); "
            "django.setup(); "
            "from apps.catalog.components.products import _memory_probe_scenario_worker; "
            "import sys; _memory_probe_scenario_worker(sys.argv[1], sys.argv[2], sys.argv[3])"
        ),
        case,
        str(ready_path),
        str(done_path),
    ]
    process = subprocess.Popen(
        command,
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 600
        while not ready_path.exists() and process.poll() is None:
            if time.monotonic() > deadline:
                process.terminate()
                process.wait(timeout=5)
                raise TimeoutError("Memory benchmark worker did not become ready.")
            time.sleep(0.01)
        if not ready_path.exists():
            stdout, stderr = process.communicate(timeout=5)
            raise RuntimeError(
                "Memory benchmark worker exited before becoming ready.\n"
                f"{stderr or stdout}"
            )
        ready_message = json.loads(ready_path.read_text(encoding="utf-8"))
        if ready_message["status"] != "ready":
            raise RuntimeError(ready_message["error"])

        while process.poll() is None:
            if done_path.exists():
                break
            time.sleep(0.01)
        stdout, stderr = process.communicate(timeout=30)
        if not done_path.exists():
            raise RuntimeError(
                f"Memory benchmark worker exited with code {process.returncode}.\n"
                f"{stderr or stdout}"
            )
        done_message = json.loads(done_path.read_text(encoding="utf-8"))
        if done_message["status"] == "error":
            raise RuntimeError(done_message["error"])
        deltas = done_message.get("deltas", {})
        return {a: float(deltas.get(a, 0.0)) for a in approaches}
    finally:
        if process.poll() is None:
            process.terminate()
            with contextlib.suppress(Exception):
                process.wait(timeout=5)
        with contextlib.suppress(OSError):
            ready_path.unlink()
        with contextlib.suppress(OSError):
            done_path.unlink()


def _memory_probe_scenario_worker(
    case_json: str,
    ready_path_value: str,
    done_path_value: str,
) -> None:
    """Subprocess entry point called by ``_measure_scenario_peak_rss_delta_mb``.

    Seeds the scenario's shared fixture once, warms the heavy libs, signals
    ``ready`` (so setup + warming are excluded from every measurement), then
    self-measures each approach's peak-RSS delta from a fresh local baseline and
    writes ``done`` with ``{approach: delta_mb}``. Always cleans up its rows and
    Parquet sources on exit.
    """
    ready_path = Path(ready_path_value)
    done_path = Path(done_path_value)
    prefix = None
    row_count = 0
    approaches: list = []
    try:
        case = json.loads(case_json)
        scenario = case["scenario"]
        row_count = int(case["row_count"])
        approaches = list(case["approaches"])

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        from django.apps import apps as django_apps

        if not django_apps.ready:
            django.setup()

        prefix = f"MEM-{scenario.upper()}-{uuid.uuid4().hex[:8]}"
        runners = _prepare_scenario_runners(scenario, prefix, row_count, approaches)
        _warm_heavy_libs(scenario)
        gc.collect()
        ready_path.write_text(
            json.dumps({"status": "ready", "rss_bytes": _current_rss_bytes()}),
            encoding="utf-8",
        )

        deltas = {}
        for approach, runner, cleanup in runners:
            deltas[approach] = _measure_peak_rss_delta_mb(runner)
            if cleanup:
                with contextlib.suppress(Exception):
                    cleanup()
            gc.collect()

        done_path.write_text(
            json.dumps({"status": "ok", "deltas": deltas}), encoding="utf-8"
        )
    except Exception:
        error_payload = json.dumps({"status": "error", "error": traceback.format_exc()})
        if not ready_path.exists():
            with contextlib.suppress(Exception):
                ready_path.write_text(error_payload, encoding="utf-8")
        with contextlib.suppress(Exception):
            done_path.write_text(error_payload, encoding="utf-8")
        raise
    finally:
        with contextlib.suppress(Exception):
            if prefix:
                # The prefix filter also catches create's per-approach
                # `{prefix}-{approach}` rows, so one delete covers them all.
                ProductModel.objects.filter(sku__startswith=prefix).delete()
                for approach in approaches:
                    _source_parquet_path(
                        f"{prefix}-{approach}", row_count
                    ).unlink(missing_ok=True)
            _release_db_connections()


def _current_rss_bytes() -> int:
    """Real resident-set size of this process, cross-platform via psutil."""
    return psutil.Process().memory_info().rss
