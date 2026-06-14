import csv

import pytest
from django_mindoff import MindoffTestCase


@pytest.mark.django_db(transaction=True)
class TestBenchmarkCsvV1APIView(MindoffTestCase):
    api_url_name = "catalog__benchmark_csv"

    def test_returns_csv_file_with_two_decimal_values(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            url_kwargs={"version": 1},
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        content = b"".join(response.streaming_content).decode("utf-8")
        rows = list(csv.DictReader(content.splitlines()))
        assert rows
        assert set(rows[0]) == {
            "scenario",
            "approach",
            "row_count",
            "time_ms",
            "time_seconds",
            "memory_mb",
            "query_count",
        }
        assert len(rows[0]["time_seconds"].split(".")[-1]) == 2
        assert len(rows[0]["memory_mb"].split(".")[-1]) == 2
