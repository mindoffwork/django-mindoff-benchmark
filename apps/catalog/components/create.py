"""Bulk CREATE implementations â€” DRF vs pandas vs django-mindoff.

Each rival sits next to the others so an auditor can confirm the compared work
is genuinely equivalent: same columns written, same Parquet source ingested,
validation level stated explicitly.

Two shapes of create are benchmarked:

* **From rows** (``drf_bulk_validated_create``, ``pandas_bulk_create``,
  ``mindoff_create``) â€” used by the ``import_products`` flow, where the payload
  has already been deserialized to ``list[dict]``.
* **From Parquet** (``*_create_from_parquet``) â€” the realistic bulk-ingest shape
  used by the timed benchmark. The Parquet source is built once in setup (never
  timed) so the measured operation is purely *file â†’ DB*.

``standard_bulk_create`` is not a benchmark approach; it is a fast, validation-
free fixture helper used to seed rows for read/update benchmark passes.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import polars as pl
from django.db import connection, transaction
from django.utils import timezone
from django_mindoff import mo_crud_kit
from sqlalchemy import create_engine, event

from apps.catalog.models import ProductModel
from apps.catalog.serializers import ProductModelSerializer
from apps.catalog.components.compat import mindoff_create_kwargs
from apps.catalog.components.fixtures import product_frame


# ---------------------------------------------------------------------------
# Shared: a correctly-configured pandas SQLite engine
# ---------------------------------------------------------------------------
def _pandas_sqlite_engine():
    """Bind a SQLAlchemy engine to Django's live connection for pandas ``to_sql``.

    A pandas user reaches the DB through a SQLAlchemy engine. We bind it to
    Django's live connection (same DB as every other approach, and the only way
    to see an in-memory test DB) and emit an explicit ``BEGIN`` on transaction
    start. Django opens SQLite in autocommit mode, so without this each batch
    would auto-commit per statement â€” a fair pandas baseline gets a correctly
    configured engine, not a crippled one.
    """
    engine = create_engine("sqlite://", creator=lambda: connection.connection)
    event.listen(engine, "begin", lambda conn: conn.exec_driver_sql("BEGIN"))
    return engine


# ---------------------------------------------------------------------------
# From rows
# ---------------------------------------------------------------------------
def drf_bulk_validated_create(rows: list[dict]) -> None:
    """DRF: validate every row with the serializer, then a single ``bulk_create``."""
    serializer = ProductModelSerializer(data=rows, many=True)
    serializer.is_valid(raise_exception=True)
    ProductModel.objects.bulk_create(
        [ProductModel(**row) for row in serializer.validated_data],
        batch_size=1000,
    )


def standard_bulk_create(rows: list[dict]) -> None:
    """Plain Django ``bulk_create`` with no validation â€” used to seed fixtures fast."""
    ProductModel.objects.bulk_create(
        [ProductModel(**row) for row in rows],
        batch_size=1000,
    )


def pandas_bulk_create(rows: list[dict]) -> None:
    """pandas: build a DataFrame, then ``to_sql`` in batched multi-row inserts.

    Mirrors the same columns Mindoff writes so the two dataframe engines move
    identical data.
    """
    now = timezone.now()
    frame = pd.DataFrame(
        [{"id": uuid.uuid4().hex, "created_at": now, "updated_at": now, **row} for row in rows]
    )
    engine = _pandas_sqlite_engine()
    with transaction.atomic():
        frame.to_sql(
            ProductModel._meta.db_table,
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )


def mindoff_create(rows: list[dict], *, validation_level: str = "full") -> None:
    """django-mindoff eager create: build a frame and hand it to ``mo_crud_kit``."""
    frame = product_frame(rows)
    mo_crud_kit.create(
        {ProductModel: frame},
        is_partial=False,
        **mindoff_create_kwargs(validation_level),
    )


# ---------------------------------------------------------------------------
# From Parquet (the timed benchmark operation)
# ---------------------------------------------------------------------------
def drf_create_from_parquet(path: Path) -> None:
    """DRF needs Python dicts, so reading the file to records is its native ingest.

    Read-only ``id``/timestamp columns are simply ignored by the serializer.
    """
    drf_bulk_validated_create(pl.read_parquet(path).to_dicts())


def pandas_create_from_parquet(path: Path) -> None:
    """pandas: ``read_parquet`` then ``to_sql`` â€” its native file-to-DB path."""
    frame = pd.read_parquet(path)
    engine = _pandas_sqlite_engine()
    with transaction.atomic():
        frame.to_sql(
            ProductModel._meta.db_table,
            engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )


def mindoff_create_from_parquet(path: Path) -> None:
    """django-mindoff eager: read the Parquet and bulk write with FULL validation."""
    mo_crud_kit.create(
        {ProductModel: pl.read_parquet(path)},
        is_partial=False,
        **mindoff_create_kwargs("full"),
    )


def mindoff_lazy_create_from_parquet(path: Path) -> None:
    """django-mindoff streaming: ``scan_parquet`` lazily and stream to the DB.

    Full validation would collect the LazyFrame (defeating streaming), so the
    lazy path skips validation â€” like pandas, which also does none.
    """
    mo_crud_kit.create(
        {ProductModel: pl.scan_parquet(path)},
        is_partial=False,
        **mindoff_create_kwargs("none"),
    )

