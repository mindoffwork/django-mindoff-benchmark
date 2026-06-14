import pytest
from django_mindoff import MindoffRouterTestCase



@pytest.mark.django_db
class TestImportProductsRouter(MindoffRouterTestCase):
    """Tests for the Import Products version router."""

    app_module = "apps.catalog.views"
    router_function_name = "import_products_router"



@pytest.mark.django_db
class TestListProductsReportRouter(MindoffRouterTestCase):
    """Tests for the List Products Report version router."""

    app_module = "apps.catalog.views"
    router_function_name = "list_products_report_router"



@pytest.mark.django_db
class TestRunProductBenchmarkRouter(MindoffRouterTestCase):
    """Tests for the Run Product Benchmark version router."""

    app_module = "apps.catalog.views"
    router_function_name = "run_product_benchmark_router"



@pytest.mark.django_db
class TestBenchmarkChartRouter(MindoffRouterTestCase):
    """Tests for the Benchmark Chart version router."""

    app_module = "apps.catalog.views"
    router_function_name = "benchmark_chart_router"



@pytest.mark.django_db
class TestBenchmarkCsvRouter(MindoffRouterTestCase):
    """Tests for the Benchmark Csv version router."""

    app_module = "apps.catalog.views"
    router_function_name = "benchmark_csv_router"
