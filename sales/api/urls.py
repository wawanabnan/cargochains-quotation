from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuotationViewSet, CargoViewSet, CargoChargeViewSet

router = DefaultRouter()
router.register(r"quotations", QuotationViewSet, basename="api-quotation")
router.register(r"cargos", CargoViewSet, basename="api-cargo")
router.register(r"charges", CargoChargeViewSet, basename="api-charge")

urlpatterns = [
    path("", include(router.urls)),
]
