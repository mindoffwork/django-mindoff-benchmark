"""Turning metrics into the deliverables a reviewer actually looks at.

Outputs, all written to ``output/``:

* ``catalog_benchmark_values.csv`` — the raw numbers, plus a ``remarks`` column
  that records every deliberately-skipped comparison and why (``build_benchmark_csv``).
* three line-chart files — one per operation (``catalog_benchmark_create.png`` /
  ``_read.png`` / ``_update.png``), each with a time panel and a memory panel
  (``build_benchmark_charts``).

Line charts (value vs. row count) are deliberately chosen over bar charts: bulk
handling is a story about *slope*, so plotting each method as the dataset grows
is the fair way to compare. Every operation is judged on both time and memory
against the same line-up (``config.SCENARIO_APPROACHES``); a rival with no
nominal workflow for an operation is skipped and called out with a ``*`` footnote
(``config.SKIPPED_COMBOS``).

Both builders fall back to running a fresh benchmark when handed no metrics; that
fallback imports ``run_product_benchmark`` from ``products`` lazily (inside the
function body) to keep the import graph acyclic — ``products.py`` imports this
module at the top level, so the reverse import must be deferred.
"""

from __future__ import annotations

import contextlib
import csv
import textwrap
from pathlib import Path

from django.db import connection

from apps.catalog.components.config import (
    APPROACH_LABELS,
    APPROACH_ORDER,
    APPROACH_VALIDATION,
    CHART_BENCHMARK_ROW_COUNT,
    DEFAULT_BENCHMARK_ITERATIONS,
    DEFAULT_BENCHMARK_ROW_COUNT,
    DEFAULT_BENCHMARK_WARMUPS,
    DRF_COLOR,
    MINDOFF_COLOR,
    MINDOFF_LAZY_COLOR,
    PANDAS_COLOR,
    POLARS_COLOR,
    READ_MATERIALIZATION_NOTE,
    SCENARIO_APPROACHES,
    SCENARIO_CAVEATS,
    SCENARIO_CHART_FILENAMES,
    SCENARIO_EXPORT_KEYS,
    SCENARIO_LABELS,
    SCENARIO_ORDER,
    SKIPPED_COMBOS,
    _query_count_note,
)
from apps.catalog.components.storage import latest_metrics


# ---------------------------------------------------------------------------
# CSV deliverable
# ---------------------------------------------------------------------------
CSV_FIELDNAMES = [
    "scenario",
    "approach",
    "row_count",
    "time_ms",
    "time_seconds",
    "memory_mb",
    "query_count",
    "query_count_note",
    "iterations",
    "warmup_iterations",
    "backend",
    "memory_metric",
    "remarks",
]


def build_benchmark_csv(metrics: list[dict] | None = None) -> Path:
    """Write the canonical benchmark CSV and return its path.

    Falls back to stored metrics, then to a fresh run, when none are supplied.
    Skipped comparisons (``config.SKIPPED_COMBOS``) are appended as dedicated
    rows whose ``remarks`` column carries the ``*`` reason.
    """
    metrics = list(metrics or reversed(latest_metrics()))
    if not metrics:
        from apps.catalog.components.products import run_product_benchmark

        metrics, _ = run_product_benchmark(row_count=DEFAULT_BENCHMARK_ROW_COUNT)
    metrics = _sorted_metrics(metrics)

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "catalog_benchmark_values.csv"

    with out_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for metric in metrics:
            writer.writerow(_csv_row(metric))
        for row in _skipped_csv_rows(metrics):
            writer.writerow(row)

    return out_path


def _csv_row(metric: dict) -> dict:
    return {
        "scenario": metric["scenario"],
        "approach": metric["approach"],
        "row_count": metric["row_count"],
        "time_ms": f"{metric['time_ms']:.2f}",
        "time_seconds": f"{metric['time_seconds']:.2f}",
        "memory_mb": f"{metric['memory_mb']:.2f}",
        "query_count": metric["query_count"],
        "query_count_note": metric.get(
            "query_count_note", _query_count_note(metric["approach"])
        ),
        "iterations": metric.get("iterations", DEFAULT_BENCHMARK_ITERATIONS),
        "warmup_iterations": metric.get("warmup_iterations", DEFAULT_BENCHMARK_WARMUPS),
        "backend": metric.get("backend", connection.vendor),
        "memory_metric": metric.get("memory_metric", "peak_rss_delta_mb"),
        "remarks": _approach_remark(metric["scenario"], metric["approach"]),
    }


def _approach_remark(scenario: str, approach: str) -> str:
    """Per-line disclosure: validation posture and (for read) how it materializes.

    Makes the workload asymmetries visible in the CSV itself — a "validated" line
    does strictly more work than a "no validation" one, and the read engines
    differ in how they build the frame and write the CSV.
    """
    parts = []
    validation = APPROACH_VALIDATION.get((scenario, approach))
    if validation:
        parts.append(f"{validation} bulk write")
    if scenario == "serializer_read" and approach in READ_MATERIALIZATION_NOTE:
        parts.append(READ_MATERIALIZATION_NOTE[approach])
    return "; ".join(parts)


def _skipped_csv_rows(metrics: list[dict]) -> list[dict]:
    """One row per skipped (scenario, approach), at each measured row count.

    Blank metric fields and a ``* <reason>`` remark, so the CSV documents exactly
    which comparison was dropped for which operation and why.
    """
    row_counts = sorted({m["row_count"] for m in metrics})
    rows = []
    for (scenario, approach), reason in SKIPPED_COMBOS.items():
        for row_count in row_counts:
            rows.append(
                {
                    "scenario": scenario,
                    "approach": approach,
                    "row_count": row_count,
                    "time_ms": "",
                    "time_seconds": "",
                    "memory_mb": "",
                    "query_count": "",
                    "query_count_note": "",
                    "iterations": "",
                    "warmup_iterations": "",
                    "backend": "",
                    "memory_metric": "",
                    "remarks": f"* skipped — {reason}",
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Chart deliverables
# ---------------------------------------------------------------------------
def build_benchmark_charts(metrics: list[dict] | None = None) -> dict[str, Path]:
    """Build one chart file per operation (create / read / update).

    Each file has a time panel and a memory panel; both show the same line-up of
    methods (``config.SCENARIO_APPROACHES``) as the row count grows, with skipped
    rivals called out in a ``*`` footnote.
    """
    metrics = list(metrics or reversed(latest_metrics()))
    if not metrics:
        from apps.catalog.components.products import run_product_benchmark

        metrics, _ = run_product_benchmark(row_count=CHART_BENCHMARK_ROW_COUNT)
    metrics = _sorted_metrics(metrics)
    series = _metric_series(metrics)

    return {
        SCENARIO_EXPORT_KEYS[scenario]: _build_scenario_chart(scenario, series)
        for scenario in SCENARIO_ORDER
    }


def _build_scenario_chart(scenario: str, series: dict) -> Path:
    """Render one operation's time + memory line charts into a single file."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    approaches = SCENARIO_APPROACHES[scenario]
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / SCENARIO_CHART_FILENAMES[scenario]

    fig, (ax_time, ax_mem) = plt.subplots(1, 2, figsize=(13, 6.0))
    _plot_panel(
        ax_time, scenario, approaches, series,
        field="time_seconds", ylabel="Seconds", title="Time — lower is better",
    )
    _plot_panel(
        ax_mem, scenario, approaches, series,
        field="memory_mb", ylabel="Peak RSS delta (MB)",
        title="Memory — lower is better",
    )

    fig.suptitle(
        f"{SCENARIO_LABELS[scenario]}: {_comparison_label(scenario)}",
        fontsize=18,
        fontweight="bold",
    )

    # The "*" skip note lives in its own reserved band along the bottom (wrapped
    # so it never runs off the figure), clear of the x-axis labels rather than
    # overlapping them.
    notes = _chart_notes(scenario)
    note_text = "\n".join(textwrap.fill(note, width=145) for note in notes)
    note_lines = (note_text.count("\n") + 1) if notes else 0
    bottom_margin = (0.05 + 0.032 * note_lines) if notes else 0.08
    fig.tight_layout(rect=(0, bottom_margin, 1, 0.94))
    if notes:
        fig.text(
            0.012, 0.012, note_text,
            fontsize=8.5, style="italic", color="#555555",
            ha="left", va="bottom", linespacing=1.4,
        )
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def _plot_panel(axis, scenario, approaches, series, *, field, ylabel, title) -> None:
    panel_max = 0.0
    for approach in approaches:
        items = series.get((scenario, approach), [])
        if not items:
            continue
        is_mindoff = _is_mindoff(approach)
        y_vals = [item[field] for item in items]
        panel_max = max(panel_max, max(y_vals))
        # Prepend the origin so every line starts from (0, 0): at zero rows both
        # time and memory are zero, and anchoring there makes the slope of each
        # approach visually comparable from a common baseline.
        x_plot = [0] + [item["row_count"] for item in items]
        y_plot = [0.0] + y_vals
        axis.plot(
            x_plot,
            y_plot,
            label=_chart_label(scenario, approach),
            color=_approach_color(approach),
            marker=_approach_marker(approach),
            linestyle=_approach_linestyle(approach),
            linewidth=3.2 if is_mindoff else 2.2,
            alpha=1.0 if is_mindoff else 0.72,
        )
    axis.set_title(title, fontsize=14, fontweight="bold")
    axis.set_xlabel("Rows")
    axis.set_ylabel(ylabel)
    # Always start at 0 so the reader can judge absolute magnitude, not just
    # relative distance between lines. Add 15 % headroom so lines don't touch the
    # top border and the legend has room to breathe.
    axis.set_ylim(bottom=0, top=panel_max * 1.15 if panel_max > 0 else 1)
    axis.grid(axis="y", alpha=0.18)
    axis.ticklabel_format(style="plain", axis="x")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    if axis.get_legend_handles_labels()[1]:
        axis.legend(loc="best", frameon=False, fontsize=9)


# ---------------------------------------------------------------------------
# Presentation rules (ordering, palette, labels)
# ---------------------------------------------------------------------------
def _sorted_metrics(metrics: list[dict]) -> list[dict]:
    """Stable sort into (row_count, scenario, approach) display order."""
    return sorted(
        metrics,
        key=lambda m: (
            m["row_count"],
            SCENARIO_ORDER.get(m["scenario"], 99),
            APPROACH_ORDER.get(m["approach"], 99),
            m["approach"],
        ),
    )


def _metric_series(metrics: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group metrics into per-(scenario, approach) series sorted by row count."""
    series: dict[tuple[str, str], list[dict]] = {}
    for metric in metrics:
        key = (metric["scenario"], metric["approach"])
        series.setdefault(key, []).append(metric)
    return {
        key: sorted(items, key=lambda item: item["row_count"])
        for key, items in series.items()
    }


def _approach_color(approach: str) -> str:
    return {
        "mindoff": MINDOFF_COLOR,
        "mindoff_lazy": MINDOFF_LAZY_COLOR,
        "pandas": PANDAS_COLOR,
        "polars_naive": POLARS_COLOR,
    }.get(approach, DRF_COLOR)


def _approach_marker(approach: str) -> str:
    return {
        "mindoff": "o",
        "mindoff_lazy": "D",
        "pandas": "^",
        "polars_naive": "v",
    }.get(approach, "s")


def _approach_linestyle(approach: str) -> str:
    # Non-mindoff baselines are dashed so they stay visible even when their values
    # coincide with a mindoff line (e.g. both flat at the same level).
    return "-" if _is_mindoff(approach) else "--"


def _is_mindoff(approach: str) -> bool:
    return approach.startswith("mindoff")


def _comparison_label(scenario: str) -> str:
    """Human "X vs Y vs django-mindoff" label from the scenario's line-up."""
    rivals = [
        APPROACH_LABELS[a]
        for a in SCENARIO_APPROACHES[scenario]
        if not _is_mindoff(a)
    ]
    return " vs ".join([*rivals, "django-mindoff"])


def _chart_label(scenario: str, approach: str) -> str:
    """Legend label, suffixed with validation posture where lines differ."""
    base = APPROACH_LABELS[approach]
    validation = APPROACH_VALIDATION.get((scenario, approach))
    return f"{base}  ·  {validation}" if validation else base


def _chart_notes(scenario: str) -> list[str]:
    """Bottom-of-chart notes: each "*" skip, then the per-operation caveat."""
    notes = [
        f"* {APPROACH_LABELS[approach]} not compared — {reason}"
        for (skip_scenario, approach), reason in SKIPPED_COMBOS.items()
        if skip_scenario == scenario
    ]
    caveat = SCENARIO_CAVEATS.get(scenario)
    if caveat:
        notes.append(f"Note: {caveat}")
    return notes


# ---------------------------------------------------------------------------
# Output housekeeping
# ---------------------------------------------------------------------------
def _stringify_paths(value):
    """Recursively convert ``Path`` values to ``str`` for JSON-serializable output."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _stringify_paths(item) for key, item in value.items()}
    return value


def _cleanup_transient_outputs() -> None:
    """Remove benchmark scaffolding so ``output/`` holds only the deliverables.

    Deliverables = ``catalog_benchmark_values.csv`` + the three operation charts.
    """
    import shutil

    for name in ("output_read", "bench_sources", "memory_probe"):
        with contextlib.suppress(OSError):
            shutil.rmtree(Path("output") / name, ignore_errors=True)
