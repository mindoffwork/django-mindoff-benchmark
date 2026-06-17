"""Test data, frames, and on-disk scaffolding shared by every approach.

Everything here is deliberately *deterministic*: the same row count always
produces the same rows, the same SKUs, the same Parquet bytes. That is what
makes the benchmark reproducible and the cross-approach parity check meaningful
â€” each engine is handed identical input and asked to produce identical output.

Three kinds of helper live here:

* **Row generation / validation** â€” ``deterministic_rows`` and
  ``validate_product_rows`` build and sanity-check the plain ``list[dict]``
  payloads.
* **Frames** â€” ``product_frame`` / ``product_update_frame`` /
  ``_product_source_frame`` turn rows into Polars frames in the column shape the
  ``ProductModel`` table expects.
* **Output paths & CSV sanitizing** â€” the small helpers that decide *where*
  benchmark artifacts are written and make Polars frames safe to serialize.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import polars as pl
from django.utils import timezone

from apps.catalog.models import ProductModel


# ---------------------------------------------------------------------------
# Row generation & validation
# ---------------------------------------------------------------------------
def validate_product_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate an inbound import payload without touching the database.

    Returns ``(valid_rows, errors)``. Each entry in ``errors`` is
    ``{"row_index": int, "fields": {field: message}}`` so callers can report
    precisely which row and field failed. Duplicate SKUs within a single payload
    are rejected too â€” the import is meant to be idempotent per SKU.
    """
    valid_rows = []
    errors = []
    seen_skus = set()
    for index, row in enumerate(rows):
        row_errors = {}
        sku = str(row.get("sku") or "").strip()
        if not sku:
            row_errors["sku"] = "This field is required."
        elif sku in seen_skus:
            row_errors["sku"] = "Duplicate SKU in payload."
        seen_skus.add(sku)

        try:
            price = float(row.get("price"))
            if price <= 0:
                row_errors["price"] = "Must be greater than 0."
        except (TypeError, ValueError):
            row_errors["price"] = "Must be a number."

        try:
            stock = int(row.get("stock"))
            if stock < 0:
                row_errors["stock"] = "Must be 0 or greater."
        except (TypeError, ValueError):
            row_errors["stock"] = "Must be a whole number."

        if not row.get("name"):
            row_errors["name"] = "This field is required."
        if not row.get("category"):
            row_errors["category"] = "This field is required."

        if row_errors:
            errors.append({"row_index": index, "fields": row_errors})
            continue

        valid_rows.append(
            {
                "sku": sku,
                "name": str(row["name"]),
                "price": price,
                "stock": stock,
                "category": str(row["category"]),
                "is_active": bool(row.get("is_active", True)),
            }
        )
    return valid_rows, errors


def deterministic_rows(row_count: int, prefix: str) -> list[dict]:
    """Build ``row_count`` reproducible product rows under a unique ``prefix``.

    The prefix keeps each run's rows isolated (so prefix-scoped cleanup is safe)
    and guarantees SKU uniqueness across concurrent approaches.
    """
    categories = ["accessories", "keyboards", "mice", "cables"]
    return [
        {
            "sku": f"{prefix}-{i:05d}",
            "name": f"Demo Product {i}",
            "price": float(10 + (i % 90)),
            "stock": int(5 + (i % 50)),
            "category": categories[i % len(categories)],
            "is_active": i % 7 != 0,
        }
        for i in range(row_count)
    ]


# ---------------------------------------------------------------------------
# Frames (Polars views over the rows, in ProductModel column shape)
# ---------------------------------------------------------------------------
def product_frame(rows: list[dict]) -> pl.DataFrame:
    """Wrap create rows in a Polars frame with generated id/timestamps."""
    now = timezone.now()
    return pl.DataFrame(
        [
            {
                "id": str(uuid.uuid4()),
                "created_at": now,
                "updated_at": now,
                **row,
            }
            for row in rows
        ]
    )


def product_update_frame(products: list[ProductModel]) -> pl.DataFrame:
    """Build the full update frame for a set of existing products.

    Every mutable column is bumped (``price``/``stock`` +1, ``updated_at`` now)
    so both the Mindoff and DRF update paths write an identical, non-trivial
    change set.
    """
    now = timezone.now()
    return pl.DataFrame(
        [
            {
                "id": str(product.id),
                "created_at": product.created_at,
                "updated_at": now,
                "sku": product.sku,
                "name": product.name,
                "price": product.price + 1,
                "stock": product.stock + 1,
                "category": product.category,
                "is_active": product.is_active,
            }
            for product in products
        ]
    )


def _product_source_frame(prefix: str, row_count: int) -> pl.DataFrame:
    """Column-oriented source frame used to materialize the Parquet create source.

    Built columnarly (one list per column) because that is Polars' native, fast
    construction path â€” the opposite of the row-of-dicts path that would unfairly
    tax it during setup.
    """
    now = timezone.now()
    categories = ["accessories", "keyboards", "mice", "cables"]
    return pl.DataFrame(
        {
            "id": [uuid.uuid4().hex for _ in range(row_count)],
            "created_at": [now] * row_count,
            "updated_at": [now] * row_count,
            "sku": [f"{prefix}-{i:05d}" for i in range(row_count)],
            "name": [f"Demo Product {i}" for i in range(row_count)],
            "price": [float(10 + (i % 90)) for i in range(row_count)],
            "stock": [int(5 + (i % 50)) for i in range(row_count)],
            "category": [categories[i % len(categories)] for i in range(row_count)],
            "is_active": [i % 7 != 0 for i in range(row_count)],
        }
    )


# ---------------------------------------------------------------------------
# On-disk Parquet source for the CREATE benchmark
#
# Bulk data realistically arrives as a columnar file, so the create benchmark
# reads a Parquet source instead of hand-building Python dicts inside the timed
# region. Each approach gets its own prefix-scoped source so prefix cleanup and
# PK uniqueness hold across iterations.
# ---------------------------------------------------------------------------
def _source_parquet_path(prefix: str, row_count: int) -> Path:
    out_dir = Path("output") / "bench_sources"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"src_{prefix}_{row_count}.parquet"


def ensure_source_parquet(prefix: str, row_count: int) -> Path:
    """Write (once) and return the Parquet source for an approach's create run.

    Built during benchmark setup, never inside the measured region, so the
    measured operation is purely *ingest file + persist* â€” the realistic bulk
    create â€” for every approach.
    """
    path = _source_parquet_path(prefix, row_count)
    if not path.exists():
        _product_source_frame(prefix, row_count).write_parquet(path)
    return path


# ---------------------------------------------------------------------------
# Read-output paths & CSV sanitizing
# ---------------------------------------------------------------------------
def _read_output_path(name: str, row_count: int) -> Path:
    """Path for a read benchmark's transient CSV output (under ``output/output_read``)."""
    out_dir = Path("output") / "output_read"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"catalog_{name}_{row_count}.csv"


def _csv_safe_frame(frm: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame | pl.LazyFrame:
    """Coerce any Polars ``Object`` columns to strings so CSV writing can't fail.

    A no-op when there are no object columns, so the common path stays cheap and
    the streaming (lazy) frame is left untouched unless it genuinely needs it.
    """
    schema = frm.collect_schema() if isinstance(frm, pl.LazyFrame) else frm.schema
    object_columns = [name for name, dtype in schema.items() if dtype == pl.Object]
    if not object_columns:
        return frm
    return frm.with_columns(
        [
            pl.col(name)
            .map_elements(
                lambda value: "" if value is None else str(value),
                return_dtype=pl.Utf8,
            )
            .alias(name)
            for name in object_columns
        ]
    )


def _write_records_csv(records, out_path: Path) -> None:
    """Serialize an iterable of record dicts to CSV via the shared Polars writer.

    Both the DRF and Mindoff read paths funnel through this one writer so the
    measured difference is the read/serialize step, not the CSV engine.
    """
    frame = pl.DataFrame([dict(record) for record in records])
    _csv_safe_frame(frame).write_csv(out_path)

