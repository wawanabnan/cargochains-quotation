import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari folder project (yang ada manage.py)."

APP = ROOT / "sales"
TPL = APP / "templates" / "sales"
APP.mkdir(exist_ok=True, parents=True)
TPL.mkdir(parents=True, exist_ok=True)

def backup(path: pathlib.Path):
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  • backup {path} -> {bak}")

print("== Rebuild clean sales module ==")

# ------------------------------------------------------------
# utils.py (auto-number, anti-tabrakan)
# ------------------------------------------------------------
utils_py = APP / "utils.py"
backup(utils_py)
utils_py.write_text(
"""from django.utils import timezone

def next_quotation_number(model):
    \"\"\"Generate nomor unik: Q-YYYY-####, cek DB agar tidak bentrok.\"\"\"
    y = timezone.now().year
    prefix = f"Q-{y}-"
    last = (model.objects.filter(number__startswith=prefix)
            .order_by("-number").first())
    if not last:
        seq = 1
    else:
        try:
            seq = int(str(last.number).split("-")[-1]) + 1
        except Exception:
            seq = 1
    while True:
        candidate = f"{prefix}{seq:04d}"
        if not model.objects.filter(number=candidate).exists():
            return candidate
        seq += 1
""",
    encoding="utf-8"
)
print(" ✓ utils.py")

# ------------------------------------------------------------
# models.py
# ------------------------------------------------------------
models_py = APP / "models.py"
backup(models_py)
models_py.write_text(
"""from django.db import models
from django.db.models import Sum
from django.urls import reverse
from .utils import next_quotation_number

class Quotation(models.Model):
    number = models.CharField(max_length=30, unique=True, blank=True)
    date = models.DateField()
    customer = models.ForeignKey("partners.Customer", on_delete=models.PROTECT)
    cargo_desc = models.CharField(max_length=255, blank=True)
    validity_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.number or str(self.number).strip() == "":
            self.number = next_quotation_number(Quotation)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.number or f"Quotation {self.pk}"

    def get_absolute_url(self):
        return reverse("sales:quotation_detail", args=[self.pk])

    @property
    def totals_by_currency(self):
        return (QuotationLine.objects
                .filter(destination__quotation=self)
                .values("currency")
                .annotate(total=Sum("amount"))
                .order_by("currency"))

class QuotationDestination(models.Model):
    quotation = models.ForeignKey(Quotation, related_name="destinations", on_delete=models.CASCADE)
    destination = models.CharField(max_length=100)
    incoterms = models.CharField(max_length=10, blank=True)
    transit_time_days = models.CharField(max_length=30, blank=True)
    schedule = models.CharField(max_length=50, blank=True)
    extra_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.quotation.number} → {self.destination}"

    def totals_by_currency(self):
        return (self.lines.values("currency")
                .annotate(total=Sum("amount"))
                .order_by("currency"))

class QuotationLine(models.Model):
    CHARGE_CHOICES = [
        ("FREIGHT","FREIGHT"),
        ("ORIGIN","ORIGIN"),
        ("DEST","DEST"),
        ("DOC","DOC"),
        ("OTHER","OTHER"),
    ]
    destination = models.ForeignKey(QuotationDestination, related_name="lines", on_delete=models.CASCADE)
    origin = models.CharField(max_length=100, blank=True)  # ⬅ origin per-line (sesuai permintaan)
    charge_type = models.CharField(max_length=20, choices=CHARGE_CHOICES)
    description = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.rate or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.destination} | {self.charge_type} {self.currency} {self.rate}"
""",
    encoding="utf-8"
)
print(" ✓ models.py")

# ------------------------------------------------------------
# forms.py
# ------------------------------------------------------------
forms_py = APP / "forms.py"
backup(forms_py)
forms_py.write_text(
"""from datetime import date, timedelta
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, QuotationDestination, QuotationLine

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["date", "customer", "cargo_desc", "validity_date", "payment_terms", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "validity_date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "customer": forms.Select(attrs={"class":"form-select"}),
            "cargo_desc": forms.TextInput(attrs={"class":"form-control"}),
            "payment_terms": forms.TextInput(attrs={"class":"form-control"}),
            "notes": forms.Textarea(attrs={"class":"form-control","rows":3}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["date"].initial = date.today()
            self.fields["validity_date"].initial = date.today() + timedelta(days=14)

class _DestinationFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = [
            f for f in self.forms
            if not f.cleaned_data.get("DELETE", False)
            and any(f.cleaned_data.get(k)
                    for k in ["destination","incoterms","transit_time_days","schedule","extra_notes"])
        ]
        if len(active) < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal harus ada 1 destination pada quotation ini.")

DestinationFormSet = inlineformset_factory(
    Quotation,
    QuotationDestination,
    formset=_DestinationFormSet,
    fields=["destination","incoterms","transit_time_days","schedule","extra_notes"],
    extra=1,
    can_delete=True
)

class _LineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = 0
        for f in self.forms:
            if f.cleaned_data.get("DELETE", False):
                continue
            if any(f.cleaned_data.get(k) for k in ["origin","charge_type","description","unit","qty","rate","currency"]):
                active += 1
        if active < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal 1 line pada setiap destination.")

LineFormSet = inlineformset_factory(
    QuotationDestination,
    QuotationLine,
    formset=_LineFormSet,
    fields=["origin","charge_type","description","unit","qty","rate","currency"],
    extra=3,
    can_delete=True
)

def LineFormSetFactory():
    return inlineformset_factory(
        QuotationDestination,
        QuotationLine,
        formset=_LineFormSet,
        fields=["origin","charge_type","description","unit","qty","rate","currency"],
        extra=1,
        can_delete=True
    )
""",
    encoding="utf-8"
)
print(" ✓ forms.py")

# ------------------------------------------------------------
# views.py (List, Detail, Single-page Wizard save-once)
# ------------------------------------------------------------
views_py = APP / "views.py"
backup(views_py)
views_py.write_text(
"""from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db import transaction
from .models import Quotation, QuotationDestination
from .forms import QuotationForm, DestinationFormSet, LineFormSetFactory

class QuotationListView(ListView):
    model = Quotation
    template_name = "sales/quotation_list.html"
    context_object_name = "quotations"
    paginate_by = 20
    ordering = ["-date","-id"]

class QuotationDetailView(DetailView):
    model = Quotation
    template_name = "sales/quotation_detail.html"
    context_object_name = "quotation"

# Single-page wizard (header + destinations + lines), simpan sekali
def quotation_wizard(request):
    if request.method == "POST":
        header_form = QuotationForm(request.POST)
        dest_formset = DestinationFormSet(request.POST, prefix="dest")
        # siapkan line formsets per index dest (tanpa instance dulu)
        LFSF = LineFormSetFactory()
        total_dest = int(request.POST.get("dest-TOTAL_FORMS", "0") or "0")
        line_formsets = []
        for i in range(total_dest):
            if request.POST.get(f"dest-{i}-DELETE") == "on":
                continue
            fs = LFSF(data=request.POST, prefix=f"line-{i}", instance=None)
            line_formsets.append((i, fs))

        valid = header_form.is_valid() and dest_formset.is_valid() and all(fs.is_valid() for _, fs in line_formsets)

        # validasi bisnis: min satu dest & tiap dest min 1 line
        from django.core.exceptions import ValidationError
        active_dest_indices = []
        for i in range(total_dest):
            if request.POST.get(f"dest-{i}-DELETE") == "on":
                continue
            if any(request.POST.get(f"dest-{i}-{k}", "").strip() for k in ["destination","incoterms","transit_time_days","schedule","extra_notes"]):
                active_dest_indices.append(i)

        if len(active_dest_indices) < 1:
            header_form.add_error(None, ValidationError("Minimal harus ada 1 destination."))
            valid = False

        for i, fs in line_formsets:
            active_lines = 0
            for form in fs.forms:
                if form.cleaned_data.get("DELETE", False):
                    continue
                if any(form.cleaned_data.get(k) for k in ["origin","charge_type","description","unit","qty","rate","currency"]):
                    active_lines += 1
            if active_lines < 1:
                fs._non_form_errors = ["Minimal 1 line untuk destination ke-%s." % (i+1)]
                valid = False

        if not valid:
            return render(request, "sales/quotation_wizard.html", {
                "header_form": header_form,
                "dest_formset": dest_formset,
                "line_formsets": line_formsets,
                "line_prefix_base": "line",
            })

        with transaction.atomic():
            q = header_form.save(commit=False)
            q.save()
            saved = []
            for i in range(total_dest):
                if request.POST.get(f"dest-{i}-DELETE") == "on":
                    continue
                if not any(request.POST.get(f"dest-{i}-{k}", "").strip() for k in ["destination","incoterms","transit_time_days","schedule","extra_notes"]):
                    continue
                d = QuotationDestination(
                    quotation=q,
                    destination=request.POST.get(f"dest-{i}-destination","").strip(),
                    incoterms=request.POST.get(f"dest-{i}-incoterms","").strip(),
                    transit_time_days=request.POST.get(f"dest-{i}-transit_time_days","").strip(),
                    schedule=request.POST.get(f"dest-{i}-schedule","").strip(),
                    extra_notes=request.POST.get(f"dest-{i}-extra_notes","").strip(),
                )
                d.save()
                saved.append((i, d))

            # simpan line untuk setiap destination yang tersimpan
            from .models import QuotationLine
            for i, d in saved:
                LFSF2 = LineFormSetFactory()
                fs = LFSF2(data=request.POST, prefix=f"line-{i}", instance=d)
                if fs.is_valid():
                    fs.save()
                else:
                    raise ValidationError("Data lines invalid pada destination ke-%s." % (i+1))

        return redirect("sales:quotation_detail", pk=q.pk)

    # GET
    header_form = QuotationForm()
    dest_formset = DestinationFormSet(prefix="dest")
    return render(request, "sales/quotation_wizard.html", {
        "header_form": header_form,
        "dest_formset": dest_formset,
        "line_prefix_base": "line",
    })
""",
    encoding="utf-8"
)
print(" ✓ views.py")

# ------------------------------------------------------------
# urls.py
# ------------------------------------------------------------
urls_py = APP / "urls.py"
backup(urls_py)
urls_py.write_text(
"""from django.urls import path
from .views import QuotationListView, QuotationDetailView, quotation_wizard

app_name = "sales"

urlpatterns = [
    path("quotations/", QuotationListView.as_view(), name="quotation_list"),
    path("quotations/<int:pk>/", QuotationDetailView.as_view(), name="quotation_detail"),
    path("quotations/wizard/new/", quotation_wizard, name="quotation_wizard"),
]
""",
    encoding="utf-8"
)
print(" ✓ urls.py")

# ------------------------------------------------------------
# admin.py (opsional, biar gampang cek data)
# ------------------------------------------------------------
admin_py = APP / "admin.py"
backup(admin_py)
admin_py.write_text(
"""from django.contrib import admin
from .models import Quotation, QuotationDestination, QuotationLine

class QuotationLineInline(admin.TabularInline):
    model = QuotationLine
    extra = 0

class QuotationDestinationAdmin(admin.ModelAdmin):
    inlines = [QuotationLineInline]
    list_display = ("quotation","destination","incoterms","transit_time_days","schedule")

class QuotationAdmin(admin.ModelAdmin):
    list_display = ("number","date","customer","validity_date")
    search_fields = ("number","customer__name")

admin.site.register(Quotation, QuotationAdmin)
admin.site.register(QuotationDestination, QuotationDestinationAdmin)
""",
    encoding="utf-8"
)
print(" ✓ admin.py")

# ------------------------------------------------------------
# Templates
# ------------------------------------------------------------

# list
tpl_list = TPL / "quotation_list.html"
backup(tpl_list)
tpl_list.write_text(
"""{% extends "base.html" %}
{% block title %}Quotations{% endblock %}
{% block content %}
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">Quotations</h2>
    <a class="btn btn-primary" href="{% url 'sales:quotation_wizard' %}">New Quotation (Wizard)</a>
  </div>
  <div class="card">
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr><th>No</th><th>Date</th><th>Customer</th><th>Validity</th><th></th></tr>
        </thead>
        <tbody>
          {% for q in quotations %}
          <tr>
            <td>{{ q.number }}</td>
            <td>{{ q.date }}</td>
            <td>{{ q.customer }}</td>
            <td>{{ q.validity_date|default:"-" }}</td>
            <td class="text-end">
              <a class="btn btn-sm btn-outline-secondary" href="{% url 'sales:quotation_detail' q.pk %}">Open</a>
            </td>
          </tr>
          {% empty %}
          <tr><td colspan="5" class="text-center text-body-secondary py-4">No data</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}
""",
    encoding="utf-8"
)
print(" ✓ template: quotation_list.html")

# detail
tpl_detail = TPL / "quotation_detail.html"
backup(tpl_detail)
tpl_detail.write_text(
"""{% extends "base.html" %}
{% load humanize %}
{% block title %}Quotation {{ quotation.number }}{% endblock %}
{% block content %}
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">Quotation {{ quotation.number }}</h2>
    <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_list' %}">Back</a>
  </div>

  <div class="card shadow-sm rounded-2xl mb-4">
    <div class="card-header d-flex justify-content-between align-items-center">
      <h3 class="card-title">Header</h3>
      <span class="text-body-secondary">Date: {{ quotation.date }}</span>
    </div>
    <div class="card-body">
      <div class="row g-3">
        <div class="col-md-4">
          <div class="border p-3 rounded bg-body-tertiary">
            <div class="fw-bold mb-2">Customer</div>
            <div>{{ quotation.customer }}</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="border p-3 rounded bg-body-tertiary">
            <div class="fw-bold mb-2">Validity</div>
            <div>{{ quotation.validity_date|default:"-" }}</div>
            <div class="fw-bold mt-2">Payment Terms</div>
            <div>{{ quotation.payment_terms|default:"-" }}</div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="border p-3 rounded bg-body-tertiary">
            <div class="fw-bold mb-2">Cargo</div>
            <div>{{ quotation.cargo_desc|default:"-" }}</div>
          </div>
        </div>
      </div>
      {% if quotation.notes %}
      <hr class="my-3">
      <div>
        <div class="fw-bold">Global Notes</div>
        <div class="text-pre-wrap">{{ quotation.notes }}</div>
      </div>
      {% endif %}
    </div>
  </div>

  {% for dest in quotation.destinations.all %}
  <div class="card mb-4 border-0 shadow-sm">
    <div class="card-header bg-body-secondary">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <span class="badge text-bg-dark me-2">{{ forloop.counter }}</span>
          <strong>{{ dest.destination }}</strong>
        </div>
        <div class="text-body-secondary small">
          Incoterms: {{ dest.incoterms|default:"-" }} •
          Transit: {{ dest.transit_time_days|default:"-" }} •
          Schedule: {{ dest.schedule|default:"-" }}
        </div>
      </div>
    </div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-hover mb-0 align-middle">
          <thead class="table-light">
            <tr>
              <th style="width:60px;">No</th>
              <th>Origin</th>
              <th>Charge Type</th>
              <th>Description</th>
              <th>Unit</th>
              <th class="text-end">Qty</th>
              <th class="text-end">Rate</th>
              <th class="text-center">Curr</th>
              <th class="text-end">Amount</th>
            </tr>
          </thead>
          <tbody>
            {% for line in dest.lines.all %}
            <tr>
              <td>{{ forloop.counter }}</td>
              <td>{{ line.origin }}</td>
              <td><span class="badge text-bg-secondary">{{ line.charge_type }}</span></td>
              <td>{{ line.description }}</td>
              <td>{{ line.unit }}</td>
              <td class="text-end">{{ line.qty|floatformat:3 }}</td>
              <td class="text-end">{{ line.rate|floatformat:2 }}</td>
              <td class="text-center">{{ line.currency }}</td>
              <td class="text-end">{{ line.amount|floatformat:2 }}</td>
            </tr>
            {% empty %}
            <tr><td colspan="9" class="text-center text-body-secondary py-3">No lines</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="p-3 pt-0">
        <div class="fw-bold">Subtotal {{ dest.destination }} (per currency)</div>
        <ul class="list-unstyled mb-0">
          {% for row in dest.totals_by_currency %}
            <li>{{ row.currency }}: <strong>{{ row.total|floatformat:2 }}</strong></li>
          {% empty %}
            <li class="text-body-secondary">No totals.</li>
          {% endfor %}
        </ul>
        {% if dest.extra_notes %}
          <div class="text-body-secondary mt-2"><em>{{ dest.extra_notes }}</em></div>
        {% endif %}
      </div>
    </div>
  </div>
  {% empty %}
    <div class="alert alert-secondary">No destinations.</div>
  {% endfor %}

  <div class="border-top pt-3">
    <div class="fw-bold mb-2">Grand Total (per currency)</div>
    <ul class="list-unstyled mb-0">
      {% for row in quotation.totals_by_currency %}
        <li>{{ row.currency }}: <strong>{{ row.total|floatformat:2 }}</strong></li>
      {% empty %}
        <li class="text-body-secondary">No totals.</li>
      {% endfor %}
    </ul>
  </div>
</div>
{% endblock %}
""",
    encoding="utf-8"
)
print(" ✓ template: quotation_detail.html")

# wizard (single-page) with simple JS add rows
tpl_wizard = TPL / "quotation_wizard.html"
backup(tpl_wizard)
tpl_wizard.write_text(
"""{% extends "base.html" %}
{% block title %}New Quotation (Wizard){% endblock %}
{% block content %}
<div class="container-fluid">
  <form method="post" id="wizard-form" novalidate>
    {% csrf_token %}

    <!-- STEP 1 -->
    <div class="card shadow-sm mb-3 step" id="step-1">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 1/3 — Header</h3>
        <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_list' %}">Back</a>
      </div>
      <div class="card-body">
        <div class="row g-3">
          <div class="col-md-4">
            <label class="form-label">Date</label>
            {{ header_form.date }}
          </div>
          <div class="col-md-4">
            <label class="form-label">Validity Date</label>
            {{ header_form.validity_date }}
          </div>
          <div class="col-md-4">
            <label class="form-label">Customer</label>
            {{ header_form.customer }}
          </div>
          <div class="col-md-6">
            <label class="form-label">Cargo Description</label>
            {{ header_form.cargo_desc }}
          </div>
          <div class="col-md-6">
            <label class="form-label">Payment Terms</label>
            {{ header_form.payment_terms }}
          </div>
          <div class="col-12">
            <label class="form-label">Notes</label>
            {{ header_form.notes }}
          </div>
        </div>
        {% if header_form.non_field_errors %}
        <div class="alert alert-danger mt-3">
          {% for e in header_form.non_field_errors %}<div>{{ e }}</div>{% endfor %}
        </div>
        {% endif %}
      </div>
      <div class="card-footer d-flex justify-content-end">
        <button class="btn btn-primary" type="button" onclick="goStep(2)">Next</button>
      </div>
    </div>

    <!-- STEP 2 -->
    <div class="card shadow-sm mb-3 step d-none" id="step-2">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 2/3 — Destinations</h3>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary" type="button" onclick="goStep(1)">Back</button>
          <button class="btn btn-primary" type="button" onclick="goStep(3)">Next</button>
        </div>
      </div>
      <div class="card-body">
        {{ dest_formset.management_form }}
        <div class="table-responsive">
          <table class="table align-middle">
            <thead class="table-light">
              <tr>
                <th>Destination</th><th>Incoterms</th><th>Transit</th><th>Schedule</th><th>Notes</th><th>Delete</th>
              </tr>
            </thead>
            <tbody id="dest-tbody">
              {% for f in dest_formset %}
              <tr class="dest-row">
                <td>{{ f.destination }}</td>
                <td>{{ f.incoterms }}</td>
                <td>{{ f.transit_time_days }}</td>
                <td>{{ f.schedule }}</td>
                <td>{{ f.extra_notes }}</td>
                <td>{{ f.DELETE }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
        <button type="button" class="btn btn-outline-primary" onclick="addDest()">+ Add Destination</button>

        {% if dest_formset.non_form_errors %}
        <div class="alert alert-danger mt-3">
          {% for e in dest_formset.non_form_errors %}<div>{{ e }}</div>{% endfor %}
        </div>
        {% endif %}
      </div>
      <div class="card-footer d-flex justify-content-end">
        <button class="btn btn-primary" type="button" onclick="goStep(3)">Next</button>
      </div>
    </div>

    <!-- STEP 3 -->
    <div class="card shadow-sm step d-none" id="step-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 3/3 — Lines per Destination</h3>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary" type="button" onclick="goStep(2)">Back</button>
          <button class="btn btn-success" type="submit">Save Final</button>
        </div>
      </div>
      <div class="card-body" id="lines-container">
        {% if line_formsets %}
          {% for idx, fs in line_formsets %}
          <div class="border rounded p-3 mb-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <div class="fw-bold">Destination #{{ forloop.counter }}</div>
              <button type="button" class="btn btn-sm btn-outline-primary" onclick="addLine('{{ fs.prefix }}')">+ Add Line</button>
            </div>
            {{ fs.management_form }}
            <div class="table-responsive">
              <table class="table align-middle">
                <thead class="table-light">
                  <tr>
                    <th>Origin</th><th>Charge</th><th>Description</th><th>Unit</th>
                    <th class="text-end">Qty</th><th class="text-end">Rate</th><th>Curr</th><th>Delete</th>
                  </tr>
                </thead>
                <tbody id="{{ fs.prefix }}-tbody">
                  {% for lf in fs %}
                  <tr>
                    <td>{{ lf.origin }}</td>
                    <td>{{ lf.charge_type }}</td>
                    <td>{{ lf.description }}</td>
                    <td>{{ lf.unit }}</td>
                    <td class="text-end">{{ lf.qty }}</td>
                    <td class="text-end">{{ lf.rate }}</td>
                    <td>{{ lf.currency }}</td>
                    <td>{{ lf.DELETE }}</td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            {% if fs._non_form_errors %}
            <div class="alert alert-danger">
              {% for e in fs._non_form_errors %}<div>{{ e }}</div>{% endfor %}
            </div>
            {% endif %}
          </div>
          {% endfor %}
        {% else %}
          <div class="alert alert-info">Tambahkan destinasi dulu di Step 2, lalu klik Next untuk membuat lines per destination.</div>
        {% endif %}
      </div>
      <div class="card-footer d-flex justify-content-end">
        <button class="btn btn-success" type="submit">Save Final</button>
      </div>
    </div>

  </form>
</div>

<template id="dest-empty">
  <tr class="dest-row">
    <td><input name="__NAME__-destination" class="form-control"></td>
    <td><input name="__NAME__-incoterms" class="form-control"></td>
    <td><input name="__NAME__-transit_time_days" class="form-control"></td>
    <td><input name="__NAME__-schedule" class="form-control"></td>
    <td><input name="__NAME__-extra_notes" class="form-control"></td>
    <td><input type="checkbox" name="__NAME__-DELETE" class="form-check-input"></td>
  </tr>
</template>

<template id="line-empty">
  <tr>
    <td><input name="__PFX__-__IDX__-origin" class="form-control" placeholder="Jakarta"></td>
    <td>
      <select name="__PFX__-__IDX__-charge_type" class="form-select">
        <option value="">-</option>
        <option value="FREIGHT">FREIGHT</option>
        <option value="ORIGIN">ORIGIN</option>
        <option value="DEST">DEST</option>
        <option value="DOC">DOC</option>
        <option value="OTHER">OTHER</option>
      </select>
    </td>
    <td><input name="__PFX__-__IDX__-description" class="form-control"></td>
    <td><input name="__PFX__-__IDX__-unit" class="form-control" placeholder="per CBM / per KG / per SHPT"></td>
    <td><input type="number" step="0.001" name="__PFX__-__IDX__-qty" class="form-control text-end" value="1"></td>
    <td><input type="number" step="0.0001" name="__PFX__-__IDX__-rate" class="form-control text-end"></td>
    <td><input name="__PFX__-__IDX__-currency" class="form-control" value="USD"></td>
    <td><input type="checkbox" name="__PFX__-__IDX__-DELETE" class="form-check-input"></td>
  </tr>
</template>

<script>
  function goStep(n){
    document.querySelectorAll('.step').forEach(s=>s.classList.add('d-none'));
    document.getElementById('step-'+n).classList.remove('d-none');
    if(n===3){ ensureLineBlocks(); }
  }
  function addDest(){
    const totalInput = document.querySelector('input[name="dest-TOTAL_FORMS"]');
    let total = parseInt(totalInput.value || '0');
    const tpl = document.getElementById('dest-empty').content.cloneNode(true);
    tpl.querySelectorAll('[name]').forEach(inp=>{
      inp.name = inp.name.replace('__NAME__', `dest-${total}`);
    });
    document.getElementById('dest-tbody').appendChild(tpl);
    totalInput.value = total + 1;
  }
  function ensureLineBlocks(){
    const container = document.getElementById('lines-container');
    if(container.querySelector('[id$="-tbody"]')) return;
    const total = parseInt(document.querySelector('input[name="dest-TOTAL_FORMS"]').value || '0');
    for(let i=0;i<total;i++){
      const del = document.querySelector(`input[name="dest-${i}-DELETE"]`);
      if(del && del.checked) continue;
      const wrap = document.createElement('div');
      wrap.className = 'border rounded p-3 mb-3';
      const prefix = `line-${i}`;
      const head = document.createElement('div');
      head.className = 'd-flex justify-content-between align-items-center mb-2';
      head.innerHTML = `<div class="fw-bold">Destination #${i+1}</div>
        <button type="button" class="btn btn-sm btn-outline-primary" onclick="addLine('${prefix}')">+ Add Line</button>`;
      wrap.appendChild(head);
      wrap.insertAdjacentHTML('beforeend', `
        <input type="hidden" name="${prefix}-TOTAL_FORMS" value="1">
        <input type="hidden" name="${prefix}-INITIAL_FORMS" value="0">
        <input type="hidden" name="${prefix}-MIN_NUM_FORMS" value="0">
        <input type="hidden" name="${prefix}-MAX_NUM_FORMS" value="1000">
      `);
      const table = document.createElement('div');
      table.className = 'table-responsive';
      table.innerHTML = `<table class="table align-middle">
        <thead class="table-light">
          <tr>
            <th>Origin</th><th>Charge</th><th>Description</th><th>Unit</th>
            <th class="text-end">Qty</th><th class="text-end">Rate</th><th>Curr</th><th>Delete</th>
          </tr>
        </thead>
        <tbody id="${prefix}-tbody"></tbody>
      </table>`;
      wrap.appendChild(table);
      container.appendChild(wrap);
      addLine(prefix);
    }
  }
  function addLine(prefix){
    const tbody = document.getElementById(`${prefix}-tbody`);
    const totalInput = document.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);
    let idx = parseInt(totalInput.value || '0');
    const tpl = document.getElementById('line-empty').content.cloneNode(true);
    tpl.querySelectorAll('[name]').forEach(el=>{
      el.name = el.name.replace('__PFX__', prefix).replace('__IDX__', idx);
    });
    tbody.appendChild(tpl);
    totalInput.value = idx + 1;
  }
</script>
{% endblock %}
""",
    encoding="utf-8"
)
print(" ✓ template: quotation_wizard.html")

print("\nDone ✅")
print("Next steps:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("  python manage.py runserver")
