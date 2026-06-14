import pytest
from django_mindoff import MindoffTestCase

from apps.jobs.apis.generate_inventory_report import GenerateInventoryReportV1APIView


@pytest.mark.django_db(transaction=True)
class TestGenerateInventoryReportV1APIView(MindoffTestCase):
    api_url_name = "jobs__generate_inventory_report"

    def test_queue_config_and_direct_test_response(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            payload={"report_name": "weekly_inventory_snapshot"},
            url_kwargs={"version": 1},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        assert GenerateInventoryReportV1APIView.process_mode == "queue"
        assert response.data["data"]["report_name"] == "weekly_inventory_snapshot"
