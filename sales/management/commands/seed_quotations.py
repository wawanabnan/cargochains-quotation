from django.core.management.base import BaseCommand
from datetime import date, timedelta
from sales.models import Quotation, Cargo, CargoCharge
from partners.models import Customer


class Command(BaseCommand):
    help = "Seed 5 dummy quotations with cargos and charges"

    def handle(self, *args, **options):
        # ambil customer pertama, kalau belum ada buat dummy
        customer = Customer.objects.first()
        if not customer:
            customer = Customer.objects.create(name="Demo Customer")

        # bersihkan dulu
        Quotation.objects.all().delete()

        for i in range(1, 6):
            q = Quotation.objects.create(
                date=date.today(),
                customer=customer,
                validity_date=date.today() + timedelta(days=14),
                payment_terms="TOP 14 hari",
                notes=f"Demo quotation #{i}",
            )

            if i % 2 == 0:
                cargos = [
                    Cargo.objects.create(
                        quotation=q,
                        description=f"Coal {i*1000} MT",
                        package_type="MT",
                        qty=i*1000,
                        weight_kg=i*1000000,
                        volume_cbm=i*100,
                        origin="Samarinda",
                        destination="Surabaya",
                    ),
                    Cargo.objects.create(
                        quotation=q,
                        description=f"Coal {i*1000} MT",
                        package_type="MT",
                        qty=i*1000,
                        weight_kg=i*1000000,
                        volume_cbm=i*120,
                        origin="Samarinda",
                        destination="Makassar",
                    ),
                ]
            else:
                cargos = [
                    Cargo.objects.create(
                        quotation=q,
                        description=f"Nickel Ore {i*500} MT",
                        package_type="MT",
                        qty=i*500,
                        weight_kg=i*500000,
                        volume_cbm=i*80,
                        origin="Morowali",
                        destination="Surabaya",
                    )
                ]

            for c in cargos:
                CargoCharge.objects.create(
                    cargo=c,
                    charge_type="FREIGHT",
                    description="Sea Freight",
                    unit="per MT",
                    qty=c.qty,
                    rate=25 + i,
                    currency="USD",
                )
                CargoCharge.objects.create(
                    cargo=c,
                    charge_type="DOC",
                    description="Documentation",
                    unit="per SHPT",
                    qty=1,
                    rate=200 + i * 10,
                    currency="USD",
                )

        self.stdout.write(self.style.SUCCESS("✓ 5 dummy quotations created."))
