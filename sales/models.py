from django.db import models
from django.db.models import Sum
from django.urls import reverse
from .utils import next_quotation_number
from partners.models import Partner


class Quotation(models.Model):
    CURRENCY_CHOICES = [
        ('IDR','IDR'), ('USD','USD'), ('EUR','EUR'), ('GBP','GBP')
    ]
    number = models.CharField(max_length=30, unique=True, blank=True)
    date = models.DateField()
    customer = models.ForeignKey(
        Partner, on_delete=models.PROTECT,
        related_name="quotations",
        limit_choices_to={"is_customer": True},
    )
    validity_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    notes = models.TextualField if hasattr(models, "TextualField") else models.TextField  # guard untuk IDE
    notes = models.TextField(blank=True)


    TRANSPORT_CHOICES = [
        ('LAND','Land'), ('SEA','Sea'), ('AIR','Air'), ('MULTI','Multi')
    ]
    transport_mode = models.CharField(max_length=10, choices=TRANSPORT_CHOICES, default='SEA')
    service_option = models.CharField(max_length=30, blank=True)  # depends on mode
    multi_destination = models.BooleanField(default=True)
    destination_header = models.CharField(max_length=200, blank=True)
    origin_header = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.rate or 0)
        if not self.number or str(self.number).strip() == "":
            self.number = next_quotation_number(Quotation)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number or f"Quotation {self.pk}"

    def get_absolute_url(self):
        return reverse("sales:quotation_detail", args=[self.pk])

    @property
    def total_amount(self):
        from django.db.models import Sum
        agg = (CargoCharge.objects
               .filter(cargo__quotation=self)
               .aggregate(total=Sum('amount')))
        return agg.get('total') or 0

    @property
    def total_amount(self):
        from django.db.models import Sum
        agg = CargoCharge.objects.filter(cargo__quotation=self).aggregate(total=Sum("amount"))
        return agg.get("total") or 0

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

    def total_amount(self):
        from django.db.models import Sum
        agg = self.charges.aggregate(total=Sum("amount"))
        return agg.get("total") or 0

class CargoCharge(models.Model):
    CHARGE_CHOICES = [
        ("FREIGHT","FREIGHT"),
        ("ORIGIN","ORIGIN"),
        ("DEST","DEST"),
        ("DOC","DOC"),
        ("OTHER","OTHER"),
    ]
    cargo = models.ForeignKey(Cargo, related_name="charges", on_delete=models.CASCADE)
    description = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, blank=True)           # e.g. per CBM, per KG
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
	    self.amount = (self.qty or 0) * (self.rate or 0)
	    super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cargo} - {self.description}: {self.amount}"
