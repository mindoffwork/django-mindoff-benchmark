from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.jobs.components.reports import generate_inventory_report


class GenerateInventoryReportV1APIView(MindoffAPIMixin):
    api_url_name: str = "jobs__generate_inventory_report"
    api_name: str = "Generate Inventory Report"
    api_description: str = "Optional queue-mode report generation demo."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "post"
    process_mode: Literal["direct", "queue"] = "queue"
    allow_duplicate_queue = True
    max_payload_size = 2
    max_payload_depth = 2
    payload_validation = "basic"
    payload_schema = {"report_name": str}
    progress_steps = {
        "collect": {"label": "Collect catalog rows", "percent": 20},
        "summarize": {"label": "Summarize inventory", "percent": 70},
        "finish": {"label": "Finalize report", "percent": 90},
    }

    def run(self, request, *args, **kwargs):
        return mo_response_kit.json_response(
            code="SUCCESS",
            category="success",
            data=generate_inventory_report(
                request.data.get("report_name", "inventory_snapshot")
            ),
        )
