from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "partners"
MODELS = APP_DIR / "models.py"
ADMIN  = APP_DIR / "admin.py"
FIXT_DIR = APP_DIR / "fixtures"
FIXT_DIR.mkdir(parents=True, exist_ok=True)
FIXT_FILE = FIXT_DIR / "partners_sample.json"

TEMPLATE_MODELS = """
from django.db import models

class Partner(models.Model):
    name        = models.CharField(max_length=200, unique=True)
    address     = models.TextField(blank=True)
    phone       = models.CharField(max_length=50, blank=True)
    email       = models.EmailField(blank=True)

    # multi-role flags
    is_customer = models.BooleanField(default=False)
    is_vendor   = models.BooleanField(default=False)
    is_agent    = models.BooleanField(default=False)

    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# Proxy managers
class CustomerManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_customer=True, is_active=True)

class VendorManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_vendor=True, is_active=True)

class AgentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_agent=True, is_active=True)


# Proxy models (aman: nama berbeda dari model konkret lama)
class CustomerProxy(Partner):
    objects = CustomerManager()
    class Meta:
        proxy = True
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

class VendorProxy(Partner):
    objects = VendorManager()
    class Meta:
        proxy = True
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"

class AgentProxy(Partner):
    objects = AgentManager()
    class Meta:
        proxy = True
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
"""

TEMPLATE_ADMIN = """
from django.contrib import admin
from .models import Partner, CustomerProxy, VendorProxy, AgentProxy

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "is_customer", "is_vendor", "is_agent", "is_active")
    list_filter = ("is_customer","is_vendor","is_agent","is_active")
    search_fields = ("name","email","phone")

@admin.register(CustomerProxy)
class CustomerProxyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_active")
    search_fields = ("name","email","phone")
    def save_model(self, request, obj, form, change):
        obj.is_customer = True
        obj.save()

@admin.register(VendorProxy)
class VendorProxyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_active")
    search_fields = ("name","email","phone")
    def save_model(self, request, obj, form, change):
        obj.is_vendor = True
        obj.save()

@admin.register(AgentProxy)
class AgentProxyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_active")
    search_fields = ("name","email","phone")
    def save_model(self, request, obj, form, change):
        obj.is_agent = True
        obj.save()
"""

TEMPLATE_FIXTURE = """[
  { "model": "partners.partner", "pk": 101, "fields": { "name": "PT. ABC Mining",        "is_customer": true  } },
  { "model": "partners.partner", "pk": 102, "fields": { "name": "PT. Laut Nusantara",     "is_customer": true  } },
  { "model": "partners.partner", "pk": 103, "fields": { "name": "PT. Cepat Kirim",       "is_customer": true  } },
  { "model": "partners.partner", "pk": 104, "fields": { "name": "PT. Logistik Darat",    "is_customer": true, "is_vendor": true } },
  { "model": "partners.partner", "pk": 105, "fields": { "name": "PT. Ekspor Makmur",     "is_customer": true  } },
  { "model": "partners.partner", "pk": 106, "fields": { "name": "PT. Multimoda Global",  "is_customer": true, "is_agent": true } },
  { "model": "partners.partner", "pk": 107, "fields": { "name": "CV. Pelayaran Jaya",    "is_vendor":   true  } },
  { "model": "partners.partner", "pk": 108, "fields": { "name": "PT. Agency Samudera",   "is_agent":    true  } }
]
"""

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup {p} -> {b.name}")

print("== Patch Partner + Proxy Models ==")

APP_DIR.mkdir(parents=True, exist_ok=True)

# models.py
if MODELS.exists():
    backup(MODELS)
    content = MODELS.read_text(encoding="utf-8")
    need_partner = "class Partner(" not in content
    need_proxies = ("class CustomerProxy(" not in content) or ("class VendorProxy(" not in content) or ("class AgentProxy(" not in content)
    if need_partner or need_proxies:
        # tambahkan di akhir file
        MODELS.write_text(content.rstrip() + "\n\n" + TEMPLATE_MODELS.strip() + "\n", encoding="utf-8")
        print("✓ models.py: Partner + proxy models ditambahkan (append)")
    else:
        print("• models.py: sudah ada Partner & proxies")
else:
    MODELS.write_text(TEMPLATE_MODELS.strip() + "\n", encoding="utf-8")
    print("✓ models.py: dibuat baru dengan Partner + proxies")

# admin.py
if ADMIN.exists():
    backup(ADMIN)
    a = ADMIN.read_text(encoding="utf-8")
    if "CustomerProxy" not in a or "PartnerAdmin" not in a:
        ADMIN.write_text(TEMPLATE_ADMIN.strip() + "\n", encoding="utf-8")
        print("✓ admin.py: diperbarui untuk Partner + proxies")
    else:
        print("• admin.py: sudah berisi registrasi proxies")
else:
    ADMIN.write_text(TEMPLATE_ADMIN.strip() + "\n", encoding="utf-8")
    print("✓ admin.py: dibuat")

# fixture sample
if not FIXT_FILE.exists():
    FIXT_FILE.write_text(TEMPLATE_FIXTURE, encoding="utf-8")
    print(f"✓ fixture sample: {FIXT_FILE}")
else:
    print("• fixture sample sudah ada")

print("\nSelesai ✅")
print("Lanjutkan:")
print("  python manage.py makemigrations partners")
print("  python manage.py migrate")
print("  # (opsional) seed data contoh:")
print("  python manage.py loaddata partners/fixtures/partners_sample.json")
print("\nPemakaian di model lain:")
print("  - ForeignKey tetap menunjuk ke partners.Partner")
print("  - Di form, limit queryset ke CustomerProxy/VendorProxy/AgentProxy sesuai kebutuhan")
