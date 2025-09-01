# patch_service_by_mode_json.py
from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

FREIGHT_LIST_NEW = textwrap.dedent(r"""
import json
import datetime
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from .models import FreightQuotation, FreightCargo, FreightCharge

# Pakai proxy Customer jika ada, fallback ke Partner
try:
    from partners.models import CustomerProxy as CustomerModel
except Exception:
    from partners.models import Partner as CustomerModel

# Mapping service berdasarkan mode transport
SERVICE_BY_MODE = {
    "SEA": [
        ("DOOR_TO_DOOR", "Door to door"),
        ("DOOR_TO_PORT", "Door to port"),
        ("PORT_TO_PORT", "Port to port"),
    ],
    "AIR": [
        ("DOOR_TO_AIRPORT", "Door to airport"),
        ("AIRPORT_TO_AIRPORT", "Airport to airport"),
    ],
    "LAND": [
        ("TRUCKING", "Trucking"),
    ],
}

def get_customer_queryset():
    qs = CustomerModel.objects.all()
    if hasattr(CustomerModel, "is_customer"):
        try:
            qs = qs.filter(is_customer=True)
        except Exception:
            pass
    return qs.order_by("name", "id")

def freight_list(request):
    qs = (FreightQuotation.objects
          .select_related("customer")
          .order_by("-date", "-id"))

    # ---- filters (GET) ----
    number      = (request.GET.get("number") or "").strip()
    customer_id = (request.GET.get("customer_id") or "").strip()
    mode        = (request.GET.get("mode") or "").strip()      # "SEA"/"AIR"/"LAND"
    status      = (request.GET.get("status") or "").strip()
    service     = (request.GET.get("service") or "").strip()   # "PORT_TO_PORT", dst
    date_from   = parse_date(request.GET.get("date_from") or "")
    date_to     = parse_date(request.GET.get("date_to") or "")

    if number:
        qs = qs.filter(number__icontains=number)
    if customer_id.isdigit():
        qs = qs.filter(customer_id=int(customer_id))
    if mode:
        qs = qs.filter(transport_mode=mode)
    if status:
        qs = qs.filter(status=status)
    if service:
        qs = qs.filter(service_option=service)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    # === dropdown data ===
    # Customer options (id, label)
    customer_options = []
    for c in get_customer_queryset():
        label = (getattr(c, "name", None)
                 or getattr(c, "company_name", None)
                 or getattr(c, "code", None)
                 or f"Customer #{c.id}")
        customer_options.append((c.id, label))

    # Mode choices langsung dari model
    mode_choices = FreightQuotation._meta.get_field("transport_mode").choices or []

    # Service choices: tergantung mode; jika mode kosong -> gabungan semua unik
    model_service_choices = FreightQuotation._meta.get_field("service_option").choices or []
    if mode:
        service_choices = SERVICE_BY_MODE.get(mode, model_service_choices)
    else:
        seen = set(); merged = []
        for k in ("SEA","AIR","LAND"):
            for code,label in SERVICE_BY_MODE.get(k, []):
                if code not in seen:
                    merged.append((code,label))
                    seen.add(code)
        service_choices = merged or model_service_choices

    ctx = {
        "quotations": qs,
        "filters": {
            "number": number,
            "customer_id": customer_id,
            "mode": mode,
            "status": status,
            "service": service,
            "date_from": request.GET.get("date_from", ""),
            "date_to": request.GET.get("date_to", ""),
        },
        "status_choices": FreightQuotation.STATUS_CHOICES,
        "customer_options": customer_options,
        "mode_choices": mode_choices,
        "service_choices": service_choices,                 # ← sudah terfilter sesuai mode
        "service_by_mode_json": json.dumps(SERVICE_BY_MODE) # ← untuk JS di template
    }
    return render(request, "sales/freight/list.html", ctx)
""").strip() + "\n"

def backup(fp: Path):
    if fp.exists():
        bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
        shutil.copy2(fp, bak)
        print(f"[backup] {fp} -> {bak.name}")

def ensure_import_block(src: str) -> str:
    # Pastikan import json ada (biar tidak double, aman saja)
    if "import json" not in src:
        src = "import json\n" + src
    return src

def replace_freight_list(src: str) -> str:
    # Hapus definisi freight_list lama + helper terkait bila ada, ganti full block baru.
    # Cari "def freight_list(request):" sampai sebelum "def " berikutnya atau EOF.
    pat = re.compile(r"\ndef\s+freight_list\s*\(request\):[\s\S]*?(?=\ndef\s+|\Z)", re.M)
    if pat.search(src):
        src = pat.sub("\n" + FREIGHT_LIST_NEW + "\n", src)
        print("[edit] Replaced existing freight_list()")
    else:
        # Jika tidak ketemu, tambahkan di akhir file.
        if not src.endswith("\n"): src += "\n"
        src += "\n" + FREIGHT_LIST_NEW
        print("[add]   Appended new freight_list()")
    return src

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")

    # Hindari duplikasi import — block baru sudah punya import standar
    # Kita akan buang import json lama ganda; tapi aman kalau tetap ada.
    src = replace_freight_list(src)
    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] Patched sales/views.py")
    print("\n✅ Selesai. Silakan refresh halaman /sales/quotations/freight/")
    print("Dropdown Service sekarang mengikuti pilihan Mode, dan tidak ada error JSON di JavaScript.")
    print("Catatan: pastikan template menggunakan serviceByMode = {{ service_by_mode_json|safe }} di JS.")
if __name__ == "__main__":
    main()
