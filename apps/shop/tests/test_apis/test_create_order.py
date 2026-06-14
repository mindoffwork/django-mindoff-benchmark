import pytest
from django_mindoff import MindoffTestCase


ORDER_PAYLOAD = {
    "customer_name": "Asha",
    "customer_email": "asha@example.com",
    "product_name": "Wireless Mouse",
    "quantity": 2,
}


@pytest.mark.django_db(transaction=True)
class TestCreateOrderAPIView(MindoffTestCase):
    api_url_name = "shop__create_order"

    def test_v1_success(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            payload=ORDER_PAYLOAD,
            url_kwargs={"version": 1},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        assert response.data["message"]["code"] == "ORDER_CREATED"
        assert "order_summary" not in response.data["data"]

    def test_v2_success_adds_richer_metadata(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            payload=ORDER_PAYLOAD,
            url_kwargs={"version": 2},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        assert response.data["message"]["code"] == "ORDER_CREATED"
        assert response.data["data"]["estimated_delivery_days"] == 3
        assert "order_summary" in response.data["data"]

    def test_validation_failure(self):
        payload = {**ORDER_PAYLOAD, "quantity": 0}
        response = self.mo_mock_call_api(
            self.api_url_name,
            payload=payload,
            url_kwargs={"version": 1},
        )

        assert response.status_code == 400
        assert response.data["message"]["code"] == "VALIDATION_ERR"
        assert "quantity" in response.data["data"]["errors"]
