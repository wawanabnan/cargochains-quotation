from django.urls import path
from django.views.generic.base import RedirectView
from . import views   # ⬅️ penting, supaya bisa pakai views.quotation_pdf

app_name = "sales"

urlpatterns = [
    path('quotations/wizard/v3/start/', views.quotation_wizard_v3_start, name='quotation_wizard_v3_start'),
    path('quotations/wizard/v3/', views.quotation_wizard_v3, name='quotation_wizard_v3'),
    path('quotations/wizard/start/', views.quotation_wizard_start, name='quotation_wizard_start'),
    path('cargos/<int:cargo_id>/charges/', views.cargo_charges_edit, name='cargo_charges_edit'),
    path('charges/<int:pk>/edit/', views.ChargeUpdateView.as_view(), name='charge_edit'),
    path('cargos/<int:pk>/', views.CargoDetailView.as_view(), name='cargo_detail'),
    path('cargos/<int:pk>/edit/', views.CargoUpdateView.as_view(), name='cargo_edit'),
    path("", RedirectView.as_view(pattern_name="sales:quotation_list", permanent=False), name="sales_index"),
    path("quotations/", views.QuotationListView.as_view(), name="quotation_list"),
    path("quotations/<int:pk>/", views.QuotationDetailView.as_view(), name="quotation_detail"),
    path("quotations/wizard/new/", views.quotation_wizard, name="quotation_wizard"),
    path("quotations/<int:pk>/pdf/", views.quotation_pdf, name="quotation_pdf"),  # ⬅️ endpoint PDF
]

