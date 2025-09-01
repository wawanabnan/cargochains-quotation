# apply_service_choices_patch.py
from pathlib import Path
import re, shutil, datetime, textwrap

STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
ROOT = Path(__file__).resolve().parent

MODELS = ROOT / "sales" / "models.py"
FORMS  = ROOT / "sales" / "forms.py"
VIEWS  = ROOT / "sales" / "views.py"

# lokasi template list
TPL1 = ROOT / "sales" / "templates" / "sales" / "freight" / "list.html"
TPL2 = ROOT / "templates" / "sales" / "freight" / "list.html"

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")
    print(f"[write]  {p}")

def ensure_import(s: str, line: str) -> str:
    return s if line in s else (line + "\n" + s)

# ---------- Patch models.py: add SERVICE_CHOICES & choices on service_option ----------
def patch_models():
    if not MODELS.exists():
        print("[skip] sales/models.py not found")
        return
    backup(MODELS)
    src = read(MODELS)

    # Ensure TRANSPORT_CHOICES exists (optional, don't overwrite if already present)
    if "TRANSPORT_CHOICES" not in src:
        src = src.replace(
            "BUSINESS_TYPE = \"FREIGHT\"",
            'BUSINESS_TYPE = "FREIGHT"\n\n    TRANSPORT_CHOICES = [\n'
            '        ("SEA", "Sea"),\n        ("AIR", "Air"),\n        ("LAND", "Land"),\n    ]\n'
        )

    # Insert SERVICE_CHOICES inside FreightQuotation if missing
    if "SERVICE_CHOICES" not in src:
        src = re.sub(
            r"(class\s+FreightQuotation\(models\.Model\):\s+[^#]*?BUSINESS_TYPE\s*=\s*['\"]FREIGHT['\"])",
            r"""\1

    SERVICE_CHOICES = [
        ("DOOR_TO_DOOR", "Door to door"),
        ("DOOR_TO_PORT", "Door to port"),
        ("PORT_TO_PORT", "Port to port"),
        ("DOOR_TO_AIRPORT", "Door to airport"),
        ("AIRPORT_TO_AIRPORT", "Airport to airport"),
        ("TRUCKING", "Trucking"),
    ]""",
            src, flags=re.S
        )

    # Ensure transport_mode uses TRANSPORT_CHOICES
    src = re.sub(
        r'transport_mode\s*=\s*models\.CharField\([^)]*choices\s*=\s*\[[^\]]+\][^)]*\)',
        'transport_mode = models.CharField(max_length=20, choices=TRANSPORT_CHOICES)',
        src
    )

    # Ensure service_option has choices=SERVICE_CHOICES
    if re.search(r'service_option\s*=\s*models\.CharField\([^)]*choices\s*=', src) is None:
        src = re.sub(
            r'service_option\s*=\s*models\.CharField\(([^)]*)\)',
            r'service_option = models.CharField(\1, choices=SERVICE_CHOICES)',
            src
        )

    write(MODELS, src)
    print("[ok] models.py patched (SERVICE_CHOICES applied)")

# ---------- Patch forms.py: remove SERVICE_CHOICES/union duplicates; keep widget ----------
def patch_forms():
    if not FORMS.exists():
        print("[skip] sales/forms.py not found")
        return
    backup(FORMS)
    src = read(FORMS)

    # Remove any SERVICE_CHOICES / service_choices_union definitions in forms.py
    src = re.sub(
        r'(?ms)^\s*SERVICE_CHOICES\s*=\s*\[[^\]]*\]\s*',
        '', src
    )
    src = re.sub(
        r'(?ms)^\s*service_choices_union\s*=\s*.*?$',
        '', src
    )

    # Ensure FreightHeaderForm Meta.widgets has Select for service_option
    # If FreightHeaderForm is defined, ensure widget
    if "class FreightHeaderForm" in src:
        # Add widget mapping if not present
        if "Meta:" in src:
            # Ensure service_option widget line exists inside widgets dict
            src = re.sub(
                r'("service_option"\s*:\s*forms\.Select\([^)]+\),?)',
                r'\1', src
            )
            # If widgets dict exists but without service_option, inject it
            src = re.sub(
                r'widgets\s*=\s*\{\s*',
                'widgets = {\n            "service_option": forms.Select(attrs={"class": "form-select form-select-sm"}),\n            ',
                src, count=1
            )
    write(FORMS, src)
    print("[ok] forms.py cleaned (no duplicate choices, widget ensured)")

# ---------- Patch views.py: provide mode_choices & service_choices to template ----------
def patch_views():
    if not VIEWS.exists():
        print("[skip] sales/views.py not found")
        return
    backup(VIEWS)
    src = read(VIEWS)

    # Ensure imports
    src = ensure_import(src, "from django.utils.dateparse import parse_date")
    src = ensure_import(src, "from django.db.models import Q")
    if "from .models import FreightQuotation" not in src:
        # don't override existing import list if present
        src = ensure_import(src, "from .models import FreightQuotation, FreightCargo, FreightCharge")

    # Patch freight_list context to include mode_choices & service_choices from model
    def repl_ctx(m):
        block = m.group(0)
        # Add mode_choices & service_choices into ctx dict build
        if "mode_choices" not in block or "service_choices" not in block:
            block = re.sub(
                r'ctx\s*=\s*\{\s*',
                'ctx = {\n        "mode_choices": FreightQuotation._meta.get_field("transport_mode").choices,\n'
                '        "service_choices": FreightQuotation._meta.get_field("service_option").choices,\n',
                block, count=1
            )
        return block

    # find freight_list definition and patch its ctx
    pattern = re.compile(r'def\s+freight_list\s*\(request\):[\s\S]*?return\s+render\([^\n]+\)', re.M)
    src = pattern.sub(repl_ctx, src)

    write(VIEWS, src)
    print("[ok] views.py patched (choices injected to context)")

# ---------- Patch template list.html: render dropdown from choices & show display labels ----------
def patch_template():
    tpl = TPL1 if TPL1.exists() else TPL2
    if not tpl.exists():
        print("[skip] list.html not found in app or project templates")
        return
    backup(tpl)
    html = read(tpl)

    # Mode filter -> use mode_choices (code,label) and label "All Freight"
    html = re.sub(
        r'(<select\s+name="mode".*?>)([\s\S]*?)</select>',
        r'''<select name="mode" class="form-select form-select-sm" data-bs-toggle="tooltip" title="Filter by Freight Mode">
    <option value="">All Freight</option>
    {% for code, label in mode_choices %}
      <option value="{{ code }}" {% if filters.mode == code %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>''',
        html, flags=re.I
    )

    # Service filter -> use service_choices (code,label) and label "All Services"
    html = re.sub(
        r'(<select\s+name="service".*?>)([\s\S]*?)</select>',
        r'''<select name="service" class="form-select form-select-sm" data-bs-toggle="tooltip" title="Filter by Service">
    <option value="">All Services</option>
    {% for code, label in service_choices %}
      <option value="{{ code }}" {% if filters.service == code %}selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>''',
        html, flags=re.I
    )

    # Table columns: transport mode & service -> use display methods
    html = re.sub(r'{{\s*q\.transport_mode\s*}}', '{{ q.get_transport_mode_display }}', html)
    html = re.sub(r'{{\s*q\.service_option\s*}}', '{{ q.get_service_option_display }}', html)

    write(tpl, html)
    print("[ok] list.html patched (dropdown from choices, display labels)")

def main():
    patch_models()
    patch_forms()
    patch_views()
    patch_template()
    print("\n✅ Done. Next steps:")
    print("1) python manage.py makemigrations sales")
    print("2) python manage.py migrate")
    print("3) Restart server & hard refresh (Ctrl+F5)")
    print("Jika service dropdown masih kosong, pastikan function freight_list merender 'sales/freight/list.html' yang dipatch ini.")

if __name__ == "__main__":
    main()
