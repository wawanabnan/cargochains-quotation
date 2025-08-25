from django.db import transaction
from django.db.models import Q
from sales.models import Quotation
from partners.models import Partner

missing = []
used_ids = set(Quotation.objects.exclude(customer_id__isnull=True).values_list("customer_id", flat=True))
for pid in sorted(used_ids):
    if not Partner.objects.filter(id=pid).exists():
        missing.append(pid)

if not missing:
    print("✓ Tidak ada partner yang hilang. FK aman.")
else:
    print("• Missing partner IDs:", missing)
    with transaction.atomic():
        for pid in missing:
            Partner.objects.create(
                id=pid,                       # penting: samakan PK
                name=f"__MIG_PLACEHOLDER_{pid}__",
                is_customer=True,
                is_active=True,
            )
    print(f"✓ Dibuat {len(missing)} Partner placeholder. Silakan update nama/alamatnya nanti via admin.")
