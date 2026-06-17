"""Order domain logic for the ``shop`` app.

The reusable logic behind the shop's API views, kept thin per AGENTS.md S5
(handlers stay slim; business logic lives in components). Reading order mirrors
an order's lifecycle: validate the payload, create the order, then serialize it
for a response (v1 = core fields, v2 = v1 plus delivery extras). ``demo_profile``
is standalone sample data for the profile endpoint.
"""

from __future__ import annotations

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.shop.models import CustomerModel, OrderModel


def demo_profile() -> dict:
    """Static sample customer profile served by the profile endpoint."""
    return {
        "name": "Asha",
        "email": "asha@example.com",
        "membership": "gold",
    }


def validate_order_payload(payload: dict) -> dict:
    """Validate an inbound order payload without touching the database.

    Checks required fields, a positive integer quantity, and a well-formed
    email. Returns ``{"ok": bool, "errors": {field: message}}`` so the caller can
    report every problem at once rather than failing on the first.
    """
    errors = {}
    for field in ["customer_name", "customer_email", "product_name", "quantity"]:
        if payload.get(field) in [None, ""]:
            errors[field] = "This field is required."

    try:
        quantity = int(payload.get("quantity", 0))
        if quantity <= 0:
            errors["quantity"] = "Must be greater than 0."
    except (TypeError, ValueError):
        errors["quantity"] = "Must be a whole number."

    try:
        validate_email(payload.get("customer_email", ""))
    except DjangoValidationError:
        errors["customer_email"] = "Enter a valid email address."

    if errors:
        return {"ok": False, "errors": errors}
    return {"ok": True, "errors": {}}


def create_order(payload: dict) -> OrderModel:
    """Persist a new order, reusing (or creating) the customer by email.

    Assumes the payload has already passed ``validate_order_payload``.
    """
    customer, _ = CustomerModel.objects.get_or_create(
        email=payload["customer_email"],
        defaults={"name": payload["customer_name"]},
    )
    return OrderModel.objects.create(
        customer_ref=customer,
        product_name=payload["product_name"],
        quantity=int(payload["quantity"]),
        status="created",
    )


def serialize_order_v1(order: OrderModel) -> dict:
    """Serialize an order to the v1 response shape (core fields only)."""
    return {
        "order_id": str(order.id),
        "customer_name": order.customer_ref.name,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "status": order.status,
    }


def serialize_order_v2(order: OrderModel) -> dict:
    """Serialize an order to the v2 shape: v1 fields plus delivery extras."""
    return {
        **serialize_order_v1(order),
        "estimated_delivery_days": 3,
        "order_summary": f"{order.quantity} x {order.product_name} for {order.customer_ref.name}",
    }
