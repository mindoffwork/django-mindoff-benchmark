from pathlib import Path

import pytest
from django_mindoff import MindoffTestCase


@pytest.mark.django_db(transaction=True)
class TestRunProductBenchmarkV1APIView(MindoffTestCase):
    api_url_name = "catalog__run_product_benchmark"

    def test_returns_metrics_and_export_artifacts_for_requested_counts(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            payload={"row_count": [250, 1000]},
            url_kwargs={"version": 1},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        data = response.data["data"]
        metrics = data["metrics"]
        assert data["row_counts"] == [250, 1000]
        assert data["max_row_count"] == 1000
        # Output is intentionally minimal: the values CSV + one chart file per
        # operation (each with a time + memory panel); no leftover scaffolding.
        assert set(data["exports"]) == {
            "csv",
            "create_chart",
            "read_chart",
            "update_chart",
        }
        assert Path(data["exports"]["csv"]).exists()
        assert Path(data["exports"]["create_chart"]).exists()
        assert Path(data["exports"]["read_chart"]).exists()
        assert Path(data["exports"]["update_chart"]).exists()

        max_metrics = [m for m in metrics if m["row_count"] == 1000]
        create_metrics = {
            m["approach"]: m
            for m in max_metrics
            if m["scenario"] == "serializer_create"
        }
        update_metrics = {
            m["approach"]: m
            for m in max_metrics
            if m["scenario"] == "serializer_update"
        }
        read_metrics = {
            m["approach"]: m for m in max_metrics if m["scenario"] == "serializer_read"
        }

        # Each operation is judged on both time and memory against the same
        # line-up. Create: DRF vs pandas vs mindoff (eager + stream). Read:
        # queryset → Polars frame, so pandas (native DataFrame) + polars_naive
        # (pl.DataFrame(list(qs)) baseline) vs mindoff; DRF is skipped (not a
        # dataframe path). Update: DRF vs mindoff; pandas has no bulk-update path.
        assert len(max_metrics) == 11
        assert set(create_metrics) == {
            "drf_serializer_many", "pandas", "mindoff", "mindoff_lazy"
        }
        assert set(read_metrics) == {
            "pandas", "polars_naive", "mindoff", "mindoff_lazy"
        }
        assert set(update_metrics) == {"drf_serializer_many", "mindoff", "mindoff_lazy"}
        assert all(m["iterations"] >= 5 for m in metrics)
        assert all(m["memory_metric"] == "peak_rss_delta_mb" for m in metrics)
        # The benchmark must not assume an outcome: both approaches now do
        # full validation + a single bulk write, so we only assert the
        # measurements are present and well-formed, not that one side wins.
        for scenario_metrics in (create_metrics, update_metrics, read_metrics):
            for metric in scenario_metrics.values():
                assert metric["time_ms"] >= 0
                assert metric["memory_mb"] >= 0

        # CSV parity: all read approaches must produce the same content for the
        # same rows.  One parity check per requested row_count.
        parity_checks = data["csv_parity_checks"]
        assert len(parity_checks) == 2  # one per row_count [250, 1000]
        for check in parity_checks:
            assert check["status"] in ("pass", "skipped"), (
                f"Read CSV parity FAILED for row_count={check.get('row_count')}: "
                f"{check.get('mismatches')}"
            )
