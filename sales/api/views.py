from rest_framework import viewsets, status
from rest_framework.response import Response
from sales.models import Quotation, Cargo, CargoCharge
from .serializers import QuotationSerializer, CargoSerializer, CargoChargeSerializer

class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.all().order_by("-date", "-id")
    serializer_class = QuotationSerializer

class CargoViewSet(viewsets.ModelViewSet):
    queryset = Cargo.objects.select_related("quotation").all()
    serializer_class = CargoSerializer

class CargoChargeViewSet(viewsets.ModelViewSet):
    queryset = CargoCharge.objects.select_related("cargo", "cargo__quotation").all()
    serializer_class = CargoChargeSerializer
