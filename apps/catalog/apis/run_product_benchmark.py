from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.catalog.components.products import (
    DEFAULT_BENCHMARK_ITERATIONS,
    DEFAULT_BENCHMARK_ROW_COUNT,
    run_product_benchmarks,
)


class RunProductBenchmarkV1APIView(MindoffAPIMixin):
    api_url_name: str = "catalog__run_product_benchmark"
    api_name: str = "Run Product Benchmark"
    api_description: str = "Run deterministic product create/read/update benchmarks."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "post"
    process_mode: Literal["direct", "queue"] = "direct"
    max_payload_size = 10
    max_payload_depth = 3
    payload_validation = "basic"
    payload_schema = {
        "row_count": [int],
        "iterations": int,
    }

    def run(self, request, *args, **kwargs):
        benchmark = run_product_benchmarks(
            row_count=request.data.get("row_count", DEFAULT_BENCHMARK_ROW_COUNT),
            iterations=request.data.get("iterations", DEFAULT_BENCHMARK_ITERATIONS),
        )
        return mo_response_kit.json_response(
            code="BENCHMARK_COMPLETED",
            category="success",
            data=benchmark,
        )
