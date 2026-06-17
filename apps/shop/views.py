from .apis.get_profile import GetProfileV1APIView
from django_mindoff import mo_api_kit
from .apis.create_order import CreateOrderV1APIView, CreateOrderV2APIView



class GetProfileRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: GetProfileV1APIView,
    }


get_profile_router = GetProfileRouter()



class CreateOrderRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: CreateOrderV1APIView,
        2: CreateOrderV2APIView,
    }


create_order_router = CreateOrderRouter()
