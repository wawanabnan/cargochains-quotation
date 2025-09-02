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
    path("quotations/freight/actions/bulk/", views.freight_bulk_action, name="freight_bulk_action") ,
    path("quotations/freight/<int:pk>/pdf/", views.freight_pdf, name="freight_pdf"),
    path("quotations/freight/<int:pk>/email/", views.freight_send_email, name="freight_email"),
    path("sales/orders/freight/<int:pk>/generate/", views.freight_generate_order, name="freight_generate_order"),
    
   # --- Freight Order  ---
    path("orders/freight/", views.freight_order_list, name="freight_order_list"),
    path("orders/freight/<int:pk>/", views.freight_order_view, name="freight_order_view"),
    path("orders/freight/<int:pk>/generate/", views.freight_generate_order, name="freight_generate_order"),


]