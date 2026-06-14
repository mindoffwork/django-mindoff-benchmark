from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
# Add Url Patterns here
    path('import_products/', csrf_exempt(views.import_products_router), name='catalog__import_products'),
    path('list_products_report/', csrf_exempt(views.list_products_report_router), name='catalog__list_products_report'),
    path('run_product_benchmark/', csrf_exempt(views.run_product_benchmark_router), name='catalog__run_product_benchmark'),
    path('benchmark_chart/', csrf_exempt(views.benchmark_chart_router), name='catalog__benchmark_chart'),
    path('benchmark_csv/', csrf_exempt(views.benchmark_csv_router), name='catalog__benchmark_csv'),
]
