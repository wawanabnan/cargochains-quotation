import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari root project (yang ada manage.py)."

APP = ROOT / "sales"
TPL = APP / "templates" / "sales"
APP.mkdir(exist_ok=True, parents=True)
TPL.mkdir(parents=True, exist_ok=True)

def backup(p: pathlib.Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  • backup {p} -> {b}")

print("== Rebuild sales module (Quotation → Cargo → CargoCharge) ==")

# ---------------- utils.py ----------------
utils_py = APP / "utils.py"
backup(utils_py)
utils_py.write_text(
"""from django.utils import timezone

def next_quotation_number(model):
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
        cand = f"{prefix}{seq:04d}"
        if not model.objects.filter(number=cand).exists():
            return cand
        seq += 1
""", encoding="utf-8")
print(" ✓ utils.py")

# ---------------- models.py ----------------
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
    validity_date = models.DateField(null=True, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    notes = models.TextualField if hasattr(models, "TextualField") else models.TextField  # guard untuk IDE
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
        return (CargoCharge.objects
                .filter(cargo__quotation=self)
                .values("currency")
                .annotate(total=Sum("amount"))
                .order_by("currency"))

class Cargo(models.Model):
    quotation = models.ForeignKey(Quotation, related_name="cargos", on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    package_type = models.CharField(max_length=50, blank=True)   # CTN/PLT/BAG/LOOSE
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    extra_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.description} ({self.origin} → {self.destination})"

    def totals_by_currency(self):
        return (self.charges.values("currency")
                .annotate(total=Sum("amount"))
                .order_by("currency"))

class CargoCharge(models.Model):
    CHARGE_CHOICES = [
        ("FREIGHT","FREIGHT"),
        ("ORIGIN","ORIGIN"),
        ("DEST","DEST"),
        ("DOC","DOC"),
        ("OTHER","OTHER"),
    ]
    cargo = models.ForeignKey(Cargo, related_name="charges", on_delete=models.CASCADE)
    charge_type = models.CharField(max_length=20, choices=CHARGE_CHOICES)
    description = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=30, blank=True)           # e.g. per CBM, per KG
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    currency = models.CharField(max_length=3, default="USD")
    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)

    def save(self, *args, **kwargs):
        self.amount = (self.qty or 0) * (self.rate or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cargo} | {self.charge_type} {self.currency} {self.rate}"
""", encoding="utf-8")
print(" ✓ models.py")

# ---------------- forms.py ----------------
forms_py = APP / "forms.py"
backup(forms_py)
forms_py.write_text(
"""from datetime import date, timedelta
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, Cargo, CargoCharge

# ---- Header (Quotation) ----
class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["date","customer","validity_date","payment_terms","notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "validity_date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "customer": forms.Select(attrs={"class":"form-select"}),
            "payment_terms": forms.TextInput(attrs={"class":"form-control"}),
            "notes": forms.Textarea(attrs={"class":"form-control","rows":3}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["date"].initial = date.today()
            self.fields["validity_date"].initial = date.today() + timedelta(days=14)

# ---- Cargo FormSet (min 1 cargo) ----
class _CargoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = [
            f for f in self.forms
            if not f.cleaned_data.get("DELETE", False)
            and any(
                f.cleaned_data.get(k)
                for k in ["description","origin","destination","qty","weight_kg","volume_cbm","package_type"]
            )
        ]
        if len(active) < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal harus ada 1 cargo di quotation ini.")

CargoFormSet = inlineformset_factory(
    Quotation, Cargo,
    formset=_CargoFormSet,
    fields=["description","package_type","qty","weight_kg","volume_cbm","origin","destination","extra_notes"],
    extra=1, can_delete=True
)

# ---- Charge FormSet (min 1 charge per cargo) ----
class _ChargeFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = 0
        for f in self.forms:
            if f.cleaned_data.get("DELETE", False):
                continue
            if any(f.cleaned_data.get(k) for k in ["charge_type","description","unit","qty","rate","currency"]):
                active += 1
        if active < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal 1 charge untuk setiap cargo.")

ChargeFormSet = inlineformset_factory(
    Cargo, CargoCharge,
    formset=_ChargeFormSet,
    fields=["charge_type","description","unit","qty","rate","currency"],
    extra=3, can_delete=True
)

def ChargeFormSetFactory():
    return inlineformset_factory(
        Cargo, CargoCharge,
        formset=_ChargeFormSet,
        fields=["charge_type","description","unit","qty","rate","currency"],
        extra=1, can_delete=True
    )
""", encoding="utf-8")
print(" ✓ forms.py")

# ---------------- views.py ----------------
views_py = APP / "views.py"
backup(views_py)
views_py.write_text(
"""from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView
from django.db import transaction
from django.forms.utils import ErrorList
from .models import Quotation, Cargo
from .forms import QuotationForm, CargoFormSet, ChargeFormSetFactory

class QuotationListView(ListView):
    model = Quotation
    template_name = "sales/quotation_list.html"
    context_object_name = "quotations"
    ordering = ["-date","-id"]
    paginate_by = 20

class QuotationDetailView(DetailView):
    model = Quotation
    template_name = "sales/quotation_detail.html"
    context_object_name = "quotation"

# Wizard 1-halaman: Header → Cargo(s) → Charges per Cargo (save once)
def quotation_wizard(request):
    if request.method == "POST":
        header_form = QuotationForm(request.POST)
        cargo_formset = CargoFormSet(request.POST, prefix="cargo")

        # kumpulkan charge formset per cargo index
        CFSF = ChargeFormSetFactory()
        total_cargo = int(request.POST.get("cargo-TOTAL_FORMS", "0") or "0")
        charge_formsets = []
        for i in range(total_cargo):
            if request.POST.get(f"cargo-{i}-DELETE") == "on":
                continue
            fs = CFSF(data=request.POST, prefix=f"chg-{i}", instance=None)
            charge_formsets.append((i, fs))

        valid = header_form.is_valid() and cargo_formset.is_valid() and all(fs.is_valid() for _, fs in charge_formsets)

        # Validasi bisnis: min 1 cargo
        from django.core.exceptions import ValidationError
        active_cargo_idx = []
        for i in range(total_cargo):
            if request.POST.get(f"cargo-{i}-DELETE") == "on":
                continue
            if any(request.POST.get(f"cargo-{i}-{k}", "").strip()
                   for k in ["description","package_type","qty","weight_kg","volume_cbm","origin","destination","extra_notes"]):
                active_cargo_idx.append(i)
        if len(active_cargo_idx) < 1:
            header_form.add_error(None, ValidationError("Minimal harus ada 1 cargo."))
            valid = False

        # tiap cargo min 1 charge
        for i, fs in charge_formsets:
            active_lines = 0
            for form in fs.forms:
                if form.cleaned_data.get("DELETE", False):
                    continue
                if any(form.cleaned_data.get(k) for k in ["charge_type","description","unit","qty","rate","currency"]):
                    active_lines += 1
            if active_lines < 1:
                fs._non_form_errors = ErrorList([f"Minimal 1 charge untuk cargo ke-{i+1}."])
                valid = False

        if not valid:
            return render(request, "sales/quotation_wizard.html", {
                "header_form": header_form,
                "cargo_formset": cargo_formset,
                "charge_formsets": charge_formsets,
            })

        with transaction.atomic():
            q = header_form.save(commit=False)
            q.save()

            saved = []
            for i in range(total_cargo):
                if request.POST.get(f"cargo-{i}-DELETE") == "on":
                    continue
                if not any(request.POST.get(f"cargo-{i}-{k}", "").strip()
                           for k in ["description","package_type","qty","weight_kg","volume_cbm","origin","destination","extra_notes"]):
                    continue
                c = Cargo(
                    quotation=q,
                    description=request.POST.get(f"cargo-{i}-description","").strip(),
                    package_type=request.POST.get(f"cargo-{i}-package_type","").strip(),
                    qty=request.POST.get(f"cargo-{i}-qty","") or 0,
                    weight_kg=request.POST.get(f"cargo-{i}-weight_kg","") or 0,
                    volume_cbm=request.POST.get(f"cargo-{i}-volume_cbm","") or 0,
                    origin=request.POST.get(f"cargo-{i}-origin","").strip(),
                    destination=request.POST.get(f"cargo-{i}-destination","").strip(),
                    extra_notes=request.POST.get(f"cargo-{i}-extra_notes","").strip(),
                )
                c.save()
                saved.append((i, c))

            # save charges
            for i, c in saved:
                CFSF2 = ChargeFormSetFactory()
                fs = CFSF2(data=request.POST, prefix=f"chg-{i}", instance=c)
                if fs.is_valid():
                    fs.save()
                else:
                    raise ValidationError(f"Data charges invalid pada cargo ke-{i+1}.")

        return redirect("sales:quotation_detail", pk=q.pk)

    # GET
    header_form = QuotationForm()
    cargo_formset = CargoFormSet(prefix="cargo")
    return render(request, "sales/quotation_wizard.html", {
        "header_form": header_form,
        "cargo_formset": cargo_formset,
    })
""", encoding="utf-8")
print(" ✓ views.py")

# ---------------- urls.py ----------------
urls_py = APP / "urls.py"
backup(urls_py)
urls_py.write_text(
"""from django.urls import path
from django.views.generic.base import RedirectView
from .views import QuotationListView, QuotationDetailView, quotation_wizard

app_name = "sales"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="sales:quotation_list", permanent=False), name="sales_index"),
    path("quotations/", QuotationListView.as_view(), name="quotation_list"),
    path("quotations/<int:pk>/", QuotationDetailView.as_view(), name="quotation_detail"),
    path("quotations/wizard/new/", quotation_wizard, name="quotation_wizard"),
]
""", encoding="utf-8")
print(" ✓ urls.py")

# ---------------- admin.py ----------------
admin_py = APP / "admin.py"
backup(admin_py)
admin_py.write_text(
"""from django.contrib import admin
from .models import Quotation, Cargo, CargoCharge

class CargoChargeInline(admin.TabularInline):
    model = CargoCharge
    extra = 0

class CargoAdmin(admin.ModelAdmin):
    list_display = ("quotation","description","origin","destination","qty","weight_kg","volume_cbm")
    inlines = [CargoChargeInline]

class QuotationAdmin(admin.ModelAdmin):
    list_display = ("number","date","customer","validity_date")
    search_fields = ("number","customer__name")

admin.site.register(Quotation, QuotationAdmin)
admin.site.register(Cargo, CargoAdmin)
""", encoding="utf-8")
print(" ✓ admin.py")

# ---------------- templates: list ----------------
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
""", encoding="utf-8")
print(" ✓ template: quotation_list.html")

# ---------------- templates: detail ----------------
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
          {% if quotation.notes %}
          <div class="border p-3 rounded bg-body-tertiary">
            <div class="fw-bold mb-2">Notes</div>
            <div class="text-pre-wrap">{{ quotation.notes }}</div>
          </div>
          {% endif %}
        </div>
      </div>
    </div>
  </div>

  {% for cargo in quotation.cargos.all %}
  <div class="card mb-4 border-0 shadow-sm">
    <div class="card-header bg-body-secondary">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <span class="badge text-bg-dark me-2">{{ forloop.counter }}</span>
          <strong>{{ cargo.description }}</strong>
          <span class="text-body-secondary">({{ cargo.origin }} → {{ cargo.destination }})</span>
        </div>
        <div class="text-body-secondary small">
          {% if cargo.package_type %}{{ cargo.package_type }} • {% endif %}
          {% if cargo.qty %}Qty: {{ cargo.qty|floatformat:3 }} • {% endif %}
          {% if cargo.weight_kg %}Wt: {{ cargo.weight_kg|floatformat:3 }} kg • {% endif %}
          {% if cargo.volume_cbm %}Vol: {{ cargo.volume_cbm|floatformat:3 }} cbm{% endif %}
        </div>
      </div>
    </div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-hover mb-0 align-middle">
          <thead class="table-light">
            <tr>
              <th style="width:60px;">No</th>
              <th>Charge</th>
              <th>Description</th>
              <th>Unit</th>
              <th class="text-end">Qty</th>
              <th class="text-end">Rate</th>
              <th class="text-center">Curr</th>
              <th class="text-end">Amount</th>
            </tr>
          </thead>
          <tbody>
            {% for line in cargo.charges.all %}
            <tr>
              <td>{{ forloop.counter }}</td>
              <td><span class="badge text-bg-secondary">{{ line.charge_type }}</span></td>
              <td>{{ line.description }}</td>
              <td>{{ line.unit }}</td>
              <td class="text-end">{{ line.qty|floatformat:3 }}</td>
              <td class="text-end">{{ line.rate|floatformat:2 }}</td>
              <td class="text-center">{{ line.currency }}</td>
              <td class="text-end">{{ line.amount|floatformat:2 }}</td>
            </tr>
            {% empty %}
            <tr><td colspan="8" class="text-center text-body-secondary py-3">No charges</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <div class="p-3 pt-0">
        <div class="fw-bold">Subtotal cargo (per currency)</div>
        <ul class="list-unstyled mb-0">
          {% for row in cargo.totals_by_currency %}
            <li>{{ row.currency }}: <strong>{{ row.total|floatformat:2 }}</strong></li>
          {% empty %}
            <li class="text-body-secondary">No totals.</li>
          {% endfor %}
        </ul>
        {% if cargo.extra_notes %}
          <div class="text-body-secondary mt-2"><em>{{ cargo.extra_notes }}</em></div>
        {% endif %}
      </div>
    </div>
  </div>
  {% empty %}
    <div class="alert alert-secondary">No cargo added.</div>
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
""", encoding="utf-8")
print(" ✓ template: quotation_detail.html")

# ---------------- templates: wizard (header → cargo → charges) ----------------
tpl_wizard = TPL / "quotation_wizard.html"
backup(tpl_wizard)
tpl_wizard.write_text(
"""{% extends "base.html" %}
{% block title %}New Quotation (Wizard){% endblock %}
{% block content %}
<div class="container-fluid">
  <form method="post" id="wizard-form" novalidate>
    {% csrf_token %}

    <!-- STEP 1: HEADER -->
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
            <label class="form-label">Payment Terms</label>
            {{ header_form.payment_terms }}
          </div>
          <div class="col-md-6">
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

    <!-- STEP 2: CARGOS -->
    <div class="card shadow-sm mb-3 step d-none" id="step-2">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 2/3 — Cargo(s)</h3>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary" type="button" onclick="goStep(1)">Back</button>
          <button class="btn btn-primary" type="button" onclick="goStep(3)">Next</button>
        </div>
      </div>
      <div class="card-body">
        {{ cargo_formset.management_form }}
        <div class="table-responsive">
          <table class="table align-middle">
            <thead class="table-light">
              <tr>
                <th>Description</th><th>Pkg</th><th class="text-end">Qty</th>
                <th class="text-end">Wt(kg)</th><th class="text-end">Vol(cb m)</th>
                <th>Origin</th><th>Destination</th><th>Notes</th><th>Delete</th>
              </tr>
            </thead>
            <tbody id="cargo-tbody">
              {% for f in cargo_formset %}
              <tr class="cargo-row">
                <td>{{ f.description }}</td>
                <td>{{ f.package_type }}</td>
                <td class="text-end">{{ f.qty }}</td>
                <td class="text-end">{{ f.weight_kg }}</td>
                <td class="text-end">{{ f.volume_cbm }}</td>
                <td>{{ f.origin }}</td>
                <td>{{ f.destination }}</td>
                <td>{{ f.extra_notes }}</td>
                <td>{{ f.DELETE }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
        <button type="button" class="btn btn-outline-primary" onclick="addCargo()">+ Add Cargo</button>

        {% if cargo_formset.non_form_errors %}
        <div class="alert alert-danger mt-3">
          {% for e in cargo_formset.non_form_errors %}<div>{{ e }}</div>{% endfor %}
        </div>
        {% endif %}
      </div>
      <div class="card-footer d-flex justify-content-end">
        <button class="btn btn-primary" type="button" onclick="goStep(3)">Next</button>
      </div>
    </div>

    <!-- STEP 3: CHARGES PER CARGO -->
    <div class="card shadow-sm step d-none" id="step-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 3/3 — Charges per Cargo</h3>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary" type="button" onclick="goStep(2)">Back</button>
          <button class="btn btn-success" type="submit">Save Final</button>
        </div>
      </div>
      <div class="card-body" id="charges-container">
        {% if charge_formsets %}
          {% for idx, fs in charge_formsets %}
          <div class="border rounded p-3 mb-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <div class="fw-bold">Cargo #{{ forloop.counter }}</div>
              <button type="button" class="btn btn-sm btn-outline-primary" onclick="addCharge('{{ fs.prefix }}')">+ Add Charge</button>
            </div>
            {{ fs.management_form }}
            <div class="table-responsive">
              <table class="table align-middle">
                <thead class="table-light">
                  <tr>
                    <th>Charge</th><th>Description</th><th>Unit</th>
                    <th class="text-end">Qty</th><th class="text-end">Rate</th>
                    <th>Curr</th><th>Delete</th>
                  </tr>
                </thead>
                <tbody id="{{ fs.prefix }}-tbody">
                  {% for lf in fs %}
                  <tr>
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
            {% if fs.non_form_errors %}
            <div class="alert alert-danger">
              {% for e in fs.non_form_errors %}<div>{{ e }}</div>{% endfor %}
            </div>
            {% endif %}
          </div>
          {% endfor %}
        {% else %}
          <div class="alert alert-info">Tambahkan cargo di Step 2, lalu klik Next untuk membuat charges per cargo.</div>
        {% endif %}
      </div>
      <div class="card-footer d-flex justify-content-end">
        <button class="btn btn-success" type="submit">Save Final</button>
      </div>
    </div>

  </form>
</div>

<!-- TEMPLATES (DOM clone) -->
<template id="cargo-empty">
  <tr class="cargo-row">
    <td><input name="__NAME__-description" class="form-control" placeholder="Coal 5000 MT"></td>
    <td><input name="__NAME__-package_type" class="form-control" placeholder="MT/PLT/CTN"></td>
    <td><input type="number" step="0.001" name="__NAME__-qty" class="form-control text-end" value="1"></td>
    <td><input type="number" step="0.001" name="__NAME__-weight_kg" class="form-control text-end"></td>
    <td><input type="number" step="0.001" name="__NAME__-volume_cbm" class="form-control text-end"></td>
    <td><input name="__NAME__-origin" class="form-control" placeholder="Jakarta"></td>
    <td><input name="__NAME__-destination" class="form-control" placeholder="Makassar"></td>
    <td><input name="__NAME__-extra_notes" class="form-control"></td>
    <td><input type="checkbox" name="__NAME__-DELETE" class="form-check-input"></td>
  </tr>
</template>

<template id="charge-empty">
  <tr>
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
    <td><input name="__PFX__-__IDX__-unit" class="form-control" placeholder="per MT / per CBM / per SHPT"></td>
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
    if(n===3){ ensureChargeBlocks(); }
  }
  function addCargo(){
    const totalInput = document.querySelector('input[name="cargo-TOTAL_FORMS"]');
    let total = parseInt(totalInput.value || '0');
    const tpl = document.getElementById('cargo-empty').content.cloneNode(true);
    tpl.querySelectorAll('[name]').forEach(inp=>{
      inp.name = inp.name.replace('__NAME__', `cargo-${total}`);
    });
    document.getElementById('cargo-tbody').appendChild(tpl);
    totalInput.value = total + 1;
  }
  function ensureChargeBlocks(){
    const container = document.getElementById('charges-container');
    if(container.querySelector('[id$="-tbody"]')) return;
    const total = parseInt(document.querySelector('input[name="cargo-TOTAL_FORMS"]').value || '0');
    for(let i=0;i<total;i++){
      const del = document.querySelector(`input[name="cargo-${i}-DELETE"]`);
      if(del && del.checked) continue;

      const wrap = document.createElement('div');
      wrap.className = 'border rounded p-3 mb-3';
      const prefix = `chg-${i}`;

      const head = document.createElement('div');
      head.className = 'd-flex justify-content-between align-items-center mb-2';
      head.innerHTML = `<div class="fw-bold">Cargo #${i+1}</div>
        <button type="button" class="btn btn-sm btn-outline-primary" onclick="addCharge('${prefix}')">+ Add Charge</button>`;
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
            <th>Charge</th><th>Description</th><th>Unit</th>
            <th class="text-end">Qty</th><th class="text-end">Rate</th>
            <th>Curr</th><th>Delete</th>
          </tr>
        </thead>
        <tbody id="${prefix}-tbody"></tbody>
      </table>`;
      wrap.appendChild(table);
      container.appendChild(wrap);
      addCharge(prefix);
    }
  }
  function addCharge(prefix){
    const tbody = document.getElementById(`${prefix}-tbody`);
    const totalInput = document.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);
    let idx = parseInt(totalInput.value || '0');
    const tpl = document.getElementById('charge-empty').content.cloneNode(true);
    tpl.querySelectorAll('[name]').forEach(el=>{
      el.name = el.name.replace('__PFX__', prefix).replace('__IDX__', idx);
    });
    tbody.appendChild(tpl);
    totalInput.value = idx + 1;
  }
</script>
{% endblock %}
""", encoding="utf-8")
print(" ✓ template: quotation_wizard.html")

print("\nSelesai ✅")
print("Next:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("  python manage.py runserver")
