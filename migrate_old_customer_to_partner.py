from django.db import transaction, connection
from django.apps import apps
from partners.models import Partner

Old = None
for cand in [("partners","Customer"), ("partners","customer")]:
    try:
        Old = apps.get_model(*cand)
        break
    except Exception:
        continue

if Old is None:
    # Jika model sudah dihapus tapi tabel DB-nya masih ada, pakai raw SQL
    with connection.cursor() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='partners_customer'")
        row = cur.fetchone()
    if not row:
        print("! Tidak menemukan model/tabel partners_customer. Gunakan Opsi A (placeholder).")
    else:
        print("! Tabel partners_customer ada tapi modelnya tidak terdaftar. Buat model sementara atau pakai Opsi A.")
else:
    made = 0
    with transaction.atomic():
        for c in Old.objects.all():
            if not Partner.objects.filter(id=c.pk).exists():
                Partner.objects.create(
                    id=c.pk,
                    name=getattr(c, "name", f"Customer-{c.pk}"),
                    email=getattr(c, "email", ""),
                    phone=getattr(c, "phone", ""),
                    address=getattr(c, "address", ""),
                    is_customer=True,
                    is_active=True,
                )
                made += 1
    print(f"✓ Copied {made} customers into partners_partner with same PKs.")
