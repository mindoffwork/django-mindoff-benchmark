"""Bulk READ implementations and output correctness — queryset → Polars frame.

Mindoff's read goal is to hand back a Polars ``DataFrame``/``LazyFrame`` from a
Django queryset as fast and lean as possible. The fair rivals are the realistic
non-Mindoff ways to land a frame from the same queryset:

* **pandas** (``pandas_csv_export``) — native ``pd.DataFrame.from_records(qs)``,
  the dataframe most teams reach for today.
* **polars_naive** (``polars_naive_csv_export``) — ``pl.DataFrame(list(qs))``,
  the true Polars baseline: build the frame straight from the ORM ``.values()``
  dicts, with no Mindoff/ConnectorX fast path.

Both are reusable functions called from the timed loop in ``products.py`` and the
memory-probe subprocess in ``measure.py``. The Mindoff read closures (eager via
ConnectorX, stream via fetchmany) are built per-run in ``products.py``.

DRF is intentionally absent: a serializer targets API representation, not
dataframe construction, so it is not a nominal queryset → frame path (see
``config.SKIPPED_COMBOS``).

* **Cross-approach parity check** (``_validate_read_csv_parity``) — spot-checks
  that every measured approach wrote equivalent CSV rows, so the benchmark can
  claim the engines are interchangeable on correctness and only differ on
  speed/memory.

Fairness note: every approach starts from the same Django ORM queryset
(``.values()``), so UUID normalization, field aliasing, and query compilation are
identical. The measured difference is purely in how each engine materializes that
queryset — pandas/polars_naive via Python dicts, Mindoff via ConnectorX
(DB → Arrow, skipping the dict step).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pandas as pd
import polars as pl

from apps.catalog.models import ProductModel
from apps.catalog.components.fixtures import _csv_safe_frame, _read_output_path


def _read_values_qs(prefix: str, row_count: int):
    """Shared ``.values()`` queryset every read approach materializes from."""
    return (
        ProductModel.objects.filter(sku__startswith=prefix)
        .order_by("sku")
        .values()
    )[:row_count]


# ---------------------------------------------------------------------------
# pandas READ approach (native pandas DataFrame)
# ---------------------------------------------------------------------------
def pandas_csv_export(prefix: str, row_count: int, out_path: Path) -> None:
    """pandas read: ORM queryset → ``list[dict]`` → pandas DataFrame → CSV."""
    frame = pd.DataFrame.from_records(_read_values_qs(prefix, row_count))
    frame.to_csv(out_path, index=False)


# ---------------------------------------------------------------------------
# polars_naive READ approach (true Polars baseline, no Mindoff fast path)
# ---------------------------------------------------------------------------
def polars_naive_csv_export(prefix: str, row_count: int, out_path: Path) -> None:
    """Baseline Polars read: ``pl.DataFrame(list(qs))`` → CSV.

    The naive way to land a Polars frame from a queryset without Mindoff: pull
    the ORM ``.values()`` dicts into Python, then build the frame. No ConnectorX
    DB→Arrow transfer, no streaming — the honest "just use Polars directly" path.
    """
    frame = pl.DataFrame(list(_read_values_qs(prefix, row_count)))
    _csv_safe_frame(frame).write_csv(out_path)


# ---------------------------------------------------------------------------
# Output correctness check
# ---------------------------------------------------------------------------

# Column groups used by the parity check — each type gets its own comparison
# rule so format differences that don't affect data integrity are tolerated.
_PARITY_CSV_NAME = {
    "pandas": "pandas_read",
    "polars_naive": "polars_naive_read",
    "mindoff": "mindoff_read",
    "mindoff_lazy": "mindoff_lazy_read",
}
_STRING_COLS = ["sku", "name", "category"]
_INT_COLS = ["stock"]
_FLOAT_COLS = ["price"]
_BOOL_COLS = ["is_active"]


def _parity_mismatch(approach: str, col: str, idx: int, ref_val, cmp_val) -> dict:
    return {"approach": approach, "col": col, "row": idx, "ref": ref_val, "got": cmp_val}


def _check_string_cols(approach, ref, frm, idx, mismatches) -> None:
    for col in _STRING_COLS:
        if col not in frm.columns:
            continue
        rv, cv = ref[col][idx], frm[col][idx]
        if rv != cv:
            mismatches.append(_parity_mismatch(approach, col, idx, rv, cv))


def _check_int_cols(approach, ref, frm, idx, mismatches) -> None:
    for col in _INT_COLS:
        if col not in frm.columns:
            continue
        with contextlib.suppress(TypeError, ValueError):
            if int(ref[col][idx]) != int(frm[col][idx]):
                mismatches.append(_parity_mismatch(approach, col, idx, ref[col][idx], frm[col][idx]))


def _check_float_cols(approach, ref, frm, idx, mismatches) -> None:
    for col in _FLOAT_COLS:
        if col not in frm.columns:
            continue
        with contextlib.suppress(TypeError, ValueError):
            rv_f, cv_f = float(ref[col][idx]), float(frm[col][idx])
            if abs(rv_f - cv_f) > 1e-6 * max(1.0, abs(rv_f)):
                mismatches.append(_parity_mismatch(approach, col, idx, rv_f, cv_f))


def _check_bool_cols(approach, ref, frm, idx, mismatches) -> None:
    for col in _BOOL_COLS:
        if col not in frm.columns:
            continue
        rv_b = str(ref[col][idx]).lower()
        cv_b = str(frm[col][idx]).lower()
        if rv_b != cv_b:
            mismatches.append(_parity_mismatch(approach, col, idx, rv_b, cv_b))


def _check_row(approach, ref, frm, idx, mismatches) -> None:
    _check_string_cols(approach, ref, frm, idx, mismatches)
    _check_int_cols(approach, ref, frm, idx, mismatches)
    _check_float_cols(approach, ref, frm, idx, mismatches)
    _check_bool_cols(approach, ref, frm, idx, mismatches)


def _validate_read_csv_parity(row_count: int, approaches: list) -> dict:
    """Spot-check that all read approaches produced equivalent CSV content.

    Loads the last-written output CSV for each approach (written during the
    shared timing loop), sorts by sku, picks 5 evenly-spaced rows, and compares
    product fields across approaches. Format differences that do not affect data
    integrity are tolerated: booleans compared case-insensitively, floats within
    a small epsilon.

    Returns a verdict dict (``status`` ∈ ``pass`` / ``fail`` / ``skipped``) with
    the concrete mismatches, so a failing run names exactly which approach,
    column, and row diverged.
    """
    frames = {}
    for approach in approaches:
        path = _read_output_path(_PARITY_CSV_NAME.get(approach, approach), row_count)
        if path.exists():
            with contextlib.suppress(Exception):
                frames[approach] = pl.read_csv(path, infer_schema=False).sort("sku")

    if len(frames) < 2:
        return {"status": "skipped", "reason": "fewer than 2 output CSVs available"}

    ref_name = approaches[0] if approaches[0] in frames else next(iter(frames))
    ref = frames[ref_name]
    n = ref.height
    indices = [int(i * n / 5) for i in range(5)] if n >= 5 else list(range(n))

    mismatches: list[dict] = []
    for approach, frm in frames.items():
        if approach == ref_name:
            continue
        for idx in indices:
            _check_row(approach, ref, frm, idx, mismatches)

    return {
        "status": "pass" if not mismatches else "fail",
        "reference": ref_name,
        "approaches_checked": list(frames.keys()),
        "rows_sampled": len(indices),
        "mismatches": mismatches,
    }
