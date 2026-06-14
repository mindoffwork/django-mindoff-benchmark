import pytest
from django_mindoff import MindoffTestCase


@pytest.mark.django_db(transaction=True)
class TestImportProductsV1APIView(MindoffTestCase):
    api_url_name = "catalog__import_products"

    def test_mixed_valid_invalid_rows(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            payload={
                "rows": [
                    {
                        "sku": "SKU-001",
                        "name": "Keyboard",
                        "price": 49.99,
                        "stock": 20,
                        "category": "accessories",
                    },
                    {
                        "sku": "",
                        "name": "Bad Product",
                        "price": -10,
                        "stock": 5,
                        "category": "misc",
                    },
                ]
            },
            url_kwargs={"version": 1},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        data = response.data["data"]
        assert data["total_rows"] == 2
        assert data["inserted_rows"] == 1
        assert data["rejected_rows"] == 1
        assert {m["approach"] for m in data["metrics"]} == {
            "django_row_loop",
            "django_mindoff_polars",
        }
