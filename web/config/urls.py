
from django.urls import path
from django.views.generic import TemplateView

from .views import api_proxy


urlpatterns = [
    path(
        "",
        TemplateView.as_view(template_name="index.html"),
        name="inicio"
    ),

    path(
        "api/<path:endpoint>",
        api_proxy,
        name="api_proxy"
    ),
]
