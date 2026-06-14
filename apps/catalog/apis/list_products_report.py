from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.catalog.components.products import list_products_report


class ListProductsReportV1APIView(MindoffAPIMixin):
    api_url_name: str = "catalog__list_products_report"
    api_name: str = "List Products Report"
    api_description: str = "Read catalog data through Mindoff CRUD and return a category report."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "get"

    def run(self, request, *args, **kwargs):
        return mo_response_kit.json_response(
            code="SUCCESS", category="success", data=list_products_report()
        )
