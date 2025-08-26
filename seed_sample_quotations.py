from datetime import date, timedelta
from decimal import Decimal
from sales.models import Quotation, Cargo, CargoCharge
from partners.models import Partner

def get_customer(name):
    return Partner.objects.filter(name=name, is_customer=True).first()

def make_single(customer_name, origin, dest, cargos):
    c = get_customer(customer_name)
    q = Quotation.objects.create(
        customer=c, currency="IDR", business_type="FREIGHT",
        transport_mode="SEA", service_option="PORT_TO_PORT",
        multi_destination=False, origin=origin, destination=dest,
        date=date.today(), validity_date=date.today()+timedelta(days=14),
        notes=f"Single-destination test for {customer_name}"
    )
    for desc, qty in cargos:
        cg = Cargo.objects.create(quotation=q, description=desc, qty=qty, origin=origin, destination=dest)
        CargoCharge.objects.create(cargo=cg, description="Ocean Freight", qty=qty, rate=Decimal("250000"))
        CargoCharge.objects.create(cargo=cg, description="THC", qty=1, rate=Decimal("150000"))
    return q

def make_multi(customer_name, cargos):
    c = get_customer(customer_name)
    q = Quotation.objects.create(
        customer=c, currency="IDR", business_type="FREIGHT",
        transport_mode="SEA", service_option="DOOR_TO_PORT",
        multi_destination=True, origin="", destination="",
        date=date.today(), validity_date=date.today()+timedelta(days=21),
        notes=f"Multi-destination test for {customer_name}"
    )
    for desc, origin, dest, qty in cargos:
        cg = Cargo.objects.create(quotation=q, description=desc, qty=qty, origin=origin, destination=dest)
        CargoCharge.objects.create(cargo=cg, description="Pickup Trucking", qty=1, rate=Decimal("500000"))
        CargoCharge.objects.create(cargo=cg, description="Ocean Freight", qty=qty, rate=Decimal("275000"))
    return q

def run():
    if not Partner.objects.filter(is_customer=True).exists():
        print("! No customers, please load partners fixtures first: python manage.py loaddata partners_sample.json")
        return

    Qs = []
    Qs.append(make_single("PT. ABC Mining", "Jakarta", "Surabaya", [("Steel Coil", 10), ("Machinery", 2)]))
    Qs.append(make_single("PT. Nusantara Logistik", "Semarang", "Makassar", [("Textile Rolls", 30)]))
    Qs.append(make_multi("PT. Samudera Raya", [("Fertilizer", "Jakarta", "Medan", 20), ("Fertilizer", "Jakarta", "Balikpapan", 15)]))
    Qs.append(make_multi("CV. Berkah Jaya", [("Electronics", "Bandung", "Batam", 5), ("Electronics", "Bandung", "Banjarmasin", 3)]))
    Qs.append(make_single("PT. Lintas Benua", "Surabaya", "Belawan", [("Paper Reels", 12)]))

    print(f"✓ Seeded {len(Qs)} quotations. IDs: {[q.id for q in Qs]}")
