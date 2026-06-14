import pytest
from django_mindoff import MindoffTestCase

from apps.catalog.models import ProductModel


@pytest.mark.django_db(transaction=True)
class TestListProductsReportV1APIView(MindoffTestCase):
    api_url_name = "catalog__list_products_report"

    def test_summary_shape(self):
        ProductModel.objects.create(
            sku="REPORT-001",
            name="Keyboard",
            price=50,
            stock=10,
            category="accessories",
            is_active=True,
        )

        response = self.mo_mock_call_api(
            self.api_url_name,
            url_kwargs={"version": 1},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        data = response.data["data"]
        assert data["total_products"] >= 1
        assert "by_category" in data
        assert "read_stats" in data
