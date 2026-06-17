"""Bulk UPDATE implementations â€” DRF vs django-mindoff.

pandas has no idiomatic bulk-update path so it is absent here; its memory-chart
slot for ``serializer_update`` falls back to DRF (marked N/A in the charts).

Both approaches update the *same set of mutable columns* (``DRF_UPDATE_FIELDS``)
by the *same delta* (price and stock each +1, ``updated_at`` refreshed). That
parity is what makes the timing comparison meaningful.

Validation posture â€” stated explicitly so the comparison is honest:
* ``drf_bulk_validated_update`` â€” full per-row serializer validation before the
  bulk write, matching the DRF create path.
* ``mindoff_update`` â€” full validation (``validation_level="full"``), matching
  ``mindoff_create_from_parquet``.
* ``mindoff_lazy_update`` â€” validation skipped to stay streaming, matching
  ``mindoff_lazy_create_from_parquet``.
"""

from __future__ import annotations

from django.utils import timezone
from django_mindoff import mo_crud_kit

from apps.catalog.models import ProductModel
from apps.catalog.serializers import ProductModelSerializer
from apps.catalog.components.compat import mindoff_update_kwargs
from apps.catalog.components.fixtures import product_update_frame


# Mutable columns Mindoff rewrites when it persists the full update frame.
# DRF mirrors the same column set so neither side writes more or less data.
DRF_UPDATE_FIELDS = ["sku", "name", "price", "stock", "category", "is_active", "updated_at"]


def drf_bulk_validated_update(products: list[ProductModel]) -> None:
    """DRF update, the fair mirror of ``mindoff_update``.

    Full serializer validation of every row, then a single ``bulk_update`` of the
    same columns Mindoff writes.
    """
    now = timezone.now()
    updated_products = []
    for product in products:
        serializer = ProductModelSerializer(
            product,
            data={
                "sku": product.sku,
                "name": product.name,
                "price": product.price + 1,
                "stock": product.stock + 1,
                "category": product.category,
                "is_active": product.is_active,
            },
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(product, field, value)
        product.updated_at = now
        updated_products.append(product)
    ProductModel.objects.bulk_update(
        updated_products,
        DRF_UPDATE_FIELDS,
        batch_size=1000,
    )


def mindoff_update(products: list[ProductModel], *, validation_level: str = "full") -> None:
    """django-mindoff eager update: full update frame upserted via ``mo_crud_kit``."""
    frame = product_update_frame(products)
    mo_crud_kit.update(
        {ProductModel: frame},
        is_partial=False,
        batch_size=1000,
        **mindoff_update_kwargs(validation_level, skip_db_fill=True),
    )


def mindoff_lazy_update(products: list[ProductModel]) -> None:
    """django-mindoff streaming update: upsert from a LazyFrame.

    Validation is skipped to keep the upsert streaming (the same trade-off as the
    lazy create path).
    """
    frame = product_update_frame(products).lazy()
    mo_crud_kit.update(
        {ProductModel: frame},
        is_partial=False,
        batch_size=1000,
        **mindoff_update_kwargs("none", skip_db_fill=True),
    )

