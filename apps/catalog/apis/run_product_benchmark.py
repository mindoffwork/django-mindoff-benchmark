from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.catalog.components.products import DEFAULT_BENCHMARK_ROW_COUNT, run_product_benchmark


class RunProductBenchmarkV1APIView(MindoffAPIMixin):
    api_url_name: str = "catalog__run_product_benchmark"
    api_name: str = "Run Product Benchmark"
    api_description: str = "Run deterministic product create/read/update benchmarks."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "post"
    payload_validation = "basic"
    payload_schema = {"row_count": int}

    def run(self, request, *args, **kwargs):
        return mo_response_kit.json_response(
            code="BENCHMARK_COMPLETED",
            category="success",
            data={
                "metrics": run_product_benchmark(
                    request.data.get("row_count", DEFAULT_BENCHMARK_ROW_COUNT)
                )
            },
        )
