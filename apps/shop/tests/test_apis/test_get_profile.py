import pytest
from django_mindoff import MindoffTestCase


@pytest.mark.django_db(transaction=True)
class TestGetProfileV1APIView(MindoffTestCase):
    api_url_name = "shop__get_profile"

    def test_acceptance_api_success(self):
        response = self.mo_mock_call_api(
            self.api_url_name,
            url_kwargs={"version": 1},
        )

        self.mo_assert_api_response(api_url_name=self.api_url_name, response=response)
        assert response.data["message"]["code"] == "SUCCESS"
        assert response.data["data"]["email"] == "asha@example.com"
