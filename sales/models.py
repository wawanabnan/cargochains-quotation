from django.db import models
from django.db.models import Sum
from django.urls import reverse
from .utils import next_quotation_number

class Quotation(models.Model):
    number = models.CharField(max_length=30, unique=True, blank=True)
    date = models.DateField()
    customer = models.ForeignKey("partners.Customer", on_delete=models.PROTECT)
    validity_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    notes = models.TextualField if hasattr(models, "TextualField") else models.TextField  # guard untuk IDE
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.number or str(self.number).strip() == "":
            self.number = next_quotation_number(Quotation)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number or f"Quotation {self.pk}"

    def get_absolute_url(self):
        return reverse("sales:quotation_detail", args=[self.pk])

    @property
    def totals_by_currency(self):
        return (CargoCharge.objects
                .filter(cargo__quotation=self)
                .values("currency")
                .annotate(total=Sum("amount"))
                .order_by("currency"))

class Cargo(models.Model):
    quotation = models.ForeignKey(Quotation, related_name="cargos", on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    package_type = models.CharField(max_length=50, blank=True)   # CTN/PLT/BAG/LOOSE
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    extra_notes = models.TextField(blank=True)

    # Parties
    shipper = models.CharField(max_length=200, blank=True)
    consignee = models.CharField(max_length=200, blank=True)
    notify_party = models.CharField(max_length=200, blank=True)
    def __str__(self):
        return f"{self.description} ({self.origin} → {self.destination})"

    def totals_by_currency(self):
        return (self.charges.values("currency")
                .annotate(total=Sum("amount"))
                .order_by("currency"))

class CargoCharge(models.Model):
    CHARGE_CHOICES = [
        ("FREIGHT","FREIGHT"),
        ("ORIGIN","ORIGIN"),
        ("DEST","DEST"),
        ("DOC","DOC"),
        ("OTHER","OTHER"),
    ]
    cargo = models.ForeignKey(Cargo, related_name="charges", on_delete=models.CASCADE)
    charge_type = models.CharField(max_length=20, choices=CHARGE_CHOICES)
    description = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, blank=True)           # e.g. per CBM, per KG
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.rate or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cargo} | {self.charge_type} {self.currency} {self.rate}"
