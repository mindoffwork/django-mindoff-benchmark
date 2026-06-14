import pytest
from django_mindoff import MindoffRouterTestCase



@pytest.mark.django_db
class TestGenerateInventoryReportRouter(MindoffRouterTestCase):
    """Tests for the Generate Inventory Report version router."""

    app_module = "apps.jobs.views"
    router_function_name = "generate_inventory_report_router"
