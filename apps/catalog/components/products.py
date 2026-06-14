from __future__ import annotations

import time
import tracemalloc
import uuid
import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import polars as pl
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django_mindoff import mo_crud_kit

from apps.catalog.models import BenchmarkResultModel, ProductModel


@dataclass
class Measurement:
    approach: str
    scenario: str
    row_count: int
    time_ms: float
    memory_mb: float
    query_count: int

    def as_dict(self) -> dict:
        return {
            "approach": self.approach,
            "scenario": self.scenario,
            "row_count": self.row_count,
            "time_ms": round(self.time_ms, 2),
            "time_seconds": round(self.time_ms / 1000, 2),
            "memory_mb": round(self.memory_mb, 2),
            "query_count": self.query_count,
        }


DEFAULT_BENCHMARK_ROW_COUNT = 1000
MAX_BENCHMARK_ROW_COUNT = 20000


def validate_product_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
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


def product_frame(rows: list[dict]) -> pl.DataFrame:
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


def measure(approach: str, scenario: str, row_count: int, func) -> Measurement:
    tracemalloc.start()
    start = time.perf_counter()
    with CaptureQueriesContext(connection) as ctx:
        func()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    _ = current
    return Measurement(
        approach=approach,
        scenario=scenario,
        row_count=row_count,
        time_ms=(time.perf_counter() - start) * 1000,
        memory_mb=peak / (1024 * 1024),
        query_count=len(ctx.captured_queries),
    )


def standard_create(rows: list[dict]) -> None:
    for row in rows:
        ProductModel.objects.create(**row)


def standard_validated_create(rows: list[dict]) -> None:
    valid_rows, errors = validate_product_rows(rows)
    if errors:
        raise ValueError(errors)
    standard_create(valid_rows)


def standard_bulk_create(rows: list[dict]) -> None:
    ProductModel.objects.bulk_create(
        [ProductModel(**row) for row in rows],
        batch_size=1000,
    )


def mindoff_create(rows: list[dict]) -> None:
    mo_crud_kit.create(
        {ProductModel: product_frame(rows)},
        is_validate=True,
        is_partial=False,
    )


def import_products(rows: list[dict]) -> dict:
    valid_rows, errors = validate_product_rows(rows)
    metrics = []
    if valid_rows:
        probe = [
            dict(row, category=f"standard_probe_{row['category']}")
            for row in valid_rows
        ]
        metrics.append(
            measure(
                "django_row_loop",
                "import_products",
                len(probe),
                lambda: standard_create(probe),
            ).as_dict()
        )
        ProductModel.objects.filter(category__startswith="standard_probe_").delete()
        metrics.append(
            measure(
                "django_mindoff_polars",
                "import_products",
                len(valid_rows),
                lambda: mindoff_create(valid_rows),
            ).as_dict()
        )
        save_metrics(metrics)

    return {
        "total_rows": len(rows),
        "inserted_rows": len(valid_rows),
        "rejected_rows": len(errors),
        "errors": errors[:5],
        "metrics": metrics,
    }


def list_products_report() -> dict:
    frm, stats = mo_crud_kit.read(ProductModel.objects.all().values(), batch_size=500)
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


def run_product_benchmark(row_count: int = DEFAULT_BENCHMARK_ROW_COUNT) -> list[dict]:
    row_count = max(1, min(int(row_count), MAX_BENCHMARK_ROW_COUNT))
    run_id = uuid.uuid4().hex[:8]
    results = []

    ProductModel.objects.filter(sku__startswith=f"STD-CREATE-{run_id}").delete()
    ProductModel.objects.filter(sku__startswith=f"NATIVE-CREATE-{run_id}").delete()
    ProductModel.objects.filter(sku__startswith=f"MO-CREATE-{run_id}").delete()
    std_rows = deterministic_rows(row_count, f"STD-CREATE-{run_id}")
    native_rows = deterministic_rows(row_count, f"NATIVE-CREATE-{run_id}")
    mo_rows = deterministic_rows(row_count, f"MO-CREATE-{run_id}")
    results.append(
        measure(
            "django_row_loop",
            "validated_bulk_create",
            row_count,
            lambda: standard_validated_create(std_rows),
        ).as_dict()
    )
    results.append(
        measure(
            "django_native_bulk",
            "native_bulk_create",
            row_count,
            lambda: standard_bulk_create(native_rows),
        ).as_dict()
    )
    results.append(
        measure(
            "django_mindoff_polars",
            "validated_bulk_create",
            row_count,
            lambda: mindoff_create(mo_rows),
        ).as_dict()
    )

    def standard_pandas_read_conversion():
        qs = ProductModel.objects.filter(
            sku__startswith=f"STD-CREATE-{run_id}"
        ).values()
        return pd.DataFrame.from_records(qs)

    def mindoff_polars_read_conversion():
        qs = ProductModel.objects.filter(
            sku__startswith=f"MO-CREATE-{run_id}"
        ).values()
        return mo_crud_kit.read(qs, batch_size=500, is_lazy=True)

    results.append(
        measure(
            "standard_django_pandas",
            "read_conversion",
            row_count,
            standard_pandas_read_conversion,
        ).as_dict()
    )
    results.append(
        measure(
            "django_mindoff_polars",
            "read_conversion",
            row_count,
            mindoff_polars_read_conversion,
        ).as_dict()
    )

    std_products = list(
        ProductModel.objects.filter(sku__startswith=f"STD-CREATE-{run_id}")
    )
    native_products = list(
        ProductModel.objects.filter(sku__startswith=f"NATIVE-CREATE-{run_id}")
    )
    mo_products = list(ProductModel.objects.filter(sku__startswith=f"MO-CREATE-{run_id}"))
    for product in std_products:
        product.price += 1
        product.stock += 1
    for product in native_products:
        product.price += 1
        product.stock += 1

    def standard_validated_update():
        for product in std_products:
            valid_rows, errors = validate_product_rows(
                [
                    {
                        "sku": product.sku,
                        "name": product.name,
                        "price": product.price,
                        "stock": product.stock,
                        "category": product.category,
                        "is_active": product.is_active,
                    }
                ]
            )
            if errors or not valid_rows:
                raise ValueError(errors)
            product.save(update_fields=["price", "stock", "updated_at"])

    def standard_bulk_update():
        ProductModel.objects.bulk_update(
            native_products,
            ["price", "stock", "updated_at"],
            batch_size=1000,
        )

    results.append(
        measure(
            "django_row_loop",
            "validated_bulk_update",
            row_count,
            standard_validated_update,
        ).as_dict()
    )
    results.append(
        measure(
            "django_native_bulk",
            "native_bulk_update",
            row_count,
            standard_bulk_update,
        ).as_dict()
    )

    now = timezone.now()
    update_frame = pl.DataFrame(
        [
            {
                "id": str(product.id),
                "updated_at": now,
                "price": product.price + 1,
                "stock": product.stock + 1,
            }
            for product in mo_products
        ]
    )
    results.append(
        measure(
            "django_mindoff_polars",
            "validated_bulk_update",
            row_count,
            lambda: mo_crud_kit.update(
                {ProductModel: update_frame},
                is_validate=True,
                is_partial=False,
                batch_size=1000,
            ),
        ).as_dict()
    )

    save_metrics(results)
    return results


def save_metrics(metrics: list[dict]) -> None:
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


def latest_metrics(limit: int = 24) -> list[dict]:
    return [
        {
            "scenario": item.scenario,
            "approach": item.approach,
            "row_count": item.row_count,
            "time_ms": round(item.time_ms, 2),
            "time_seconds": round(item.time_ms / 1000, 2),
            "memory_mb": round(item.memory_mb, 2),
            "query_count": item.query_count,
        }
        for item in BenchmarkResultModel.objects.order_by("-created_at")[:limit]
    ]


def build_benchmark_csv() -> Path:
    metrics = list(reversed(latest_metrics()))
    if not metrics:
        metrics = run_product_benchmark(row_count=DEFAULT_BENCHMARK_ROW_COUNT)

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "catalog_benchmark_values.csv"
    fieldnames = [
        "scenario",
        "approach",
        "row_count",
        "time_ms",
        "time_seconds",
        "memory_mb",
        "query_count",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for metric in metrics:
            writer.writerow(
                {
                    "scenario": metric["scenario"],
                    "approach": metric["approach"],
                    "row_count": metric["row_count"],
                    "time_ms": f"{metric['time_ms']:.2f}",
                    "time_seconds": f"{metric['time_seconds']:.2f}",
                    "memory_mb": f"{metric['memory_mb']:.2f}",
                    "query_count": metric["query_count"],
                }
            )

    return out_path


def build_benchmark_chart() -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = list(reversed(latest_metrics()))
    if not metrics:
        metrics = run_product_benchmark(row_count=DEFAULT_BENCHMARK_ROW_COUNT)

    labels = [f"{m['scenario']}\n{m['approach']}" for m in metrics]
    time_values = [m["time_ms"] for m in metrics]
    memory_values = [m["memory_mb"] for m in metrics]
    query_values = [m["query_count"] for m in metrics]

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "catalog_benchmark.png"

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), constrained_layout=True)
    axes[0].bar(labels, time_values, color="#2563eb")
    axes[0].set_ylabel("Time ms")
    axes[1].bar(labels, memory_values, color="#059669")
    axes[1].set_ylabel("Memory MB")
    axes[2].bar(labels, query_values, color="#dc2626")
    axes[2].set_ylabel("Queries")
    for axis in axes:
        axis.tick_params(axis="x", labelrotation=45)
        axis.grid(axis="y", alpha=0.25)
    fig.suptitle("Django vs django-mindoff catalog benchmarks")
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    build_benchmark_csv()
    return out_path
