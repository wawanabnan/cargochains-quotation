from django.urls import path
from . import views
app_name = "sales"
urlpatterns = [
    path("quotations/", views.quotation_list, name="quotation_list"),
    path("quotations/wizard/v3/start/", views.quotation_wizard_v3_start, name="quotation_wizard_v3_start"),
    path("quotations/freight/new/", views.freight_wizard, name="freight_wizard"),
    path("charter/quotations/new/", views.charter_wizard, name="charter_wizard"),
    path("quotations/<int:pk>/", views.quotation_detail, name="quotation_detail"),
]
