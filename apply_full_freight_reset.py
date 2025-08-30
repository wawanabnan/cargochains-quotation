import os, re, shutil, sys, textwrap, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP  = ROOT / "sales"
TPL  = ROOT / "templates" / "sales" / "freight"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    if not p.exists(): return
    bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
    bak.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, bak)
    print(f"[backup] {p} -> {bak}")

def write(p: Path, content: str, mode="w"):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, mode, encoding="utf-8") as f:
        f.write(textwrap.dedent(content).lstrip())
    print(f"[write]  {p}")

def ensure_app():
    if not APP.exists():
        raise SystemExit(f"Folder app tidak ditemukan: {APP}")

def reset_models():
    p = APP / "models.py"
    backup(p)
    content = f"""
    from django.db import models
    from django.conf import settings

    class FreightQuotation(models.Model):
        BUSINESS_TYPE = "FREIGHT"

        number = models.CharField(max_length=50, unique=True, blank=True)
        date = models.DateField()
        # TODO: Ganti ke model Customer/Partner Anda jika ada (mis. partners.Partner)
        customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
        currency = models.CharField(max_length=10, default="IDR")
        transport_mode = models.CharField(max_length=20, choices=[("SEA","Sea"),("AIR","Air"),("LAND","Land")])
        service_option = models.CharField(max_length=50)
        notes = models.TextField(blank=True)

        # single-destination: isi di header; multi: kosong & isi per cargo
        multi_destination = models.BooleanField(default=False)
        origin = models.CharField(max_length=100, blank=True)
        destination = models.CharField(max_length=100, blank=True)

        created_at = models.DateTimeField(auto_now_add=True)
        updated_at = models.DateTimeField(auto_now=True)

        class Meta:
            ordering = ("-date", "-id")

        def __str__(self):
            return self.number or f"FQ-{{self.pk}}"

    class FreightCargo(models.Model):
        quotation = models.ForeignKey(FreightQuotation, on_delete=models.CASCADE, related_name="cargos")
        description = models.CharField(max_length=255)
        qty = models.PositiveIntegerField(default=1)
        weight_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
        volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
        amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

        # untuk multi-destination
        origin = models.CharField(max_length=100, blank=True)
        destination = models.CharField(max_length=100, blank=True)

        def __str__(self):
            return self.description

    class FreightCharge(models.Model):
        cargo = models.ForeignKey(FreightCargo, on_delete=models.CASCADE, related_name="charges")
        description = models.CharField(max_length=255, blank=True)
        qty = models.PositiveIntegerField(default=0)
        rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
        amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

        def __str__(self):
            return self.description or f"Charge-{{self.pk}}"
    """
    write(p, content)

def reset_forms():
    p = APP / "forms.py"
    backup(p)
    content = """
    from django import forms
    from django.forms import formset_factory
    from .models import FreightQuotation, FreightCargo, FreightCharge

    TRANSPORT_CHOICES = [("SEA","Sea"),("AIR","Air"),("LAND","Land")]
    SERVICE_CHOICES_UNION = [
        ("DOOR_TO_DOOR","Door to Door"),
        ("DOOR_TO_PORT","Door to Port"),
        ("PORT_TO_PORT","Port to Port"),
        ("DOOR_TO_AIRPORT","Door to Airport"),
        ("AIRPORT_TO_AIRPORT","Airport to Airport"),
        ("TRUCKING","Trucking"),
    ]

    class FreightTypeForm(forms.Form):
        business_type = forms.CharField(
            label="Pilih Jenis Quotation", initial="FREIGHT", widget=forms.HiddenInput()
        )

    class FreightHeaderForm(forms.ModelForm):
        transport_mode = forms.ChoiceField(
            label="Moda Transportasi", choices=TRANSPORT_CHOICES, initial="SEA",
            widget=forms.Select(attrs={"class":"form-select form-select-sm","id":"id_transport_mode"})
        )
        service_option = forms.ChoiceField(
            label="Service Option", choices=SERVICE_CHOICES_UNION, initial="DOOR_TO_DOOR",
            widget=forms.Select(attrs={"class":"form-select form-select-sm","id":"id_service_option"})
        )
        multi_destination = forms.BooleanField(
            label="Multi Destination", required=False,
            widget=forms.CheckboxInput(attrs={"class":"form-check-input","id":"id_multi_destination"})
        )

        class Meta:
            model = FreightQuotation
            fields = ["date","customer","currency","notes","origin","destination"]
            widgets = {
                "date": forms.DateInput(attrs={"type":"date","class":"form-control form-control-sm"}),
                "customer": forms.Select(attrs={"class":"form-select form-select-sm"}),
                "currency": forms.Select(attrs={"class":"form-select form-select-sm"}),
                "notes": forms.Textarea(attrs={"class":"form-control form-control-sm","rows":2}),
                "origin": forms.TextInput(attrs={"class":"form-control form-control-sm"}),
                "destination": forms.TextInput(attrs={"class":"form-control form-control-sm"}),
            }

        def clean(self):
            cleaned = super().clean()
            multi = cleaned.get("multi_destination") or False
            origin = cleaned.get("origin")
            dest = cleaned.get("destination")
            if not multi:
                if not origin or not dest:
                    raise forms.ValidationError("Single-destination: Origin & Destination harus diisi.")
            else:
                if origin or dest:
                    raise forms.ValidationError("Multi-destination: Origin/Destination header dikosongkan (isi per cargo).")
            return cleaned

    class FreightCargoForm(forms.ModelForm):
        class Meta:
            model = FreightCargo
            fields = ["description","qty","weight_kg","volume_cbm","amount","origin","destination"]
            widgets = {
                "description": forms.TextInput(attrs={"class":"form-control form-control-sm"}),
                "qty": forms.NumberInput(attrs={"class":"form-control form-control-sm"}),
                "weight_kg": forms.NumberInput(attrs={"class":"form-control form-control-sm"}),
                "volume_cbm": forms.NumberInput(attrs={"class":"form-control form-control-sm"}),
                "amount": forms.NumberInput(attrs={"class":"form-control form-control-sm"}),
                "origin": forms.TextInput(attrs={"class":"form-control form-control-sm"}),
                "destination": forms.TextInput(attrs={"class":"form-control form-control-sm"}),
            }

        def __init__(self, *args, **kwargs):
            self.multi = kwargs.pop("multi_destination", False)
            super().__init__(*args, **kwargs)
            if not self.multi:
                self.fields["origin"].widget = forms.HiddenInput()
                self.fields["destination"].widget = forms.HiddenInput()

        def clean(self):
            cleaned = super().clean()
            if self.multi:
                if not cleaned.get("origin") or not cleaned.get("destination"):
                    raise forms.ValidationError("Multi-destination: Origin & Destination wajib per cargo.")
            return cleaned

    class FreightChargeForm(forms.ModelForm):
        class Meta:
            model = FreightCharge
            fields = ["description","qty","rate","amount"]
            widgets = {
                "description": forms.TextInput(attrs={"class":"form-control form-control-sm"}),
                "qty": forms.NumberInput(attrs={"class":"form-control form-control-sm"}),
                "rate": forms.NumberInput(attrs={"class":"form-control form-control-sm"}),
                "amount": forms.NumberInput(attrs={"class":"form-control form-control-sm"}),
            }

    CargoFormSet  = formset_factory(FreightCargoForm,  extra=2, min_num=1, validate_min=True)
    ChargeFormSet = formset_factory(FreightChargeForm, extra=2, min_num=0, validate_min=False)
    """
    write(p, content)

def reset_views():
    p = APP / "views.py"
    backup(p)
    content = """
    from django.shortcuts import render, redirect, get_object_or_404
    from django.contrib import messages
    from django.views.decorators.http import require_http_methods, require_GET
    from django.db import transaction
    from django.http import JsonResponse
    import datetime
    from django import forms

    from .models import FreightQuotation, FreightCargo, FreightCharge
    from .forms import (
        FreightTypeForm, FreightHeaderForm,
        FreightCargoForm, FreightChargeForm,
        CargoFormSet, ChargeFormSet
    )

    SERVICE_OPTIONS_BY_MODE = {
        "SEA": [("DOOR_TO_DOOR","Door to Door"), ("DOOR_TO_PORT","Door to Port"), ("PORT_TO_PORT","Port to Port")],
        "AIR": [("DOOR_TO_AIRPORT","Door to Airport"), ("AIRPORT_TO_AIRPORT","Airport to Airport")],
        "LAND": [("TRUCKING","Trucking")],
    }

    @require_GET
    def freight_service_options(request):
        mode = (request.GET.get("mode") or "").upper()
        options = [{"value": v, "label": l} for v, l in SERVICE_OPTIONS_BY_MODE.get(mode, [])]
        return JsonResponse({"mode": mode, "options": options})

    # LIST
    def freight_list(request):
        qs = FreightQuotation.objects.all()
        return render(request, "sales/freight/list.html", {"quotations": qs})

    # Wizard state
    WKEY = "freight_wizard"

    def _wiz_get(request):
        return request.session.get(WKEY, {"step": "type", "header": {}, "multi": False})

    def _wiz_set(request, data):
        request.session[WKEY] = data
        request.session.modified = True

    def _wiz_clear(request):
        if WKEY in request.session:
            del request.session[WKEY]

    @require_http_methods(["GET","POST"])
    def freight_create_wizard(request):
        wiz = _wiz_get(request)
        step = (request.GET.get("step") or wiz.get("step") or "type").lower()

        # STEP 1
        if step == "type":
            if request.method == "POST":
                wiz["step"] = "header"
                _wiz_set(request, wiz)
                return redirect(f"{request.path}?step=header")
            form = FreightTypeForm()
            return render(request, "sales/freight/wizard.html", {"step": "type", "form_type": form})

        # STEP 2
        if step == "header":
            if request.method == "POST":
                form = FreightHeaderForm(request.POST)
                if form.is_valid():
                    cd = form.cleaned_data
                    wiz["header"] = {
                        "date": cd["date"].isoformat(),
                        "customer_id": cd["customer"].pk,
                        "currency": cd["currency"],
                        "notes": cd.get("notes") or "",
                        "origin": cd.get("origin") or "",
                        "destination": cd.get("destination") or "",
                        "transport_mode": cd["transport_mode"],
                        "service_option": cd["service_option"],
                        "multi_destination": bool(cd.get("multi_destination") or False),
                    }
                    wiz["multi"] = wiz["header"]["multi_destination"]
                    wiz["step"] = "lines"
                    _wiz_set(request, wiz)
                    return redirect(f"{request.path}?step=lines")
                messages.error(request, "Periksa Header Information.")
            else:
                form = FreightHeaderForm()
            return render(request, "sales/freight/wizard.html", {"step":"header", "form_header": form})

        # guard
        if step == "lines" and not wiz.get("header"):
            wiz["step"] = "header"; _wiz_set(request, wiz)
            return redirect(f"{request.path}?step=header")

        # STEP 3
        if step == "lines":
            hdr = wiz["header"]
            multi = wiz.get("multi", False)
            origin_hdr = hdr.get("origin","")
            dest_hdr = hdr.get("destination","")

            CargoFS = CargoFormSet
            ChargeFS = ChargeFormSet

            if request.method == "POST":
                cargo_fs = CargoFS(request.POST, prefix="cargo")
                charge_fs = ChargeFS(request.POST, prefix="charge")

                # inject multi flag untuk tampilan single→hide O/D
                for f in cargo_fs.forms:
                    f.multi = multi
                    if not multi:
                        f.fields["origin"].widget = forms.HiddenInput()
                        f.fields["destination"].widget = forms.HiddenInput()

                if cargo_fs.is_valid() and charge_fs.is_valid():
                    # save header
                    q = FreightQuotation.objects.create(
                        date = datetime.date.fromisoformat(hdr["date"]),
                        customer_id = hdr["customer_id"],
                        currency = hdr["currency"] or "IDR",
                        transport_mode = hdr["transport_mode"],
                        service_option = hdr["service_option"],
                        notes = hdr.get("notes",""),
                        multi_destination = multi,
                        origin = ("" if multi else origin_hdr),
                        destination = ("" if multi else dest_hdr),
                    )

                    # cargos
                    cargos_created = 0
                    for f in cargo_fs:
                        cd = f.cleaned_data or {}
                        if not cd: continue
                        c = FreightCargo(
                            quotation=q,
                            description=cd.get("description"),
                            qty=cd.get("qty") or 0,
                            weight_kg=cd.get("weight_kg") or 0,
                            volume_cbm=cd.get("volume_cbm") or 0,
                            amount=cd.get("amount") or 0,
                            origin=(cd.get("origin") if multi else origin_hdr) or "",
                            destination=(cd.get("destination") if multi else dest_hdr) or "",
                        )
                        c.save()
                        cargos_created += 1

                    if cargos_created < 1:
                        q.delete()
                        messages.error(request, "Minimal satu Cargo wajib diisi.")
                        return render(request, "sales/freight/wizard.html", {
                            "step":"lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs, "multi_destination": multi
                        })

                    # charges (opsional) — attach ke cargo pertama
                    first_cargo = q.cargos.first()
                    if first_cargo:
                        for f in charge_fs:
                            cd = f.cleaned_data or {}
                            if not cd: continue
                            if not (cd.get("description") or cd.get("qty") or cd.get("rate") or cd.get("amount")):
                                continue
                            FreightCharge.objects.create(
                                cargo=first_cargo,
                                description=cd.get("description",""),
                                qty=cd.get("qty") or 0,
                                rate=cd.get("rate") or 0,
                                amount=cd.get("amount") or 0,
                            )

                    _wiz_clear(request)
                    messages.success(request, "Freight Quotation berhasil dibuat.")
                    return redirect("sales:freight_list")

                messages.error(request, "Periksa isian Cargo / Charge.")
                return render(request, "sales/freight/wizard.html", {
                    "step":"lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs, "multi_destination": multi
                })

            # GET
            cargo_fs = CargoFS(prefix="cargo")
            charge_fs = ChargeFS(prefix="charge")
            return render(request, "sales/freight/wizard.html", {
                "step":"lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs, "multi_destination": wiz.get("multi", False)
            })

        # fallback
        wiz["step"] = "type"; _wiz_set(request, wiz)
        return redirect(f"{request.path}?step=type")

    def freight_view(request, pk):
        q = get_object_or_404(FreightQuotation, pk=pk)
        return render(request, "sales/freight/view.html", {"q": q})

    @require_http_methods(["GET","POST"])
    @transaction.atomic
    def freight_edit(request, pk):
        q = get_object_or_404(FreightQuotation, pk=pk)
        if request.method == "POST":
            form = FreightHeaderForm(request.POST, instance=q)
            if form.is_valid():
                obj = form.save(commit=False)
                # maintain extra fields from cleaned_data:
                cd = form.cleaned_data
                q.transport_mode = cd["transport_mode"]
                q.service_option = cd["service_option"]
                q.multi_destination = bool(cd.get("multi_destination") or False)
                obj.save()
                messages.success(request, "Quotation updated.")
                return redirect("sales:freight_view", pk=q.pk)
        else:
            initial = {
                "transport_mode": q.transport_mode,
                "service_option": q.service_option,
                "multi_destination": q.multi_destination,
            }
            form = FreightHeaderForm(instance=q, initial=initial)
        return render(request, "sales/freight/edit.html", {"form": form, "q": q})
    """
    write(p, content)

def reset_urls():
    p = APP / "urls.py"
    backup(p)
    content = """
    from django.urls import path
    from . import views

    app_name = "sales"

    urlpatterns = [
        # FREIGHT
        path("quotations/freight/", views.freight_list, name="freight_list"),
        path("quotations/freight/new/", views.freight_create_wizard, name="freight_create"),
        path("quotations/freight/<int:pk>/edit/", views.freight_edit, name="freight_edit"),
        path("quotations/freight/<int:pk>/view/", views.freight_view, name="freight_view"),
        # AJAX
        path("quotations/freight/service-options/", views.freight_service_options, name="freight_service_options"),
    ]
    """
    write(p, content)

def reset_admin():
    p = APP / "admin.py"
    backup(p)
    content = """
    from django.contrib import admin
    from .models import FreightQuotation, FreightCargo, FreightCharge

    class FreightCargoInline(admin.TabularInline):
        model = FreightCargo
        extra = 0

    @admin.register(FreightQuotation)
    class FreightQuotationAdmin(admin.ModelAdmin):
        list_display = ("id","number","date","customer","transport_mode","service_option","multi_destination","currency")
        inlines = [FreightCargoInline]

    @admin.register(FreightCharge)
    class FreightChargeAdmin(admin.ModelAdmin):
        list_display = ("id","cargo","description","qty","rate","amount")
    """
    write(p, content)

def reset_templates():
    # list.html
    write(TPL / "list.html", """
    {% extends "base.html" %}
    {% block title %}Freight Quotations{% endblock %}
    {% block content %}
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h3 class="mb-0">Freight Quotations</h3>
      <a href="{% url 'sales:freight_create' %}" class="btn btn-primary rounded-0">Create New</a>
    </div>
    <div class="card shadow-sm border-0">
      <div class="table-responsive">
        <table class="table table-hover table-sm align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>No</th><th>Date</th><th>Customer</th><th>Mode</th><th>Service</th><th>Multi</th><th></th>
            </tr>
          </thead>
          <tbody>
            {% for q in quotations %}
            <tr>
              <td>{{ q.number|default:q.pk }}</td>
              <td>{{ q.date|date:"Y-m-d" }}</td>
              <td>{{ q.customer }}</td>
              <td>{{ q.transport_mode }}</td>
              <td>{{ q.service_option }}</td>
              <td>{% if q.multi_destination %}<span class="badge text-bg-primary">Yes</span>{% else %}<span class="badge text-bg-secondary">No</span>{% endif %}</td>
              <td class="text-end">
                <a class="btn btn-sm btn-outline-secondary" href="{% url 'sales:freight_view' q.pk %}">View</a>
              </td>
            </tr>
            {% empty %}
            <tr><td colspan="7" class="text-center text-secondary py-4">No data.</td></tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    {% endblock %}
    """)

    # wizard.html
    write(TPL / "wizard.html", """
    {% extends "base.html" %}
    {% block title %}New Freight Quotation{% endblock %}

    {% block content %}
    <div class="card shadow-sm border-0">
      <div class="card-header py-2">
        <ol class="breadcrumb mb-0">
          <li class="breadcrumb-item {% if step == 'type' %}active{% endif %}">Pilih Jenis Quotation</li>
          <li class="breadcrumb-item {% if step == 'header' %}active{% endif %}">Header Information</li>
          <li class="breadcrumb-item {% if step == 'lines' %}active{% endif %}">Cargo & Charges</li>
        </ol>
      </div>

      <div class="card-body">
        {% if step == 'type' %}
          <form method="post">{% csrf_token %}
            <p class="mb-2">Jenis yang dipilih: <strong>Freight</strong></p>
            {{ form_type.business_type }}
            <div class="d-flex justify-content-end gap-2">
              <a href="{% url 'sales:freight_list' %}" class="btn btn-outline-secondary rounded-0">Cancel</a>
              <button class="btn btn-primary rounded-0" type="submit">Next</button>
            </div>
          </form>

        {% elif step == 'header' %}
          <form method="post">{% csrf_token %}
            {% if form_header.non_field_errors %}
              <div class="alert alert-danger py-2 mb-3">{{ form_header.non_field_errors }}</div>
            {% endif %}
            <div class="row g-3">
              <div class="col-12 col-md-4">
                <label class="form-label">Date</label>{{ form_header.date }}
              </div>
              <div class="col-12 col-md-4">
                <label class="form-label">Customer</label>{{ form_header.customer }}
              </div>
              <div class="col-12 col-md-4">
                <label class="form-label">Currency</label>{{ form_header.currency }}
              </div>
              <div class="col-12">
                <label class="form-label">Notes</label>{{ form_header.notes }}
              </div>

              <div class="col-12 col-md-6">
                <label class="form-label">Moda Transportasi</label>{{ form_header.transport_mode }}
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label">Service Option</label>{{ form_header.service_option }}
              </div>

              {% if not form_header.origin.is_hidden %}
              <div class="col-12 col-md-6">
                <label class="form-label">Origin</label>{{ form_header.origin }}
              </div>
              {% else %}{{ form_header.origin }}{% endif %}

              {% if not form_header.destination.is_hidden %}
              <div class="col-12 col-md-6">
                <label class="form-label">Destination</label>{{ form_header.destination }}
              </div>
              {% else %}{{ form_header.destination }}{% endif %}

              <div class="col-12">
                <div class="form-check mt-1">
                  {{ form_header.multi_destination }}
                  <label class="form-check-label ms-1" for="id_multi_destination">Multi Destination</label>
                </div>
              </div>
            </div>

            <div class="d-flex justify-content-between mt-3">
              <a href="?step=type" class="btn btn-outline-secondary rounded-0">Back</a>
              <button class="btn btn-primary rounded-0" type="submit">Next</button>
            </div>
          </form>

        {% elif step == 'lines' %}
          <form method="post">{% csrf_token %}
            {{ cargo_fs.management_form }}
            <h6>Cargo Detail</h6>
            <div class="table-responsive mb-3">
              <table class="table table-sm align-middle">
                <thead class="table-light">
                  <tr>
                    <th>Description</th><th class="text-end" style="width:100px;">Qty</th>
                    <th class="text-end" style="width:120px;">Weight</th>
                    <th class="text-end" style="width:120px;">Volume</th>
                    <th class="text-end" style="width:140px;">Amount</th>
                    {% if multi_destination %}<th>Origin</th><th>Destination</th>{% endif %}
                  </tr>
                </thead>
                <tbody>
                  {% for f in cargo_fs %}
                  <tr>
                    <td>{{ f.description }}</td>
                    <td class="text-end">{{ f.qty }}</td>
                    <td class="text-end">{{ f.weight_kg }}</td>
                    <td class="text-end">{{ f.volume_cbm }}</td>
                    <td class="text-end">{{ f.amount }}</td>
                    {% if multi_destination %}
                      <td>{{ f.origin }}</td>
                      <td>{{ f.destination }}</td>
                    {% endif %}
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>

            {{ charge_fs.management_form }}
            <h6>Cargo Charge Lines (Optional)</h6>
            <div class="table-responsive">
              <table class="table table-sm align-middle">
                <thead class="table-light">
                  <tr><th>Charge</th><th class="text-end" style="width:100px;">Qty</th><th class="text-end" style="width:140px;">Rate</th><th class="text-end" style="width:140px;">Amount</th></tr>
                </thead>
                <tbody>
                  {% for f in charge_fs %}
                  <tr>
                    <td>{{ f.description }}</td>
                    <td class="text-end">{{ f.qty }}</td>
                    <td class="text-end">{{ f.rate }}</td>
                    <td class="text-end">{{ f.amount }}</td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>

            <div class="d-flex justify-content-between mt-3">
              <a href="?step=header" class="btn btn-outline-secondary rounded-0">Back</a>
              <button class="btn btn-primary rounded-0" type="submit">Create</button>
            </div>
          </form>
        {% endif %}
      </div>
    </div>
    {% endblock %}

    {% block extra_js %}
    <script>
    (function(){
      const modeSel=document.getElementById("id_transport_mode");
      const svcSel=document.getElementById("id_service_option");
      if(!modeSel||!svcSel) return;
      const endpoint="{% url 'sales:freight_service_options' %}";
      function refill(opts){
        const prev=svcSel.value; svcSel.innerHTML="";
        (opts||[]).forEach(o=>{const el=document.createElement("option"); el.value=o.value; el.textContent=o.label; svcSel.appendChild(el);});
        const keep=[...svcSel.options].some(o=>o.value===prev);
        svcSel.value=keep?prev:(svcSel.options[0]?.value||"");
      }
      function fetchOps(mode){
        fetch(endpoint+"?mode="+encodeURIComponent(mode),{headers:{"X-Requested-With":"XMLHttpRequest"}})
          .then(r=>r.json()).then(d=>refill(d.options)).catch(()=>{});
      }
      fetchOps(modeSel.value);
      modeSel.addEventListener("change",()=>fetchOps(modeSel.value));
    })();
    </script>
    {% endblock %}
    """)

    # view.html
    write(TPL / "view.html", """
    {% extends "base.html" %}
    {% block title %}View Freight Quotation{% endblock %}
    {% block content %}
    <h3 class="mb-3">Freight Quotation {{ q.number|default:q.pk }}</h3>
    <p class="text-secondary mb-2">{{ q.date|date:"Y-m-d" }} · {{ q.customer }} · {{ q.currency }}</p>
    <p class="mb-2">{{ q.transport_mode }} — {{ q.service_option }}</p>
    {% if q.multi_destination %}
      <p class="mb-2"><span class="badge text-bg-primary">Multi Destination</span></p>
    {% else %}
      <p class="mb-2">{{ q.origin }} → {{ q.destination }}</p>
    {% endif %}

    <div class="card border-0 shadow-sm mt-3">
      <div class="card-body p-0">
        <div class="table-responsive">
          <table class="table table-sm align-middle mb-0">
            <thead class="table-light">
              <tr><th>Description</th><th class="text-end">Qty</th><th class="text-end">Weight</th><th class="text-end">Volume</th><th class="text-end">Amount</th><th>O/D</th></tr>
            </thead>
            <tbody>
              {% for c in q.cargos.all %}
              <tr>
                <td>{{ c.description }}</td>
                <td class="text-end">{{ c.qty }}</td>
                <td class="text-end">{{ c.weight_kg }}</td>
                <td class="text-end">{{ c.volume_cbm }}</td>
                <td class="text-end">{{ c.amount }}</td>
                <td>
                  {% if q.multi_destination %}{{ c.origin }} → {{ c.destination }}{% else %}{{ q.origin }} → {{ q.destination }}{% endif %}
                </td>
              </tr>
              {% for ch in c.charges.all %}
              <tr class="table-light">
                <td class="ps-4">↳ {{ ch.description }}</td>
                <td class="text-end">{{ ch.qty }}</td>
                <td></td><td></td>
                <td class="text-end">{{ ch.amount }}</td>
                <td></td>
              </tr>
              {% endfor %}
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
    {% endblock %}
    """)

    # edit.html
    write(TPL / "edit.html", """
    {% extends "base.html" %}
    {% block title %}Edit Freight Quotation{% endblock %}
    {% block content %}
    <h3 class="mb-3">Edit Freight Quotation {{ q.number|default:q.pk }}</h3>
    <form method="post">{% csrf_token %}
      <div class="row g-3">
        {{ form.non_field_errors }}
        {% for f in form %}
          <div class="col-12 col-md-4">
            <label class="form-label">{{ f.label }}</label>
            {{ f }}
            {% if f.errors %}<div class="text-danger small">{{ f.errors|striptags }}</div>{% endif %}
          </div>
        {% endfor %}
      </div>
      <div class="mt-3 d-flex justify-content-between">
        <a class="btn btn-outline-secondary rounded-0" href="{% url 'sales:freight_view' q.pk %}">Cancel</a>
        <button class="btn btn-primary rounded-0" type="submit">Save</button>
      </div>
    </form>
    {% endblock %}
    """)

def remove_old_imports_alias_hint():
    """Optional: beritahu jika file lain masih import Quotation/Cargo lama."""
    suspects = []
    for f in ["views.py","forms.py","admin.py","serializers.py","urls.py"]:
        p = APP / f
        if p.exists() and "from .models import Quotation" in p.read_text(encoding="utf-8"):
            suspects.append(str(p))
    if suspects:
        print("\n[notice] File berikut masih mengimpor 'Quotation' lama:")
        for s in suspects:
            print(" -", s)
        print("Silakan sesuaikan bila perlu (skrip saat ini sudah menulis ulang forms/views/urls/admin).")

def main():
    ensure_app()
    reset_models()
    reset_forms()
    reset_views()
    reset_urls()
    reset_admin()
    reset_templates()
    remove_old_imports_alias_hint()
    print("\n✅ Patch selesai.")
    print("➡ Jalankan:")
    print("   python manage.py makemigrations sales")
    print("   python manage.py migrate")
    print("   python manage.py runserver")
    print("\nFreight URLs:")
    print(" - /sales/quotations/freight/")
    print(" - /sales/quotations/freight/new/?step=type")
    print(" - /sales/quotations/freight/<pk>/view/")
    print(" - /sales/quotations/freight/<pk>/edit/")

if __name__ == "__main__":
    main()
