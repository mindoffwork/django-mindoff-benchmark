from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [
# Add Url Patterns here
    path('get_profile/', csrf_exempt(views.get_profile_router), name='shop__get_profile'),
    path('create_order/', csrf_exempt(views.create_order_router), name='shop__create_order'),
]
