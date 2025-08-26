from django.urls import path
from . import views

app_name = "sales_api"
urlpatterns = [
    path("ping/", views.ping, name="ping"),
]
