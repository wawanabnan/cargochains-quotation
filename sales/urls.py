from django.urls import path
from django.views.generic.base import RedirectView
from . import views   # ⬅️ penting, supaya bisa pakai views.quotation_pdf

app_name = "sales"

urlpatterns = [
    path('cargos/<int:pk>/', views.CargoDetailView.as_view(), name='cargo_detail'),
    path('cargos/<int:pk>/edit/', views.CargoUpdateView.as_view(), name='cargo_edit'),
    path("", RedirectView.as_view(pattern_name="sales:quotation_list", permanent=False), name="sales_index"),
    path("quotations/", views.QuotationListView.as_view(), name="quotation_list"),
    path("quotations/<int:pk>/", views.QuotationDetailView.as_view(), name="quotation_detail"),
    path("quotations/wizard/new/", views.quotation_wizard, name="quotation_wizard"),
    path("quotations/<int:pk>/pdf/", views.quotation_pdf, name="quotation_pdf"),  # ⬅️ endpoint PDF
]

