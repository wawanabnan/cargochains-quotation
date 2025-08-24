from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari root project (yang ada manage.py)."

APP = ROOT / "sales"
API = APP / "api"
TPL = APP / "templates" / "sales"

API.mkdir(parents=True, exist_ok=True)
TPL.mkdir(parents=True, exist_ok=True)

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

# 1) api/__init__.py
init_py = API / "__init__.py"
if not init_py.exists():
    init_py.write_text("", encoding="utf-8")

# 2) api/views.py (ViewSets)
views_api = API / "views.py"
backup(views_api)
views_api.write_text(
"""from rest_framework import viewsets, status
from rest_framework.response import Response
from sales.models import Quotation, Cargo, CargoCharge
from .serializers import QuotationSerializer, CargoSerializer, CargoChargeSerializer

class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.all().order_by("-date", "-id")
    serializer_class = QuotationSerializer

class CargoViewSet(viewsets.ModelViewSet):
    queryset = Cargo.objects.select_related("quotation").all()
    serializer_class = CargoSerializer

class CargoChargeViewSet(viewsets.ModelViewSet):
    queryset = CargoCharge.objects.select_related("cargo", "cargo__quotation").all()
    serializer_class = CargoChargeSerializer
""",
    encoding="utf-8",
)

# 3) api/urls.py (router)
urls_api = API / "urls.py"
backup(urls_api)
urls_api.write_text(
"""from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuotationViewSet, CargoViewSet, CargoChargeViewSet

router = DefaultRouter()
router.register(r"quotations", QuotationViewSet, basename="api-quotation")
router.register(r"cargos", CargoViewSet, basename="api-cargo")
router.register(r"charges", CargoChargeViewSet, basename="api-charge")

urlpatterns = [
    path("", include(router.urls)),
]
""",
    encoding="utf-8",
)

# 4) sales/urls.py → include pdf endpoint + (opsional) api include at project level later
sales_urls = APP / "urls.py"
backup(sales_urls)
s = sales_urls.read_text(encoding="utf-8")

# import view pdf
if "quotation_pdf" not in s:
    s = s.replace("from .views import ", "from .views import ")
# ensure import line exists
if "from .views import " not in s:
    # rewrite file adding import at top
    s = re.sub(r"(^from django.urls import path.*?$)", r"\\1\nfrom . import views", s, flags=re.MULTILINE)
    if "from . import views" in s and "views.quotation_pdf" not in s:
        pass  # we'll refer to views.quotation_pdf in pattern

# ensure pattern for pdf
if "quotation_pdf" not in s:
    s = s.replace(
        "urlpatterns = [",
        "urlpatterns = [\n    path(\"quotations/<int:pk>/pdf/\", views.quotation_pdf, name=\"quotation_pdf\"),"
    )

sales_urls.write_text(s, encoding="utf-8")

# 5) sales/views.py → add quotation_pdf view
views_py = APP / "views.py"
backup(views_py)
v = views_py.read_text(encoding="utf-8")
if "def quotation_pdf(" not in v:
    v += """

# -------- PDF EXPORT --------
from django.http import HttpResponse
from django.template.loader import render_to_string

def quotation_pdf(request, pk: int):
    from .models import Quotation
    quotation = Quotation.objects.prefetch_related("cargos__charges").get(pk=pk)

    html = render_to_string("sales/quotation_pdf.html", {"quotation": quotation})
    # Try xhtml2pdf
    try:
        from xhtml2pdf import pisa
        from io import BytesIO
        result = BytesIO()
        pdf = pisa.CreatePDF(src=html, dest=result, encoding="utf-8")
        if not pdf.err:
            resp = HttpResponse(result.getvalue(), content_type=\"application/pdf\")
            filename = f\"quotation-{quotation.number or quotation.pk}.pdf\"
            resp['Content-Disposition'] = f'inline; filename=\"{filename}\"'
            return resp
        # if error, fall-through to HTML
    except Exception as e:
        html = f\"\"\"<div style='padding:16px;background:#fff3cd;border:1px solid #ffeeba'>
        <strong>PDF generator not available.</strong><br>
        Install with: <code>pip install xhtml2pdf</code>.<br>
        Error: {e}
        </div>\"\"\" + html

    return HttpResponse(html)
"""
    views_py.write_text(v, encoding="utf-8")

# 6) sales/templates/sales/quotation_pdf.html (simple printable)
pdf_tpl = TPL / "quotation_pdf.html"
backup(pdf_tpl)
pdf_tpl.write_text(
"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Quotation {{ quotation.number }}</title>
<style>
  @page { size: A4; margin: 18mm 14mm; }
  body { font-family: Arial, Helvetica, sans-serif; font-size: 12px; color: #222; }
  h1, h2, h3 { margin: 0 0 8px; }
  .meta { margin-bottom: 12px; }
  .box { border: 1px solid #999; padding: 10px; margin-bottom: 12px; }
  .muted { color: #666; }
  table { width: 100%; border-collapse: collapse; }
  th, td { border: 1px solid #ccc; padding: 6px; vertical-align: top; }
  th { background: #f4f4f4; }
  .right { text-align: right; }
  .center { text-align: center; }
  .mb8 { margin-bottom: 8px; }
  .mb12 { margin-bottom: 12px; }
  .mt12 { margin-top: 12px; }
  .totals { margin-top: 6px; }
  .small { font-size: 11px; }
</style>
</head>
<body>
  <h1>Quotation {{ quotation.number }}</h1>
  <div class="meta muted">Date: {{ quotation.date }} &nbsp; | &nbsp; Valid Until: {{ quotation.validity_date|default:"-" }}</div>

  <div class="box">
    <table>
      <tr>
        <td width="55%">
          <strong>Customer</strong><br>
          {{ quotation.customer }}
        </td>
        <td width="45%">
          <strong>Payment Terms</strong><br>
          {{ quotation.payment_terms|default:"-" }}<br>
          {% if quotation.notes %}<div class="small mt12"><strong>Notes:</strong> {{ quotation.notes }}</div>{% endif %}
        </td>
      </tr>
    </table>
  </div>

  {% for cargo in quotation.cargos.all %}
  <h3>Cargo #{{ forloop.counter }} — {{ cargo.description }}</h3>
  <div class="mb8 muted">{{ cargo.origin }} → {{ cargo.destination }}</div>
  <table class="small mb12">
    <tr>
      <td>Pkg: {{ cargo.package_type|default:"-" }}</td>
      <td>Qty: {{ cargo.qty|floatformat:3 }}</td>
      <td>Wt(kg): {{ cargo.weight_kg|floatformat:3 }}</td>
      <td>Vol(cb m): {{ cargo.volume_cbm|floatformat:3 }}</td>
    </tr>
    {% if cargo.extra_notes %}<tr><td colspan="4">Notes: {{ cargo.extra_notes }}</td></tr>{% endif %}
  </table>

  <table>
    <thead>
      <tr>
        <th width="7%">No</th>
        <th width="14%">Charge</th>
        <th>Description</th>
        <th width="12%">Unit</th>
        <th width="10%" class="right">Qty</th>
        <th width="12%" class="right">Rate</th>
        <th width="8%" class="center">Curr</th>
        <th width="14%" class="right">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for line in cargo.charges.all %}
      <tr>
        <td class="center">{{ forloop.counter }}</td>
        <td>{{ line.charge_type }}</td>
        <td>{{ line.description|default:"" }}</td>
        <td>{{ line.unit|default:"" }}</td>
        <td class="right">{{ line.qty|floatformat:3 }}</td>
        <td class="right">{{ line.rate|floatformat:2 }}</td>
        <td class="center">{{ line.currency }}</td>
        <td class="right">{{ line.amount|floatformat:2 }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="8" class="center muted">No charges</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="totals small">
    <strong>Subtotal (per currency):</strong>
    <ul style="margin:6px 0 12px 18px;">
      {% for row in cargo.totals_by_currency %}
        <li>{{ row.currency }}: <strong>{{ row.total|floatformat:2 }}</strong></li>
      {% empty %}
        <li class="muted">No totals.</li>
      {% endfor %}
    </ul>
  </div>
  {% endfor %}

  <hr class="mb12">
  <div><strong>Grand Total (per currency):</strong></div>
  <ul class="small" style="margin:6px 0 0 18px;">
    {% for row in quotation.totals_by_currency %}
      <li>{{ row.currency }}: <strong>{{ row.total|floatformat:2 }}</strong></li>
    {% empty %}
      <li class="muted">No totals.</li>
    {% endfor %}
  </ul>
</body>
</html>
""",
    encoding="utf-8",
)

# 7) project urls.py → include /api/
# default project dir 'config'; kalau beda, ubah di sini:
PROJECT_URLS = ROOT / "config" / "urls.py"
if PROJECT_URLS.exists():
    backup(PROJECT_URLS)
    txt = PROJECT_URLS.read_text(encoding="utf-8")
    changed = False

    # ensure imports
    if "from django.urls import path, include" not in txt:
        if "from django.urls import path" in txt:
            txt = txt.replace("from django.urls import path", "from django.urls import path, include"); changed = True
        elif "from django.urls import include" in txt:
            txt = txt.replace("from django.urls import include", "from django.urls import path, include"); changed = True
        else:
            txt = "from django.urls import path, include\n" + txt; changed = True

    # ensure /api/ include
    if "include('sales.api.urls')" not in txt and 'include("sales.api.urls")' not in txt:
        if "urlpatterns" in txt:
            txt = re.sub(r"urlpatterns\s*=\s*\[",
                         "urlpatterns = [\n    path('api/', include('sales.api.urls')),\n",
                         txt, count=1)
            changed = True

    if changed:
        PROJECT_URLS.write_text(txt, encoding="utf-8")
        print("✓ Patched config/urls.py: include /api/")
    else:
        print("• config/urls.py sudah include /api/")
else:
    print("! Tidak menemukan config/urls.py — kalau nama project beda, edit variabel PROJECT_URLS di skrip ini.")

print("\\nSelesai ✅")
print("Jalankan:")
print("  pip install djangorestframework xhtml2pdf")
print("  python manage.py makemigrations && python manage.py migrate")
print("  python manage.py runserver")
