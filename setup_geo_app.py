from pathlib import Path
import re, shutil, datetime, textwrap, sys

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    print(f"[write]  {p}")

def ensure_settings():
    # cari settings.py
    candidates = list(ROOT.glob("**/settings.py"))
    if not candidates:
        sys.exit("Tidak menemukan settings.py. Jalankan skrip ini di root Django project.")
    # ambil yang paling pendek path-nya
    return sorted(candidates, key=lambda p: len(str(p)))[0]

def add_geo_to_installed_apps(settings_path: Path):
    backup(settings_path)
    txt = settings_path.read_text(encoding="utf-8")
    if re.search(r"['\"]geo['\"]", txt):
        print("[settings] 'geo' sudah ada di INSTALLED_APPS")
        return
    pattern = re.compile(r"INSTALLED_APPS\s*=\s*\[.*?\]", re.S)
    m = pattern.search(txt)
    if not m:
        sys.exit("Tidak menemukan INSTALLED_APPS di settings.py")
    block = m.group(0)
    # sisipkan 'geo' sebelum penutup ]
    block_new = re.sub(r"\]$", ",\n    'geo',\n]", block, flags=re.S)
    txt = txt.replace(block, block_new)
    settings_path.write_text(txt, encoding="utf-8")
    print("[settings] tambah 'geo' ke INSTALLED_APPS")

def create_geo_app():
    geo = ROOT / "geo"
    (geo / "__init__.py").parent.mkdir(exist_ok=True)
    write(geo / "__init__.py", "")
    write(geo / "apps.py", """
    from django.apps import AppConfig
    class GeoConfig(AppConfig):
        default_auto_field = "django.db.models.BigAutoField"
        name = "geo"
    """)
    write(geo / "models.py", """
    from django.db import models

    class Location(models.Model):
        CITY = "CITY"
        SEAPORT = "SEAPORT"
        AIRPORT = "AIRPORT"
        JETTY = "JETTY"
        TYPE_CHOICES = [
            (CITY, "City"),
            (SEAPORT, "Sea Port"),
            (AIRPORT, "Airport"),
            (JETTY, "Jetty"),
        ]
        name = models.CharField(max_length=150)
        code = models.CharField(max_length=20, blank=True)      # IATA / UN/Locode / internal code
        country = models.CharField(max_length=2, blank=True)    # ISO (ID, SG, ...)
        type = models.CharField(max_length=10, choices=TYPE_CHOICES)

        class Meta:
            ordering = ["type", "name"]
            unique_together = [("code", "type")]

        def __str__(self):
            suf = f" - {self.code}" if self.code else ""
            return f"{self.name} ({self.type}){suf}"
    """)
    write(geo / "admin.py", """
    from django.contrib import admin
    from .models import Location

    @admin.register(Location)
    class LocationAdmin(admin.ModelAdmin):
        list_display = ("name", "type", "code", "country")
        list_filter = ("type","country")
        search_fields = ("name","code")
    """)
    mig = geo / "migrations"
    mig.mkdir(parents=True, exist_ok=True)
    write(mig / "__init__.py", "")

def patch_sales_models():
    sales_models = ROOT / "sales" / "models.py"
    if not sales_models.exists():
        print("[warn] sales/models.py tidak ditemukan, lewati patch models sales.")
        return
    backup(sales_models)
    txt = sales_models.read_text(encoding="utf-8")

    # import Location
    if "from geo.models import Location" not in txt:
        txt = txt.replace("from django.conf import settings", "from django.conf import settings\nfrom geo.models import Location")

    # ganti origin/destination menjadi FK ke Location
    # kasus 1: sudah FK tapi bukan ke geo.Location → normalkan
    txt = re.sub(
        r"origin\s*=\s*models\.ForeignKey\([^\)]*\)",
        "origin = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True, related_name='cargo_origins')",
        txt
    )
    txt = re.sub(
        r"destination\s*=\s*models\.ForeignKey\([^\)]*\)",
        "destination = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True, related_name='cargo_destinations')",
        txt
    )
    # kasus 2: sebelumnya CharField → ganti definisi sederhana (pattern baris)
    txt = re.sub(
        r"origin\s*=\s*models\.CharField\(.*?\)\s*",
        "origin = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True, related_name='cargo_origins')",
        txt, flags=re.S
    )
    txt = re.sub(
        r"destination\s*=\s*models\.CharField\(.*?\)\s*",
        "destination = models.ForeignKey(Location, on_delete=models.PROTECT, null=True, blank=True, related_name='cargo_destinations')",
        txt, flags=re.S
    )

    sales_models.write_text(txt, encoding="utf-8")
    print("[patched] sales/models.py (origin/destination -> FK geo.Location)")

def patch_sales_forms():
    sales_forms = ROOT / "sales" / "forms.py"
    if not sales_forms.exists():
        print("[warn] sales/forms.py tidak ditemukan, lewati patch forms sales.")
        return
    backup(sales_forms)
    txt = sales_forms.read_text(encoding="utf-8")

    # import Location dari geo
    if "from geo.models import Location" not in txt:
        txt = txt.replace(
            "from .models import FreightQuotation, FreightCargo, FreightCharge",
            "from .models import FreightQuotation, FreightCargo, FreightCharge\nfrom geo.models import Location"
        )

    # pastikan FreightCargoForm origin/destination adalah ModelChoiceField dengan queryset none (nanti di-assign di views)
    # Tambah definisi form fields jika belum ada
    pattern = re.compile(r"class\s+FreightCargoForm\(forms\.ModelForm\):(.*?)(\nclass\s|\Z)", re.S)
    m = pattern.search(txt)
    if m:
        block = m.group(0)
        if "ModelChoiceField" not in block:
            block_new = block.replace(
                "class Meta:",
                """origin = forms.ModelChoiceField(queryset=Location.objects.none(), required=False, widget=forms.Select(attrs={"class":"form-select form-select-sm"}))
    destination = forms.ModelChoiceField(queryset=Location.objects.none(), required=False, widget=forms.Select(attrs={"class":"form-select form-select-sm"}))

    class Meta:"""
            )
            txt = txt.replace(block, block_new)

        # bersihkan widget text untuk origin/destination jika masih ada
        txt = re.sub(
            r'"origin":\s*forms\.TextInput\([^\)]*\),\s*',
            '',
            txt
        )
        txt = re.sub(
            r'"destination":\s*forms\.TextInput\([^\)]*\),\s*',
            '',
            txt
        )

    sales_forms.write_text(txt, encoding="utf-8")
    print("[patched] sales/forms.py (CargoForm pakai ModelChoiceField Location)")

def patch_sales_views():
    sales_views = ROOT / "sales" / "views.py"
    if not sales_views.exists():
        print("[warn] sales/views.py tidak ditemukan, lewati patch views sales.")
        return
    backup(sales_views)
    txt = sales_views.read_text(encoding="utf-8")

    # import Location
    if "from geo.models import Location" not in txt:
        txt = txt.replace(
            "from .models import FreightQuotation, FreightCargo, FreightCharge",
            "from .models import FreightQuotation, FreightCargo, FreightCharge\nfrom geo.models import Location"
        )

    # di step "lines", setelah cargo_fs dibuat, set queryset berdasarkan mode
    # Sisipkan blok pengaturan queryset jika belum ada
    if "loc_types =" not in txt or "Location.SEAPORT" not in txt:
        txt = re.sub(
            r"(if step == \"lines\":\n\s+hdr = wiz\[\"header\"\][\s\S]+?if request\.method == \"POST\":[\s\S]+?charge_fs = ChargeFS\(request\.POST, prefix=\"charge\"\)\n\s+)",
            r"""\\1
    # Filter Location sesuai transport_mode
    mode = hdr.get("transport_mode", "SEA").upper()
    if mode == "SEA":
        loc_types = [Location.SEAPORT, Location.JETTY]
    elif mode == "AIR":
        loc_types = [Location.AIRPORT]
    else:  # LAND / default
        loc_types = [Location.CITY, Location.JETTY]

    loc_qs = Location.objects.filter(type__in=loc_types).order_by("name")
    for f in cargo_fs.forms:
        if "origin" in f.fields:
            f.fields["origin"].queryset = loc_qs
        if "destination" in f.fields:
            f.fields["destination"].queryset = loc_qs
    """,
            txt
        )
        # juga path GET branch
        txt = re.sub(
            r"(# GET\s*\n\s*cargo_fs = CargoFS\(prefix=\"cargo\"\)\n\s*charge_fs = ChargeFS\(prefix=\"charge\"\)\n\s*return render\(request, \"sales/freight/new\.html\",\s*\{\s*\"step\":\s*\"lines\",\s*\"cargo_fs\":\s*cargo_fs,\s*\"charge_fs\":\s*charge_fs\s*\}\)\n)",
            r"""# GET
        cargo_fs = CargoFS(prefix="cargo")
        charge_fs = ChargeFS(prefix="charge")

        mode = hdr.get("transport_mode", "SEA").upper()
        if mode == "SEA":
            loc_types = [Location.SEAPORT, Location.JETTY]
        elif mode == "AIR":
            loc_types = [Location.AIRPORT]
        else:
            loc_types = [Location.CITY, Location.JETTY]
        loc_qs = Location.objects.filter(type__in=loc_types).order_by("name")
        for f in cargo_fs.forms:
            if "origin" in f.fields:
                f.fields["origin"].queryset = loc_qs
            if "destination" in f.fields:
                f.fields["destination"].queryset = loc_qs

        return render(request, "sales/freight/new.html", {
            "step": "lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs
        })
        """,
            txt
        )

    sales_views.write_text(txt, encoding="utf-8")
    print("[patched] sales/views.py (filter Location sesuai mode)")

def main():
    settings_py = ensure_settings()
    add_geo_to_installed_apps(settings_py)
    create_geo_app()
    patch_sales_models()
    patch_sales_forms()
    patch_sales_views()
    print("\n✅ Selesai men-setup app `geo` dan patch `sales`.")
    print("➡ Langkah berikut (manual):")
    print("   python manage.py makemigrations geo")
    print("   python manage.py makemigrations sales")
    print("   python manage.py migrate")
    print("\nTips:")
    print(" - Input master lokasi di /admin (Geo → Locations).")
    print(" - Saat membuat Freight Quotation, pilih transport mode di Header → pada step Cargo dropdown O/D otomatis terfilter.")

if __name__ == "__main__":
    main()
