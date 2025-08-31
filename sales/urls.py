from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    path("quotations/freight/<int:pk>/charges/", views.freight_manage_charges, name="freight_charges"),
    path('quotations/freight/new/', views.freight_create_wizard, name='freight_new'),
    # FREIGHT
    path("quotations/freight/", views.freight_list, name="freight_list"),
  #  path("quotations/freight/<int:pk>/edit/", views.freight_edit, name="freight_edit"),
    path("quotations/freight/<int:pk>/view/", views.freight_view, name="freight_view"),
    # AJAX
    path("quotations/freight/service-options/", views.freight_service_options, name="freight_service_options"),
    path("quotations/freight/actions/bulk/", views.freight_bulk_action, name="freight_bulk_action"),  # << NEW

   
]