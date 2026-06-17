import pytest

from apps.catalog.apis.import_products import ImportProductsV1APIView
from apps.catalog.apis.list_products_report import ListProductsReportV1APIView
from apps.catalog.apis.run_product_benchmark import RunProductBenchmarkV1APIView
from apps.jobs.apis.generate_inventory_report import GenerateInventoryReportV1APIView
from apps.shop.apis.create_order import CreateOrderV1APIView, CreateOrderV2APIView
from apps.shop.apis.get_profile import GetProfileV1APIView


@pytest.mark.django_db
@pytest.mark.parametrize(
    "api_cls",
    [
        ImportProductsV1APIView,
        ListProductsReportV1APIView,
        RunProductBenchmarkV1APIView,
        GetProfileV1APIView,
        CreateOrderV1APIView,
        CreateOrderV2APIView,
        GenerateInventoryReportV1APIView,
    ],
)
def test_api_classes_match_current_mindoff_contract(api_cls):
    api_cls().validate_api_configuration()
