from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.shop.components.orders import (
    create_order,
    serialize_order_v1,
    serialize_order_v2,
    validate_order_payload,
)


class CreateOrderV1APIView(MindoffAPIMixin):
    api_url_name: str = "shop__create_order"
    api_name: str = "Create Order"
    api_description: str = "Create a demo order and return a compact V1 response."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "post"
    payload_validation = "strict"
    payload_schema = {
        "customer_name": str,
        "customer_email": str,
        "product_name": str,
        "quantity": int,
    }

    def run(self, request, *args, **kwargs):
        validation = validate_order_payload(request.data)
        if not validation["ok"]:
            return mo_response_kit.json_response(
                code="VALIDATION_ERR",
                category="danger",
                data={"errors": validation["errors"]},
            )

        order = create_order(request.data)
        return mo_response_kit.json_response(
            code="ORDER_CREATED", category="success", data=serialize_order_v1(order)
        )


class CreateOrderV2APIView(CreateOrderV1APIView):
    api_name: str = "Create Order V2"
    api_description: str = "Create a demo order and return richer V2 metadata."

    def run(self, request, *args, **kwargs):
        validation = validate_order_payload(request.data)
        if not validation["ok"]:
            return mo_response_kit.json_response(
                code="VALIDATION_ERR",
                category="danger",
                data={"errors": validation["errors"]},
            )

        order = create_order(request.data)
        return mo_response_kit.json_response(
            code="ORDER_CREATED", category="success", data=serialize_order_v2(order)
        )
