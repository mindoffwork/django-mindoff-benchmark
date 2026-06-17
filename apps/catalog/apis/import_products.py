from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.catalog.components.products import import_products


class ImportProductsV1APIView(MindoffAPIMixin):
    api_url_name: str = "catalog__import_products"
    api_name: str = "Import Products"
    api_description: str = "Validate and import product rows while returning benchmark metrics."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "post"
    process_mode: Literal["direct", "queue"] = "direct"
    max_payload_size = 10
    max_payload_depth = 4
    payload_validation = "basic"
    payload_schema = {"rows": [dict]}

    def run(self, request, *args, **kwargs):
        return mo_response_kit.json_response(
            code="PRODUCT_IMPORT_COMPLETED",
            category="success",
            data=import_products(request.data.get("rows", [])),
        )
