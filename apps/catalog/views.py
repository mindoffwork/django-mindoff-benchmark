from django.shortcuts import render

from .apis.import_products import ImportProductsV1APIView
from django_mindoff import mo_api_kit
from .apis.list_products_report import ListProductsReportV1APIView
from .apis.run_product_benchmark import RunProductBenchmarkV1APIView
from .apis.benchmark_chart import BenchmarkChartV1APIView
from .apis.benchmark_csv import BenchmarkCsvV1APIView
# Create your views here.



class ImportProductsRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: ImportProductsV1APIView,
    }


import_products_router = ImportProductsRouter()



class ListProductsReportRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: ListProductsReportV1APIView,
    }


list_products_report_router = ListProductsReportRouter()



class RunProductBenchmarkRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: RunProductBenchmarkV1APIView,
    }


run_product_benchmark_router = RunProductBenchmarkRouter()



class BenchmarkChartRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: BenchmarkChartV1APIView,
    }


benchmark_chart_router = BenchmarkChartRouter()



class BenchmarkCsvRouter(mo_api_kit.APIVersionRouter):
    VERSION_MAP = {
        1: BenchmarkCsvV1APIView,
    }


benchmark_csv_router = BenchmarkCsvRouter()
