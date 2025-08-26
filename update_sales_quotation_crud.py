# update_sales_quotation_crud.py
# Usage: python update_sales_quotation_crud.py [--dry-run]
from __future__ import annotations
import sys, argparse, shutil, time
from pathlib import Path

TS = time.strftime("%Y%m%d-%H%M%S")

def backup_then_write(path: Path, content: str, dry_run: bool=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        bak = path.with_suffix(path.suffix + f".{TS}.bak")
        print(f"[backup] {path} -> {bak}")
        if not dry_run:
            shutil.copy2(path, bak)
    print(f"[write]  {path}")
    if not dry_run:
        path.write_text(content, encoding="utf-8")

def assert_in_project_root():
    # heuristik sederhana: harus ada manage.py
    here = Path.cwd()
    if not (here / "manage.py").exists():
        print("ERROR: Jalankan script ini dari root proyek (yang ada manage.py).")
        sys.exit(1)

def main():
    assert_in_project_root()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Tampilkan aksi tanpa menulis file")
    args = ap.parse_args()

    # Lokasi app sales (standar)
    sales_app = Path("sales")
    if not sales_app.exists():
        print("ERROR: Folder app 'sales' tidak ditemukan di root proyek.")
        sys.exit(1)

    # ======== FILE CONTENTS ========
    forms_py = r'''from django import forms
from django.forms import inlineformset_factory
from .models import Quotation, Cargo, CargoCharge

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            "date", "validity_date", "customer", "currency",
            "transport_mode", "service_option", "multi_destination",
            "origin", "destination", "notes",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "validity_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "transport_mode": forms.Select(attrs={"class": "form-select"}),
            "service_option": forms.Select(attrs={"class": "form-select"}),
            "multi_destination": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "origin": forms.TextInput(attrs={"class": "form-control"}),
            "destination": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        multi = cleaned.get("multi_destination")
        origin = cleaned.get("origin")
        dest = cleaned.get("destination")
        if not multi:
            if not origin or not dest:
                raise forms.ValidationError("Untuk single-destination, Origin dan Destination di header wajib diisi.")
        else:
            if origin or dest:
                raise forms.ValidationError("Untuk multi-destination, Origin/Destination tidak diisi di header (diisi per Cargo).")
        return cleaned

class CargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = [
            "description", "qty", "weight_kg", "volume_cbm",
            "origin", "destination",
        ]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "qty": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "0"}),
            "weight_kg": forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "min": "0"}),
            "volume_cbm": forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "min": "0"}),
            "origin": forms.TextInput(attrs={"class": "form-control"}),
            "destination": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.quotation = kwargs.pop("quotation", None)
        super().__init__(*args, **kwargs)
        if self.quotation and not self.quotation.multi_destination:
            self.fields["origin"].widget = forms.HiddenInput()
            self.fields["destination"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        if self.quotation:
            if not self.quotation.multi_destination:
                cleaned["origin"] = self.quotation.origin
                cleaned["destination"] = self.quotation.destination
            else:
                if not cleaned.get("origin") or not cleaned.get("destination"):
                    raise forms.ValidationError("Untuk multi-destination, Origin & Destination wajib diisi per Cargo.")
        return cleaned

class CargoChargeForm(forms.ModelForm):
    class Meta:
        model = CargoCharge
        fields = ["description", "qty", "rate", "amount"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "qty": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "0"}),
            "rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        }

CargoChargeFormSet = inlineformset_factory(
    parent_model=Cargo,
    model=CargoCharge,
    form=CargoChargeForm,
    extra=1,
    can_delete=True,
)
'''

    views_py = r'''from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import transaction
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .models import Quotation, Cargo
from .forms import QuotationForm, CargoForm, CargoChargeFormSet

@require_http_methods(["GET"])
def quotation_list(request):
    qs = Quotation.objects.order_by("-date", "-id")
    return render(request, "sales/quotation_list.html", {"quotations": qs})

@require_http_methods(["GET", "POST"])
@transaction.atomic
def quotation_create(request):
    if request.method == "POST":
        form = QuotationForm(request.POST)
        if form.is_valid():
            q = form.save(commit=False)
            if not getattr(q, "currency", None):
                try:
                    q.currency = "IDR"
                except Exception:
                    pass
            q.save()
            messages.success(request, "Quotation berhasil dibuat. Silakan tambah Cargo.")
            return redirect("sales:quotation_edit", pk=q.pk)
        else:
            messages.error(request, "Gagal menyimpan. Periksa kembali isian Anda.")
    else:
        form = QuotationForm()
    return render(request, "sales/quotation_form.html", {"form": form, "mode": "create"})

@require_http_methods(["GET", "POST"])
@transaction.atomic
def quotation_edit(request, pk):
    q = get_object_or_404(Quotation, pk=pk)
    if request.method == "POST":
        form = QuotationForm(request.POST, instance=q)
        if form.is_valid():
            q = form.save()
            messages.success(request, "Quotation tersimpan.")
            return redirect("sales:quotation_detail", pk=q.pk)
        else:
            messages.error(request, "Gagal menyimpan. Silakan cek error di bawah.")
    else:
        form = QuotationForm(instance=q)
    cargos = q.cargo_set.all().select_related()
    return render(request, "sales/quotation_form.html", {"form": form, "mode": "edit", "quotation": q, "cargos": cargos})

@require_http_methods(["GET"])
def quotation_detail(request, pk):
    q = get_object_or_404(Quotation, pk=pk)
    cargos = q.cargo_set.all().prefetch_related("cargocharge_set")
    return render(request, "sales/quotation_detail.html", {"quotation": q, "cargos": cargos})

@require_http_methods(["GET", "POST"])
@transaction.atomic
def cargo_edit(request, quotation_pk, cargo_pk=None):
    q = get_object_or_404(Quotation, pk=quotation_pk)
    instance = None
    if cargo_pk:
        instance = get_object_or_404(Cargo, pk=cargo_pk, quotation=q)
    if request.method == "POST":
        form = CargoForm(request.POST, instance=instance, quotation=q)
        if form.is_valid():
            cargo = form.save(commit=False)
            cargo.quotation = q
            cargo.save()
            messages.success(request, "Cargo tersimpan.")
            return redirect("sales:quotation_edit", pk=q.pk)
        else:
            messages.error(request, "Gagal menyimpan Cargo. Periksa input Anda.")
    else:
        form = CargoForm(instance=instance, quotation=q)
    return render(request, "sales/cargo_form.html", {"form": form, "quotation": q, "cargo": instance})

@require_http_methods(["GET", "POST"])
@transaction.atomic
def cargo_charges_edit(request, quotation_pk, cargo_pk):
    q = get_object_or_404(Quotation, pk=quotation_pk)
    cargo = get_object_or_404(Cargo, pk=cargo_pk, quotation=q)

    if request.method == "POST":
        formset = CargoChargeFormSet(request.POST, instance=cargo, prefix="charges")
        if formset.is_valid():
            formset.save()
            messages.success(request, "Charges tersimpan.")
            return redirect("sales:quotation_detail", pk=q.pk)
        else:
            messages.error(request, "Gagal menyimpan Charges. Cek kembali.")
    else:
        formset = CargoChargeFormSet(instance=cargo, prefix="charges")

    return render(request, "sales/cargocharge_form.html", {"quotation": q, "cargo": cargo, "formset": formset})
'''

    urls_py = r'''from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    path("quotations/", views.quotation_list, name="quotation_list"),
    path("quotations/new/", views.quotation_create, name="quotation_create"),
    path("quotations/<int:pk>/", views.quotation_detail, name="quotation_detail"),
    path("quotations/<int:pk>/edit/", views.quotation_edit, name="quotation_edit"),

    path("quotations/<int:quotation_pk>/cargo/new/", views.cargo_edit, name="cargo_create"),
    path("quotations/<int:quotation_pk>/cargo/<int:cargo_pk>/edit/", views.cargo_edit, name="cargo_edit"),

    path("quotations/<int:quotation_pk>/cargo/<int:cargo_pk>/charges/", views.cargo_charges_edit, name="cargo_charges_edit"),
]
'''

    tpl_list = r'''{% extends "base.html" %}
{% load static %}
{% block content %}
<div class="app-wrapper p-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h4 m-0">Quotations</h1>
    <a href="{% url 'sales:quotation_create' %}" class="btn btn-primary">+ New Quotation</a>
  </div>
  <div class="table-responsive">
    <table class="table table-hover table-sm">
      <thead class="table-light">
        <tr>
          <th>No</th><th>Date</th><th>Customer</th><th>Mode</th><th>Service</th><th>Multi Dest</th><th></th>
        </tr>
      </thead>
      <tbody>
        {% for q in quotations %}
        <tr onclick="window.location='{% url 'sales:quotation_detail' q.pk %}'" style="cursor:pointer;">
          <td>{{ q.number }}</td>
          <td>{{ q.date }}</td>
          <td>{{ q.customer }}</td>
          <td>{{ q.transport_mode }}</td>
          <td>{{ q.service_option }}</td>
          <td>{% if q.multi_destination %}Yes{% else %}No{% endif %}</td>
          <td><a class="btn btn-outline-secondary btn-sm" href="{% url 'sales:quotation_edit' q.pk %}">Edit</a></td>
        </tr>
        {% empty %}
        <tr><td colspan="7" class="text-center text-muted">No data.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
'''

    tpl_form = r'''{% extends "base.html" %}
{% block content %}
<div class="app-wrapper p-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h4 m-0">{% if mode == 'create' %}New Quotation{% else %}Edit Quotation{% endif %}</h1>
    {% if quotation %}
      <div>
        <a href="{% url 'sales:quotation_detail' quotation.pk %}" class="btn btn-outline-secondary btn-sm">View</a>
      </div>
    {% endif %}
  </div>

  <form method="post" novalidate>
    {% csrf_token %}
    {% if messages %}
      {% for m in messages %}<div class="alert alert-{{ m.tags }}">{{ m }}</div>{% endfor %}
    {% endif %}

    <div class="row g-3">
      {% for field in form %}
      <div class="col-md-4">
        <label class="form-label">{{ field.label }}{% if field.field.required %} *{% endif %}</label>
        {{ field }}
        {% if field.errors %}<div class="text-danger small">{{ field.errors|striptags }}</div>{% endif %}
      </div>
      {% endfor %}
    </div>

    <div class="mt-3 d-flex gap-2">
      <button class="btn btn-primary" type="submit">Save</button>
      {% if quotation %}
        <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_detail' quotation.pk %}">Cancel</a>
      {% else %}
        <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_list' %}">Cancel</a>
      {% endif %}
    </div>
  </form>

  {% if quotation %}
  <hr class="my-4">
  <div class="d-flex justify-content-between align-items-center mb-2">
    <h2 class="h5 m-0">Cargo</h2>
    <a href="{% url 'sales:cargo_create' quotation.pk %}" class="btn btn-success btn-sm">+ Add Cargo</a>
  </div>
  <div class="table-responsive">
    <table class="table table-sm">
      <thead class="table-light"><tr><th>Description</th><th>Qty</th><th>W (kg)</th><th>V (cbm)</th><th>O</th><th>D</th><th></th></tr></thead>
      <tbody>
        {% for c in cargos %}
        <tr>
          <td>{{ c.description }}</td>
          <td class="text-end">{{ c.qty }}</td>
          <td class="text-end">{{ c.weight_kg }}</td>
          <td class="text-end">{{ c.volume_cbm }}</td>
          <td>{{ c.origin }}</td>
          <td>{{ c.destination }}</td>
          <td class="text-nowrap">
            <a href="{% url 'sales:cargo_edit' quotation.pk c.pk %}" class="btn btn-outline-secondary btn-sm">Edit</a>
            <a href="{% url 'sales:cargo_charges_edit' quotation.pk c.pk %}" class="btn btn-outline-primary btn-sm">Charges</a>
          </td>
        </tr>
        {% empty %}
        <tr><td colspan="7" class="text-center text-muted">Belum ada cargo.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</div>
{% endblock %}
'''

    tpl_cargo = r'''{% extends "base.html" %}
{% block content %}
<div class="app-wrapper p-3">
  <h1 class="h5">{{ cargo|default:'New' }} Cargo – Quotation {{ quotation.number }}</h1>
  <form method="post" novalidate>
    {% csrf_token %}
    <div class="row g-3">
      {% for field in form %}
      <div class="col-md-4">
        <label class="form-label">{{ field.label }}{% if field.field.required %} *{% endif %}</label>
        {{ field }}
        {% if field.errors %}<div class="text-danger small">{{ field.errors|striptags }}</div>{% endif %}
      </div>
      {% endfor %}
    </div>
    <div class="mt-3 d-flex gap-2">
      <button class="btn btn-primary">Save</button>
      <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_edit' quotation.pk %}">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
'''

    tpl_charges = r'''{% extends "base.html" %}
{% block content %}
<div class="app-wrapper p-3">
  <div class="d-flex justify-content-between align-items-center mb-2">
    <h1 class="h5 m-0">Charges – {{ cargo.description }} (Quotation {{ quotation.number }})</h1>
    <a href="{% url 'sales:quotation_detail' quotation.pk %}" class="btn btn-outline-secondary btn-sm">Back</a>
  </div>
  <form method="post" novalidate>
    {% csrf_token %}
    {{ formset.management_form }}
    <div class="table-responsive">
      <table class="table table-sm align-middle">
        <thead class="table-light">
          <tr>
            <th>Description</th><th class="text-end">Qty</th><th class="text-end">Rate</th><th class="text-end">Amount</th><th>Delete</th>
          </tr>
        </thead>
        <tbody>
          {% for form in formset %}
          <tr>
            <td>{{ form.description }}</td>
            <td class="text-end">{{ form.qty }}</td>
            <td class="text-end">{{ form.rate }}</td>
            <td class="text-end">{{ form.amount }}</td>
            <td class="text-center">{% if form.instance.pk %}{{ form.DELETE }}{% endif %}</td>
          </tr>
          {% if form.non_field_errors %}
            <tr><td colspan="5" class="text-danger small">{{ form.non_field_errors }}</td></tr>
          {% endif %}
          {% endfor %}
        </tbody>
      </table>
    </div>
    <button class="btn btn-primary">Save</button>
  </form>
</div>
{% endblock %}
'''

    # ======== TARGET PATHS ========
    files = {
        sales_app / "forms.py": forms_py,
        sales_app / "views.py": views_py,
        sales_app / "urls.py": urls_py,
        sales_app / "templates" / "sales" / "quotation_list.html": tpl_list,
        sales_app / "templates" / "sales" / "quotation_form.html": tpl_form,
        sales_app / "templates" / "sales" / "cargo_form.html": tpl_cargo,
        sales_app / "templates" / "sales" / "cargocharge_form.html": tpl_charges,
    }

    # ======== WRITE ========
    for path, content in files.items():
        backup_then_write(path, content, dry_run=args.dry_run)

    print("\nDone.")
    if args.dry_run:
        print("DRY-RUN selesai. Jalankan tanpa --dry-run untuk menulis file.")
    else:
        print("Silakan jalankan server, buka /sales/quotations/ dan uji Create/Edit.")

if __name__ == "__main__":
    main()
