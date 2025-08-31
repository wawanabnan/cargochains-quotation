from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import random

from sales.models import FreightQuotation, FreightCargo, FreightCharge
try:
    from partners.models import Partner
except Exception:
    # fallback sederhana kalau app partners berbeda
    Partner = None

try:
    from geo.models import Location
except Exception:
    Location = None

class Command(BaseCommand):
    help = "Delete all freight quotations and seed 10 demo rows (5 single-destination, 5 multi-destination)."

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            # Hapus data lama
            FreightCharge.objects.all().delete()
            FreightCargo.objects.all().delete()
            FreightQuotation.objects.all().delete()

            # Partner: ambil yang ada / buat dummy
            partner = None
            if Partner:
                partner = Partner.objects.first()
                if partner is None:
                    # coba buat partner dummy minimalis
                    try:
                        partner = Partner.objects.create(name="PT. Demo Partner", code="DEMO")
                    except Exception:
                        pass

            today = timezone.localdate()
            modes = [("SEA","DOOR_TO_DOOR"), ("SEA","PORT_TO_PORT"), ("AIR","AIRPORT_TO_AIRPORT"), ("LAND","TRUCKING")]

            # Helper pick location sesuai mode
            def pick_locations(mode):
                if not Location:
                    return (None, None)
                qs = Location.objects.all().order_by("?")
                if mode == "SEA":
                    qs = qs.filter(type__in=[getattr(Location, "SEAPORT", "SEAPORT"), getattr(Location, "JETTY", "JETTY")])
                elif mode == "AIR":
                    qs = qs.filter(type=getattr(Location, "AIRPORT", "AIRPORT"))
                else:
                    qs = qs.filter(type__in=[getattr(Location, "CITY", "CITY"), getattr(Location, "JETTY", "JETTY")])
                origin = qs.first()
                dest = qs[1] if qs.count() > 1 else origin
                return (origin, dest)

            # 5 single-destination (1 cargo)
            created = 0
            for i in range(5):
                mode, service = random.choice(modes)
                q = FreightQuotation.objects.create(
                    date=today,
                    customer=partner if partner else None,
                    currency="IDR",
                    payment_term="TOP 14 days",
                    transport_mode=mode,
                    service_option=service,
                    notes=f"Demo single cargo {i+1}",
                    multi_destination=False,
                )
                o, d = pick_locations(mode)
                FreightCargo.objects.create(
                    quotation=q,
                    description=f"Commodity S{i+1}",
                    qty=1,
                    weight_kg=100 + i * 10,
                    volume_cbm=5 + i,
                    price=500000,
                    amount=500000,
                    origin=o,
                    destination=d,
                )
                created += 1

            # 5 multi-destination (2 cargo)
            for i in range(5):
                mode, service = random.choice(modes)
                q = FreightQuotation.objects.create(
                    date=today,
                    customer=partner if partner else None,
                    currency="IDR",
                    payment_term="TOP 30 days",
                    transport_mode=mode,
                    service_option=service,
                    notes=f"Demo multi cargo {i+1}",
                    multi_destination=True,
                )
                # cargo 1
                o1, d1 = pick_locations(mode)
                FreightCargo.objects.create(
                    quotation=q,
                    description=f"Commodity M{i+1}-1",
                    qty=2,
                    weight_kg=200 + i * 20,
                    volume_cbm=8 + i,
                    price=750000,
                    amount=1500000,
                    origin=o1,
                    destination=d1,
                )
                # cargo 2
                o2, d2 = pick_locations(mode)
                FreightCargo.objects.create(
                    quotation=q,
                    description=f"Commodity M{i+1}-2",
                    qty=1,
                    weight_kg=120 + i * 12,
                    volume_cbm=4 + i,
                    price=600000,
                    amount=600000,
                    origin=o2,
                    destination=d2,
                )
                created += 1

            self.stdout.write(self.style.SUCCESS(f"Seeded {created} FreightQuotation rows (with cargos)."))
