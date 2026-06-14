import pytest
from django_mindoff import MindoffTestCase


@pytest.mark.django_db(transaction=True)
class TestBenchmarkChartV1APIView(MindoffTestCase):
    api_url_name = "catalog__benchmark_chart"

    def test_returns_png_file(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            url_kwargs={"version": 1},
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "image/png"
