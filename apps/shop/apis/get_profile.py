from typing import Literal

from django_mindoff import MindoffAPIMixin, mo_response_kit
from rest_framework.permissions import AllowAny

from apps.shop.components.orders import demo_profile


class GetProfileV1APIView(MindoffAPIMixin):
    api_url_name: str = "shop__get_profile"
    api_name: str = "Get Profile"
    api_description: str = "Return a tiny profile payload to demonstrate response envelopes."
    authentication_classes = []
    permission_classes = [AllowAny]
    method: Literal["get", "post", "put", "delete"] = "get"
    process_mode: Literal["direct", "queue"] = "direct"

    def run(self, request, *args, **kwargs):
        return mo_response_kit.json_response(
            code="SUCCESS", category="success", data=demo_profile()
        )
