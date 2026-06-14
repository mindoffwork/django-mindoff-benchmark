from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.catalog.components.products import build_benchmark_chart


class BenchmarkChartV1APIView(MindoffAPIMixin):
    api_url_name: str = "catalog__benchmark_chart"
    api_name: str = "Benchmark Chart"
    api_description: str = "Return a Matplotlib PNG chart for recent benchmark results."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "get"

    def run(self, request, *args, **kwargs):
        chart_path = build_benchmark_chart()
        return mo_response_kit.file_response(
            str(chart_path), filename="catalog_benchmark.png", content_type="image/png"
        )
