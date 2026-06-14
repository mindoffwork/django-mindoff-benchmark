from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.catalog.components.products import build_benchmark_csv


class BenchmarkCsvV1APIView(MindoffAPIMixin):
    api_url_name: str = "catalog__benchmark_csv"
    api_name: str = "Benchmark CSV"
    api_description: str = "Return latest benchmark values as a two-decimal CSV file."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "get"

    def run(self, request, *args, **kwargs):
        csv_path = build_benchmark_csv()
        return mo_response_kit.file_response(
            str(csv_path),
            filename="catalog_benchmark_values.csv",
            content_type="text/csv",
        )
