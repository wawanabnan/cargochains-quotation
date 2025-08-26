from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from partners.models import Partner  # pastikan app 'partners' aktif

CURRENCY_CHOICES = [("IDR","IDR"),("USD","USD"),("EUR","EUR"),("GBP","GBP")]
BUSINESS_CHOICES = [("FREIGHT","Freight"), ("SHIP_CHARTER","Ship Charter")]
CHARTER_CHOICES = [("VOYAGE","Voyage"), ("TIME","Time")]

class DocSequence(models.Model):
    key = models.CharField(max_length=20, unique=True)
    last_no = models.PositiveIntegerField(default=0)
    def __str__(self): return f"{self.key}:{self.last_no}"

def next_quotation_number():
    yymm = timezone.now().strftime("%y%m")
    key = f"Q{yymm}"
    with transaction.atomic():
        seq, _ = DocSequence.objects.select_for_update().get_or_create(key=key, defaults={"last_no": 0})
        seq.last_no = F("last_no") + 1
        seq.save(update_fields=["last_no"])
        seq.refresh_from_db(fields=["last_no"])
        return f"{key}-{seq.last_no:04d}"

class Quotation(models.Model):
    number = models.CharField(max_length=30, unique=True, blank=True)
    date = models.DateField(default=timezone.now)
    validity_date = models.DateField(null=True, blank=True)
    customer = models.ForeignKey(
        Partner, on_delete=models.PROTECT,
        related_name="sales_quotations",
        limit_choices_to={"is_customer": True},
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="IDR")

    business_type = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default="FREIGHT")

    # Freight header
    transport_mode = models.CharField(max_length=10, default="SEA")          # LAND/SEA/AIR/MULTI
    service_option = models.CharField(max_length=30, default="PORT_TO_PORT")
    multi_destination = models.BooleanField(default=True)
    origin = models.CharField(max_length=120, blank=True)
    destination = models.CharField(max_length=120, blank=True)

    # Charter header (dipertahankan untuk masa depan)
    charter_type = models.CharField(max_length=10, choices=CHARTER_CHOICES, blank=True)
    vessel_name = models.CharField(max_length=120, blank=True)
    vessel_type = models.CharField(max_length=120, blank=True)
    dwt_mt = models.IntegerField(null=True, blank=True)
    laycan_start = models.DateField(null=True, blank=True)
    laycan_end = models.DateField(null=True, blank=True)
    laytime_allowed_hours = models.IntegerField(null=True, blank=True)
    reversible_laytime = models.BooleanField(default=False)
    demurrage_usd_per_day = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    despatch_usd_per_day = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bunker_terms = models.CharField(max_length=200, blank=True)

    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if (not self.pk) and (not self.number or str(self.number).strip() == ""):
            # auto-numbering untuk quotation
            self.number = next_quotation_number()
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.number or '(draft)'} - {self.customer}"

class Cargo(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="cargos")
    description = models.CharField(max_length=200)
    origin = models.CharField(max_length=120, blank=True)
    destination = models.CharField(max_length=120, blank=True)
    qty = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    def __str__(self): return f"{self.description} ({self.origin} -> {self.destination})"

class CargoCharge(models.Model):
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE, related_name="charges")
    description = models.CharField(max_length=200)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.rate or 0)
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cargo","description"], name="uniq_charge_per_cargo"),
        ]

    def __str__(self): return f"{self.description} = {self.amount}"

class CharterLeg(models.Model):
    KINDS=[("LOAD","Load"),("DISCH","Disch"),("BUNKER","Bunker"),("PASSAGE","Passage")]
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="legs")
    order = models.PositiveIntegerField(default=1)
    kind = models.CharField(max_length=10, choices=KINDS, default="LOAD")
    port = models.CharField(max_length=120)
    terminal = models.CharField(max_length=120, blank=True)
    remarks = models.CharField(max_length=200, blank=True)
    class Meta: ordering=["order"]
    def __str__(self): return f"{self.order}. {self.get_kind_display()} - {self.port}"

class CharterCharge(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="charter_charges")
    description = models.CharField(max_length=200)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    def save(self,*a,**kw):
        self.amount = (self.qty or 0) * (self.rate or 0)
        super().save(*a,**kw)
    def __str__(self): return f"{self.description} = {self.amount}"
