from django.views.generic.base import TemplateView
from django_mindoff import urls as mindoff_urls
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html')),
    path('mindoff/', include(mindoff_urls)),
    path('admin/', admin.site.urls),
]
