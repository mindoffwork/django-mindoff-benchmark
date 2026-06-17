"""Benchmark configuration: knobs, labels, ordering, colors, methodology.

This module is the *vocabulary* of the catalog benchmark. Everything here is a
pure constant or a dependency-free helper, so it sits at the bottom of the
package's import graph and every other module can read from it freely.

Methodology in one paragraph (the rest of the package implements it):

* **Source shape.** Bulk data is sourced from a Parquet file â€” the realistic
  shape (a file/export, not hand-built Python objects) â€” so each engine ingests
  it natively and the comparison reflects real bulk handling rather than
  Python-to-dataframe construction overhead.
* **One line-up per operation, both axes.** Each operation (create / read /
  update) is judged on *both* time and memory against the same set of rivals —
  every method that has a nominal workflow for that operation. See
  ``SCENARIO_APPROACHES``.
* **Skips are explicit.** A rival with no nominal workflow for an operation is
  dropped and marked with a ``*`` (footnote on the chart, dedicated row in the
  CSV ``remarks`` column) — see ``SKIPPED_COMBOS``. pandas has no idiomatic bulk
  *update*; DRF serializers don't construct dataframes, so they sit out *read*.
* **Read is queryset → Polars frame.** Mindoff's read goal is to hand back a
  Polars ``DataFrame``/``LazyFrame`` from a Django queryset as fast and lean as
  possible. The fair rivals are the realistic non-Mindoff ways to land that:
  native pandas (``pd.DataFrame.from_records``) and the true Polars baseline
  (``pl.DataFrame(list(qs))``).
* **Validation, kept honest.** The eager Mindoff path runs FULL validation (its
  validated bulk write); the lazy path streams with validation skipped (full
  validation would collect the LazyFrame and defeat streaming). pandas does no
  validation either, so lazy-vs-pandas is like-for-like on that front.
"""

from __future__ import annotations

from pathlib import Path

# --- Run sizing -------------------------------------------------------------
DEFAULT_BENCHMARK_ROW_COUNT = 5000
CHART_BENCHMARK_ROW_COUNT = 5000
MAX_BENCHMARK_ROW_COUNT = 1_000_000
DEFAULT_BENCHMARK_ITERATIONS = 5
DEFAULT_BENCHMARK_WARMUPS = 1

# --- Display labels & ordering (used by CSV export and charts) --------------
SCENARIO_LABELS = {
    "serializer_create": "Create",
    "serializer_read": "Read",
    "serializer_update": "Update",
}

APPROACH_LABELS = {
    "drf_serializer_many": "DRF serializer + bulk",
    "pandas": "pandas",
    "polars_naive": "polars (naive)",
    "mindoff": "django-mindoff (eager)",
    "mindoff_lazy": "django-mindoff (stream)",
}

SCENARIO_ORDER = {
    "serializer_create": 1,
    "serializer_read": 2,
    "serializer_update": 3,
}

APPROACH_ORDER = {
    "drf_serializer_many": 1,
    "pandas": 2,
    "polars_naive": 3,
    "mindoff": 4,
    "mindoff_lazy": 5,
}

# --- Which approaches are compared, per scenario ----------------------------
# Both the time and the memory chart for a scenario show this SAME line-up:
# every method that runs a nominal workflow for that operation. (Earlier the two
# axes showed different rivals; now each operation is judged on both axes against
# one consistent set.) Anything missing here is intentionally skipped — see
# ``SKIPPED_COMBOS`` for the reason.
SCENARIO_APPROACHES = {
    # create/update: pure DRF vs pandas vs django-mindoff, same-work bulk persist.
    "serializer_create": ("drf_serializer_many", "pandas", "mindoff", "mindoff_lazy"),
    # read: queryset -> Polars frame. pandas (native DataFrame) and polars_naive
    # (pl.DataFrame(list(qs)), the true baseline) vs Mindoff eager/stream.
    "serializer_read": ("pandas", "polars_naive", "mindoff", "mindoff_lazy"),
    # update: DRF vs django-mindoff (pandas skipped — no idiomatic bulk update).
    "serializer_update": ("drf_serializer_many", "mindoff", "mindoff_lazy"),
}

# --- Comparisons deliberately skipped (the "*" notes) -----------------------
# A rival is skipped for an operation when it has no nominal workflow for it.
# The reason is surfaced as a "*" footnote on that operation's chart and as a
# dedicated row in the CSV ``remarks`` column.
SKIPPED_COMBOS = {
    ("serializer_read", "drf_serializer_many"): (
        "DRF serializers target API representation, not queryset->dataframe "
        "construction, so they are not a nominal queryset->Polars-frame path."
    ),
    ("serializer_update", "pandas"): (
        "pandas has no idiomatic bulk-update path."
    ),
}

# --- Validation posture, disclosed per line ---------------------------------
# create/update lines do NOT all do equal work: the validated paths run full
# validation, the rest write straight through. Surfaced as a legend suffix on
# the chart and in the CSV "remarks" column so a reviewer sees, at a glance,
# that "mindoff (eager)" and "pandas" are not the same workload. (read does no
# validation on any line — it's a read — so it has no entries here.)
APPROACH_VALIDATION = {
    ("serializer_create", "drf_serializer_many"): "validated",
    ("serializer_create", "pandas"): "no validation",
    ("serializer_create", "mindoff"): "validated",
    ("serializer_create", "mindoff_lazy"): "no validation",
    ("serializer_update", "drf_serializer_many"): "validated",
    ("serializer_update", "mindoff"): "validated",
    ("serializer_update", "mindoff_lazy"): "no validation",
}

# --- Read materialization, disclosed per line -------------------------------
# The read endpoint is "queryset -> frame -> CSV". Each engine builds the frame
# its own way AND (for pandas) writes CSV with its own writer, so the pandas line
# blends two differences. The mindoff-vs-polars_naive pair is the clean
# comparison (both Polars frames, both Polars CSV writer — isolating only the
# ConnectorX-vs-Python-dicts build step). Disclosed in the CSV "remarks" column.
READ_MATERIALIZATION_NOTE = {
    "pandas": "frame via pandas.DataFrame.from_records; CSV via pandas to_csv",
    "polars_naive": "frame via pl.DataFrame(list(qs)); CSV via Polars write_csv",
    "mindoff": "frame via ConnectorX DB->Arrow; CSV via Polars write_csv",
    "mindoff_lazy": "frame via streaming fetchmany; CSV via Polars sink_csv",
}

# --- Per-chart caveat line (shown under the "*" skip notes) ------------------
SCENARIO_CAVEATS = {
    "serializer_create": "Lines differ in validation level — see the legend.",
    "serializer_update": "Lines differ in validation level — see the legend.",
    "serializer_read": (
        "Each engine builds its frame differently; pandas also writes CSV with "
        "its own writer (the others use Polars). The mindoff vs polars (naive) "
        "pair isolates the frame-build difference cleanly."
    ),
}

# --- Chart palette ----------------------------------------------------------
DRF_COLOR = "#9CA3AF"
PANDAS_COLOR = "#2563EB"
POLARS_COLOR = "#F59E0B"
MINDOFF_COLOR = "#00C853"
MINDOFF_LAZY_COLOR = "#00897B"

# --- Chart output filenames (one file per operation, time + memory panels) --
SCENARIO_CHART_FILENAMES = {
    "serializer_create": "catalog_benchmark_create.png",
    "serializer_read": "catalog_benchmark_read.png",
    "serializer_update": "catalog_benchmark_update.png",
}

SCENARIO_EXPORT_KEYS = {
    "serializer_create": "create_chart",
    "serializer_read": "read_chart",
    "serializer_update": "update_chart",
}

# --- Cross-process coordination ---------------------------------------------
# A single file lock serializes concurrent benchmark runs so they don't fight
# over the shared DB / output directory.
BENCHMARK_LOCK_PATH = Path("output") / "catalog_benchmark.lock"


def _query_count_note(approach: str) -> str:
    """Explain how an approach's ``query_count`` should be read.

    Query count is diagnostic only (per AGENTS.md S6.7): Mindoff write paths may
    persist via a route Django's cursor instrumentation never sees, so a ``0``
    there does not mean "no database work happened".
    """
    if "mindoff" in approach:
        return "Mindoff writes may bypass Django cursor capture; 0 does not mean no DB work."
    return "Captured via Django CaptureQueriesContext in a separate pass."

