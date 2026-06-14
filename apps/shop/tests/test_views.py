import pytest
from django_mindoff import MindoffRouterTestCase



@pytest.mark.django_db
class TestGetProfileRouter(MindoffRouterTestCase):
    """Tests for the Get Profile version router."""

    app_module = "apps.shop.views"
    router_function_name = "get_profile_router"



@pytest.mark.django_db
class TestCreateOrderRouter(MindoffRouterTestCase):
    """Tests for the Create Order version router."""

    app_module = "apps.shop.views"
    router_function_name = "create_order_router"
