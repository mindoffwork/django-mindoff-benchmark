import pytest
from django_mindoff import MindoffTestCase


@pytest.mark.django_db(transaction=True)
class TestRunProductBenchmarkV1APIView(MindoffTestCase):
    api_url_name = "catalog__run_product_benchmark"

    def test_returns_standard_and_mindoff_metrics(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            payload={"row_count": 1000},
            url_kwargs={"version": 1},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        metrics = response.data["data"]["metrics"]
        create_metrics = {
            m["approach"]: m
            for m in metrics
            if m["scenario"] == "validated_bulk_create"
        }
        update_metrics = {
            m["approach"]: m
            for m in metrics
            if m["scenario"] == "validated_bulk_update"
        }
        native_create_metrics = {
            m["approach"]: m for m in metrics if m["scenario"] == "native_bulk_create"
        }
        native_update_metrics = {
            m["approach"]: m for m in metrics if m["scenario"] == "native_bulk_update"
        }
        read_metrics = {
            m["approach"]: m for m in metrics if m["scenario"] == "read_conversion"
        }

        assert set(create_metrics) == {"django_row_loop", "django_mindoff_polars"}
        assert set(update_metrics) == {"django_row_loop", "django_mindoff_polars"}
        assert set(native_create_metrics) == {"django_native_bulk"}
        assert set(native_update_metrics) == {"django_native_bulk"}
        assert set(read_metrics) == {
            "standard_django_pandas",
            "django_mindoff_polars",
        }
        assert (
            create_metrics["django_mindoff_polars"]["time_ms"]
            <= create_metrics["django_row_loop"]["time_ms"]
        )
        assert (
            create_metrics["django_mindoff_polars"]["query_count"]
            <= create_metrics["django_row_loop"]["query_count"]
        )
        assert (
            update_metrics["django_mindoff_polars"]["time_ms"]
            <= update_metrics["django_row_loop"]["time_ms"]
        )
        assert (
            update_metrics["django_mindoff_polars"]["query_count"]
            <= update_metrics["django_row_loop"]["query_count"]
        )
