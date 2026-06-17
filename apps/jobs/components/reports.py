"""Inventory reporting for the ``jobs`` app.

A thin adapter over the catalog's product read path: it reuses
``list_products_report`` (the Mindoff-powered aggregate report) and reshapes it
into the headline summary a job run cares about. Kept deliberately small — the
heavy lifting lives in the catalog component it delegates to.
"""

from __future__ import annotations

from apps.catalog.components.products import list_products_report


def generate_inventory_report(report_name: str) -> dict:
    """Produce a named inventory report from the current product catalog.

    Returns a completed-status envelope with the totals (product count, stock,
    average price) pulled from the shared ``list_products_report`` aggregate.
    """
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
