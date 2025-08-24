from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari folder yang ada manage.py"

# EDIT: kalau nama paket project bukan 'config', ubah di sini:
PROJECT_URLS = ROOT / "config" / "urls.py"

SALES_URLS = ROOT / "sales" / "urls.py"
BASE_HTML = ROOT / "sales" / "templates" / "base.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

# 1) Patch config/urls.py -> add root redirect to quotation list, ensure include(sales.urls)
if PROJECT_URLS.exists():
    backup(PROJECT_URLS)
    txt = PROJECT_URLS.read_text(encoding="utf-8")
    changed = False

    # ensure imports
    if "from django.urls import path, include" not in txt:
        if "from django.urls import path" in txt:
            txt = txt.replace("from django.urls import path", "from django.urls import path, include")
            changed = True
        elif "from django.urls import include" in txt:
            txt = txt.replace("from django.urls import include", "from django.urls import path, include")
            changed = True
        else:
            txt = "from django.urls import path, include\n" + txt
            changed = True
    if "from django.views.generic.base import RedirectView" not in txt:
        txt = "from django.views.generic.base import RedirectView\n" + txt
        changed = True

    # ensure sales include
    if "include(\"sales.urls\")" not in txt and "include('sales.urls')" not in txt:
        # insert before urlpatterns or append
        if "urlpatterns" in txt:
            txt = re.sub(r"urlpatterns\s*=\s*\[",
                         "urlpatterns = [\n    path('sales/', include('sales.urls')),\n",
                         txt, count=1)
        else:
            txt += "\nurlpatterns = [\n    path('sales/', include('sales.urls')),\n]\n"
        changed = True

    # ensure root redirect
    if "pattern_name='sales:quotation_list'" not in txt and 'pattern_name="sales:quotation_list"' not in txt:
        if "urlpatterns" in txt:
            txt = re.sub(r"urlpatterns\s*=\s*\[",
                         "urlpatterns = [\n    path('', RedirectView.as_view(pattern_name='sales:quotation_list', permanent=False)),\n",
                         txt, count=1)
        else:
            txt += "\nurlpatterns = [\n    path('', RedirectView.as_view(pattern_name='sales:quotation_list', permanent=False)),\n]\n"
        changed = True

    if changed:
        PROJECT_URLS.write_text(txt, encoding="utf-8")
        print("✓ Patched config/urls.py (root redirect + include sales)")
    else:
        print("• config/urls.py sudah OK")
else:
    print("! Tidak menemukan config/urls.py — jika nama project beda, ubah variabel PROJECT_URLS di skrip ini.")

# 2) Patch sales/urls.py -> add index redirect for /sales/
if SALES_URLS.exists():
    backup(SALES_URLS)
    s = SALES_URLS.read_text(encoding="utf-8")
    changed = False

    if "from django.views.generic.base import RedirectView" not in s:
        s = "from django.views.generic.base import RedirectView\n" + s
        changed = True

    # ensure index route
    if "name=\"sales_index\"" not in s and "name='sales_index'" not in s:
        s = re.sub(r"urlpatterns\s*=\s*\[",
                   "urlpatterns = [\n    path('', RedirectView.as_view(pattern_name='sales:quotation_list', permanent=False), name='sales_index'),\n",
                   s, count=1)
        changed = True

    if changed:
        SALES_URLS.write_text(s, encoding="utf-8")
        print("✓ Patched sales/urls.py (index redirect /sales/ → /sales/quotations/)")
    else:
        print("• sales/urls.py sudah punya index redirect")
else:
    print("! sales/urls.py tidak ditemukan")

# 3) (Opsional) Perbaiki link brand di base.html agar menuju daftar
if BASE_HTML.exists():
    backup(BASE_HTML)
    b = BASE_HTML.read_text(encoding="utf-8")
    if 'href="/"' in b or 'href="/sales/"' in b:
        b = b.replace('href="/"', 'href="{% url \'sales:quotation_list\' %}"')
        b = b.replace('href="/sales/"', 'href="{% url \'sales:quotation_list\' %}"')
        BASE_HTML.write_text(b, encoding="utf-8")
        print("✓ base.html: brand/link diarahkan ke quotation list")
    else:
        print("• base.html tidak perlu diubah")
else:
    print("• base.html tidak ditemukan (opsional)")

print("\nSelesai. Coba akses:")
print(" - /  → redirect ke /sales/quotations/")
print(" - /sales/ → redirect ke /sales/quotations/")
