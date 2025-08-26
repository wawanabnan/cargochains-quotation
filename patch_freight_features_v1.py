from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
TPL = APP / "templates" / "sales"
MIG = APP / "migrations"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print("• backup ->", b)

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print("• write", p)

print("== Patch Freight Core Features (sales) ==")

# ---------- models.py ----------
models_py = r"""
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from partners.models import Partner  # pastikan app 'partners' aktif

CURRENCY_CHOICES = [("IDR","IDR"),("USD","USD"),("EUR","EUR"),("GBP","GBP")]
BUSINESS_CHOICES = [("FREIGHT","Freight"), ("SHIP_CHARTER","Ship Charter")]
CHARTER_CHOICES = [("VOYAGE","Voyage"), ("TIME","Time")]

class DocSequence(models.Model):
    key = models.CharField(max_length=20, unique=True)
    last_no = models.PositiveIntegerField(default=0)
    def __str__(self): return f"{self.key}:{self.last_no}"

def next_quotation_number():
    yymm = timezone.now().strftime("%y%m")
    key = f"Q{yymm}"
    with transaction.atomic():
        seq, _ = DocSequence.objects.select_for_update().get_or_create(key=key, defaults={"last_no": 0})
        seq.last_no = F("last_no") + 1
        seq.save(update_fields=["last_no"])
        seq.refresh_from_db(fields=["last_no"])
        return f"{key}-{seq.last_no:04d}"

class Quotation(models.Model):
    number = models.CharField(max_length=30, unique=True, blank=True)
    date = models.DateField(default=timezone.now)
    validity_date = models.DateField(null=True, blank=True)
    customer = models.ForeignKey(
        Partner, on_delete=models.PROTECT,
        related_name="sales_quotations",
        limit_choices_to={"is_customer": True},
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="IDR")

    business_type = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default="FREIGHT")

    # Freight header
    transport_mode = models.CharField(max_length=10, default="SEA")          # LAND/SEA/AIR/MULTI
    service_option = models.CharField(max_length=30, default="PORT_TO_PORT")
    multi_destination = models.BooleanField(default=True)
    origin = models.CharField(max_length=120, blank=True)
    destination = models.CharField(max_length=120, blank=True)

    # Charter header (dipertahankan untuk masa depan)
    charter_type = models.CharField(max_length=10, choices=CHARTER_CHOICES, blank=True)
    vessel_name = models.CharField(max_length=120, blank=True)
    vessel_type = models.CharField(max_length=120, blank=True)
    dwt_mt = models.IntegerField(null=True, blank=True)
    laycan_start = models.DateField(null=True, blank=True)
    laycan_end = models.DateField(null=True, blank=True)
    laytime_allowed_hours = models.IntegerField(null=True, blank=True)
    reversible_laytime = models.BooleanField(default=False)
    demurrage_usd_per_day = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    despatch_usd_per_day = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bunker_terms = models.CharField(max_length=200, blank=True)

    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if (not self.pk) and (not self.number or str(self.number).strip() == ""):
            # auto-numbering untuk quotation
            self.number = next_quotation_number()
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.number or '(draft)'} - {self.customer}"

class Cargo(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="cargos")
    description = models.CharField(max_length=200)
    origin = models.CharField(max_length=120, blank=True)
    destination = models.CharField(max_length=120, blank=True)
    qty = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    def __str__(self): return f"{self.description} ({self.origin} -> {self.destination})"

class CargoCharge(models.Model):
    cargo = models.ForeignKey(Cargo, on_delete=models.CASCADE, related_name="charges")
    description = models.CharField(max_length=200)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.rate or 0)
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cargo","description"], name="uniq_charge_per_cargo"),
        ]

    def __str__(self): return f"{self.description} = {self.amount}"

class CharterLeg(models.Model):
    KINDS=[("LOAD","Load"),("DISCH","Disch"),("BUNKER","Bunker"),("PASSAGE","Passage")]
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="legs")
    order = models.PositiveIntegerField(default=1)
    kind = models.CharField(max_length=10, choices=KINDS, default="LOAD")
    port = models.CharField(max_length=120)
    terminal = models.CharField(max_length=120, blank=True)
    remarks = models.CharField(max_length=200, blank=True)
    class Meta: ordering=["order"]
    def __str__(self): return f"{self.order}. {self.get_kind_display()} - {self.port}"

class CharterCharge(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="charter_charges")
    description = models.CharField(max_length=200)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    def save(self,*a,**kw):
        self.amount = (self.qty or 0) * (self.rate or 0)
        super().save(*a,**kw)
    def __str__(self): return f"{self.description} = {self.amount}"
"""

# ---------- forms.py ----------
forms_py = r"""
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, Cargo, CargoCharge, CharterLeg, CharterCharge

class QuotationFreightForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["date","validity_date","customer","currency",
                  "transport_mode","service_option","multi_destination",
                  "origin","destination","notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type":"date"}),
            "validity_date": forms.DateInput(attrs={"type":"date"}),
            "notes": forms.Textarea(attrs={"rows":2}),
        }

class QuotationCharterForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["date","validity_date","customer","currency",
                  "charter_type","vessel_name","vessel_type","dwt_mt",
                  "laycan_start","laycan_end","laytime_allowed_hours","reversible_laytime",
                  "demurrage_usd_per_day","despatch_usd_per_day","bunker_terms","notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type":"date"}),
            "validity_date": forms.DateInput(attrs={"type":"date"}),
            "laycan_start": forms.DateInput(attrs={"type":"date"}),
            "laycan_end": forms.DateInput(attrs={"type":"date"}),
            "notes": forms.Textarea(attrs={"rows":2}),
        }

class BaseCargoChargeFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if self.can_delete and form.cleaned_data.get("DELETE"):
                continue
            desc = (form.cleaned_data.get("description") or "").strip().lower()
            if not desc:
                continue
            if desc in seen:
                raise forms.ValidationError("Duplicate charge description on the same cargo.")
            seen.add(desc)

CargoFormSet = inlineformset_factory(
    Quotation, Cargo,
    fields=["description","origin","destination","qty","weight_kg","volume_cbm"],
    extra=1, can_delete=True
)

CargoChargeFormSet = inlineformset_factory(
    Cargo, CargoCharge,
    fields=["description","qty","rate"],
    extra=1, can_delete=True,
    formset=BaseCargoChargeFormSet
)

LegFormSet = inlineformset_factory(
    Quotation, CharterLeg,
    fields=["order","kind","port","terminal","remarks"],
    extra=1, can_delete=True
)

CharterChargeFormSet = inlineformset_factory(
    Quotation, CharterCharge,
    fields=["description","qty","rate"],
    extra=1, can_delete=True
)
"""

# ---------- views.py ----------
views_py = r"""
from django import forms as djforms
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.template.loader import render_to_string

from .models import Quotation
from .forms import (
    QuotationFreightForm, CargoFormSet,
    QuotationCharterForm, LegFormSet, CharterChargeFormSet
)

# ====== List & Detail ======
def quotation_list(request):
    qs = Quotation.objects.select_related("customer").order_by("-date","number")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "sales/quotation_list.html", {"page_obj": page_obj})

def quotation_detail(request, pk):
    q = get_object_or_404(Quotation.objects.select_related("customer"), pk=pk)
    if q.business_type == "FREIGHT":
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("cargos__charges").first())
    else:
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("legs","charter_charges").first())
    return render(request, "sales/quotation_detail.html", {"q": q})

# ====== Start (v3) ======
WIZ_COMMON_KEY = "sales_wiz_common"
def quotation_wizard_v3_start(request):
    if request.method == "POST":
        bt = (request.POST.get("business_type") or "FREIGHT").upper()
        tm = (request.POST.get("transport_mode") or "SEA").upper()
        so = (request.POST.get("service_option") or "PORT_TO_PORT").upper()
        md = True if request.POST.get("multi_destination") in ("on","true","1","True") else False
        request.session[WIZ_COMMON_KEY] = {"transport_mode": tm, "service_option": so, "multi_destination": md}
        # Fokus Freight dulu
        return redirect(reverse("sales:freight_wizard") + "?step=1")
    return render(request, "sales/quotation_wizard_v3_start.html", {})

# ====== Freight Wizard (Step 1 header -> Step 2 cargos) ======
WIZ_FREIGHT_HEADER = "sales_wiz_freight_header"
def freight_wizard(request):
    step = int(request.GET.get("step","1"))
    common = request.session.get(WIZ_COMMON_KEY, {"transport_mode":"SEA","service_option":"PORT_TO_PORT","multi_destination":True})
    show_od_in_header = not common.get("multi_destination", True)

    if step == 1:
        if request.method == "POST":
            post = request.POST.copy()
            post["business_type"] = "FREIGHT"
            qform = QuotationFreightForm(post)
            if qform.is_valid():
                data = qform.cleaned_data
                data["business_type"] = "FREIGHT"
                # default dari step0
                data.setdefault("transport_mode", common.get("transport_mode"))
                data.setdefault("service_option", common.get("service_option"))
                data.setdefault("multi_destination", common.get("multi_destination"))
                # jika multi-destination True, kosongkan O/D header (tidak dipakai)
                if data.get("multi_destination"):
                    data["origin"] = ""
                    data["destination"] = ""
                request.session[WIZ_FREIGHT_HEADER] = data
                request.session.modified = True
                return redirect(reverse("sales:freight_wizard") + "?step=2")
            return render(request, "sales/quotation_wizard.html", {"step":1,"mode":"FREIGHT","qform":qform,"fs":None,"common":common,"show_od_in_header":show_od_in_header})
        else:
            initial = request.session.get(WIZ_FREIGHT_HEADER, {"business_type":"FREIGHT", **common})
            if initial.get("multi_destination"):
                initial["origin"] = ""
                initial["destination"] = ""
            return render(request, "sales/quotation_wizard.html", {"step":1,"mode":"FREIGHT","qform":QuotationFreightForm(initial=initial),"fs":None,"common":common,"show_od_in_header":show_od_in_header})

    if step == 2:
        header = request.session.get(WIZ_FREIGHT_HEADER)
        if not header:
            return redirect(reverse("sales:freight_wizard") + "?step=1")
        multi_dest = bool(header.get("multi_destination"))

        fs = CargoFormSet(request.POST or None, prefix="cargo")
        # single-dest: sembunyikan field origin/destination pada tiap cargo, set default dari header
        if not multi_dest:
            for f in fs.forms:
                if "origin" in f.fields:
                    f.fields["origin"].widget = djforms.HiddenInput()
                    if header.get("origin"): f.initial["origin"] = header.get("origin")
                if "destination" in f.fields:
                    f.fields["destination"].widget = djforms.HiddenInput()
                    if header.get("destination"): f.initial["destination"] = header.get("destination")

        if request.method == "POST":
            if request.POST.get("_action") == "back":
                return redirect(reverse("sales:freight_wizard") + "?step=1")

            def ok(fs):
                tot=0
                for f in fs:
                    if f.cleaned_data.get("DELETE"): continue
                    if f.cleaned_data.get("description"): tot+=1
                return tot>0

            if fs.is_valid() and ok(fs):
                with transaction.atomic():
                    qf = QuotationFreightForm(header); qf.is_valid()
                    q = qf.save(commit=False); q.business_type="FREIGHT"; q.save()
                    fs.instance = q; cargos = fs.save()

                    # jika single-destination, set O/D cargo dari header
                    if not multi_dest and (header.get("origin") or header.get("destination")):
                        for c in q.cargos.all():
                            changed=False
                            if header.get("origin"): c.origin = header["origin"]; changed=True
                            if header.get("destination"): c.destination = header["destination"]; changed=True
                            if changed: c.save(update_fields=["origin","destination"])

                    request.session.pop(WIZ_FREIGHT_HEADER, None)
                return redirect("sales:quotation_detail", pk=q.pk)

        return render(request, "sales/quotation_wizard.html", {
            "step":2,"mode":"FREIGHT",
            "qform":QuotationFreightForm(initial=header),
            "fs":fs,"common":common,"show_od_in_header":not multi_dest
        })

    return redirect(reverse("sales:freight_wizard") + "?step=1")

# ====== PDF export ======
def quotation_pdf(request, pk, kind="detail"):
    q = get_object_or_404(Quotation.objects.select_related("customer"), pk=pk)
    if q.business_type == "FREIGHT":
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("cargos__charges").first())
    else:
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("legs","charter_charges").first())

    cargo_totals = []
    grand_total = 0
    for c in getattr(q, "cargos", []).all() if hasattr(q, "cargos") else []:
        tot = c.charges.aggregate(s=Sum("amount")).get("s") or 0
        cargo_totals.append((c, tot))
        grand_total += tot

    context = {"q": q, "cargo_totals": cargo_totals, "grand_total": grand_total}

    template = "sales/quotation_pdf_detail.html" if kind.lower() == "detail" else "sales/quotation_pdf_summary.html"
    html = render_to_string(template, context)

    try:
        from weasyprint import HTML
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{q.number}-{kind}.pdf"'
        HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf(response)
        return response
    except Exception:
        # fallback: tampilkan HTML (bisa Ctrl+P simpan PDF)
        return HttpResponse(html)
"""

# ---------- urls.py ----------
urls_py = r"""
from django.urls import path
from . import views
app_name = "sales"
urlpatterns = [
    path("quotations/", views.quotation_list, name="quotation_list"),
    path("quotations/wizard/v3/start/", views.quotation_wizard_v3_start, name="quotation_wizard_v3_start"),
    path("quotations/freight/new/", views.freight_wizard, name="freight_wizard"),
    path("quotations/<int:pk>/", views.quotation_detail, name="quotation_detail"),
    path("quotations/<int:pk>/pdf/<str:kind>/", views.quotation_pdf, name="quotation_pdf"),
]
"""

# ---------- templates ----------
wizard_html = r"""
{% extends "sales/base.html" %}
{% block title %}Quotation Wizard{% endblock %}
{% block content %}
<div class="container my-4" style="max-width: 960px;">
  {% if step == 1 %}
  <form method="post" class="card p-3">
    {% csrf_token %}
    <h5 class="mb-3">Step 1 - Header (Freight)</h5>
    {{ qform.as_p }}
    <div class="alert alert-info py-2">
      {% if show_od_in_header %}
        <small>Single-destination: isi Origin/Destination di header. Di Cargo akan disembunyikan.</small>
      {% else %}
        <small>Multi-destination: Origin/Destination per Cargo. Field di header disembunyikan otomatis.</small>
      {% endif %}
    </div>
    <div class="text-end"><button class="btn btn-primary">Next</button></div>
  </form>
  <script>
  (function(){
    // Sembunyikan O/D header saat multi-destination
    var showOD = {{ show_od_in_header|yesno:"true,false" }};
    if(!showOD){
      var ids=["id_origin","id_destination"];
      ids.forEach(function(id){
        var el=document.getElementById(id);
        if(el){ var grp=el.closest("p, .mb-3, .form-group")||el.parentElement; if(grp) grp.style.display="none"; }
      });
    }
  })();
  </script>
  {% elif step == 2 %}
  <form method="post" class="card p-3">
    {% csrf_token %}
    <h5 class="mb-3">Step 2 - Cargo Lines</h5>
    {{ fs.management_form }}
    {% for f in fs %}
      <div class="border rounded p-2 mb-2">
        {{ f.as_p }}
        <div class="form-check">{{ f.DELETE }} <label class="form-check-label">Delete</label></div>
      </div>
    {% endfor %}
    <div class="d-flex justify-content-between mt-2">
      <button name="_action" value="back" class="btn btn-outline-secondary">Back</button>
      <button class="btn btn-primary">Save</button>
    </div>
  </form>
  <script>
  (function(){
    // Sembunyikan O/D cargo saat single-destination (show_od_in_header = true)
    var hideInCargo = {{ show_od_in_header|yesno:"true,false" }};
    if(hideInCargo){
      document.querySelectorAll("input[id$='-origin'], input[id$='-destination']").forEach(function(el){
        var grp=el.closest("p, .mb-3, .form-group")||el.parentElement; if(grp){grp.style.display="none";}
      });
    }
  })();
  </script>
  {% endif %}
</div>
{% endblock %}
"""

detail_html = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ q.number }} - Detail</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 12px; }
    h1,h2,h3 { margin: 0; }
    table { width:100%; border-collapse: collapse; margin-top: 8px; }
    th, td { border:1px solid #ccc; padding:6px; }
    thead { background:#f5f5f5; }
    .muted { color:#666; }
  </style>
</head>
<body>
  <h2>Quotation {{ q.number }}</h2>
  <div class="muted">{{ q.date }} · Customer: {{ q.customer }} · Currency: {{ q.currency }}</div>
  <div class="muted">Mode: {{ q.transport_mode }} · Service: {{ q.service_option }} · Multi-destination: {{ q.multi_destination }}</div>
  {% if q.origin or q.destination %}
    <div class="muted">Header O/D: {{ q.origin|default:"-" }} → {{ q.destination|default:"-" }}</div>
  {% endif %}
  {% if q.notes %}<p>{{ q.notes }}</p>{% endif %}

  <h3>Cargo & Charges (Detail)</h3>
  {% for c in q.cargos.all %}
    <h4 style="margin-top:12px">{{ c.description }} ({{ c.origin }} → {{ c.destination }})</h4>
    <table>
      <thead><tr><th>Description</th><th style="text-align:right">Qty</th><th style="text-align:right">Rate</th><th style="text-align:right">Amount</th></tr></thead>
      <tbody>
        {% for ch in c.charges.all %}
        <tr>
          <td>{{ ch.description }}</td>
          <td style="text-align:right">{{ ch.qty }}</td>
          <td style="text-align:right">{{ ch.rate }}</td>
          <td style="text-align:right">{{ ch.amount }}</td>
        </tr>
        {% empty %}
        <tr><td colspan="4" class="muted">No charges</td></tr>
        {% endfor %}
      </tbody>
    </table>
  {% endfor %}
</body>
</html>
"""

summary_html = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ q.number }} - Summary</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 12px; }
    h1,h2,h3 { margin: 0; }
    table { width:100%; border-collapse: collapse; margin-top: 8px; }
    th, td { border:1px solid #ccc; padding:6px; }
    thead { background:#f5f5f5; }
    .muted { color:#666; }
  </style>
</head>
<body>
  <h2>Quotation {{ q.number }}</h2>
  <div class="muted">{{ q.date }} · Customer: {{ q.customer }} · Currency: {{ q.currency }}</div>
  <div class="muted">Mode: {{ q.transport_mode }} · Service: {{ q.service_option }} · Multi-destination: {{ q.multi_destination }}</div>
  {% if q.origin or q.destination %}
    <div class="muted">Header O/D: {{ q.origin|default:"-" }} → {{ q.destination|default:"-" }}</div>
  {% endif %}
  {% if q.notes %}<p>{{ q.notes }}</p>{% endif %}

  <h3>Price per Cargo (Summary)</h3>
  <table>
    <thead><tr><th>Cargo</th><th>Origin</th><th>Destination</th><th style="text-align:right">Total</th></tr></thead>
    <tbody>
      {% for c, tot in cargo_totals %}
      <tr>
        <td>{{ c.description }}</td>
        <td>{{ c.origin }}</td>
        <td>{{ c.destination }}</td>
        <td style="text-align:right">{{ tot }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4" class="muted">No cargos</td></tr>
      {% endfor %}
      <tr>
        <td colspan="3" style="text-align:right"><strong>Grand Total</strong></td>
        <td style="text-align:right"><strong>{{ grand_total }}</strong></td>
      </tr>
    </tbody>
  </table>
</body>
</html>
"""

# ---------- write files ----------
models_p = APP / "models.py"
forms_p = APP / "forms.py"
views_p = APP / "views.py"
urls_p = APP / "urls.py"
wiz_tpl = TPL / "quotation_wizard.html"
pdf_detail_tpl = TPL / "quotation_pdf_detail.html"
pdf_summary_tpl = TPL / "quotation_pdf_summary.html"
detail_tpl = TPL / "quotation_detail.html"

for pth, src in [(models_p, models_py),(forms_p, forms_py),(views_p, views_py),(urls_p, urls_py),(wiz_tpl, wizard_html),
                 (pdf_detail_tpl, detail_html),(pdf_summary_tpl, summary_html)]:
    backup(pth); write(pth, src)

# Patch quotation_detail: tambahkan tombol PDF dropdown sederhana
backup(detail_tpl)
if detail_tpl.exists():
    html = detail_tpl.read_text(encoding="utf-8")
    if "Export PDF" not in html:
        inject = """
  <div class="mb-3 d-flex gap-2">
    <a class="btn btn-sm btn-outline-primary" target="_blank" href="{% url 'sales:quotation_pdf' pk=q.pk kind='summary' %}">Export PDF (Summary)</a>
    <a class="btn btn-sm btn-outline-primary" target="_blank" href="{% url 'sales:quotation_pdf' pk=q.pk kind='detail' %}">Export PDF (Detail)</a>
  </div>
"""
        # sisipkan setelah judul
        html = html.replace("<div class=\"text-muted mb-3\"", inject + "\n  <div class=\"text-muted mb-3\"", 1)
        detail_tpl.write_text(html, encoding="utf-8")
        print("• updated", detail_tpl, "(add Export PDF buttons)")
    else:
        print("• keep", detail_tpl, "(PDF buttons already present)")

# ensure migrations package
MIG.mkdir(parents=True, exist_ok=True)
mi = MIG / "__init__.py"
if not mi.exists():
    write(mi, "")

print("\nPatch selesai ✅  Sekarang jalankan:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("\nCek:")
print("  /sales/quotations/wizard/v3/start/")
print("  /sales/quotations/<id>/pdf/summary/  dan  /pdf/detail/")
