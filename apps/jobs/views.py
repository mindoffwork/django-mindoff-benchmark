from django.shortcuts import render

from .apis.generate_inventory_report import GenerateInventoryReportV1APIView
from django_mindoff import mo_api_kit
# Create your views here.



class GenerateInventoryReportRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: GenerateInventoryReportV1APIView,
    }


generate_inventory_report_router = GenerateInventoryReportRouter()
