from __future__ import annotations

from apps.catalog.components.products import list_products_report


def generate_inventory_report(report_name: str) -> dict:
    report = list_products_report()
    return {
        "report_name": report_name,
        "status": "completed",
        "summary": {
            "total_products": report["total_products"],
            "total_stock": report["total_stock"],
            "average_price": report["average_price"],
        },
    }
