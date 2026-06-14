from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
# Add Url Patterns here
    path('generate_inventory_report/', csrf_exempt(views.generate_inventory_report_router), name='jobs__generate_inventory_report'),
]
