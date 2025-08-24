import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari root project (yang ada manage.py)."

SALES = ROOT / "sales"
VIEWS = SALES / "views.py"
URLS  = SALES / "urls.py"
FORMS = SALES / "forms.py"
TPLDIR = SALES / "templates" / "sales"
TPL   = TPLDIR / "quotation_wizard.html"

def backup(p: pathlib.Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + ".bak")
        if not bak.exists():
            bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  • backup {p} -> {bak}")

def ensure_dirs():
    TPLDIR.mkdir(parents=True, exist_ok=True)

print("== Add Single-Page Quotation Wizard ==")
ensure_dirs()

# 1) Ensure forms.py has the form & formsets we need (header-only, dest & line)
print("[FORMS] ensuring QuotationForm, DestinationFormSet, LineFormSet ...")
forms_txt = FORMS.read_text(encoding="utf-8") if FORMS.exists() else ""
backup(FORMS)

BASE_FORMS = """\
from datetime import date, timedelta
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, QuotationDestination, QuotationLine

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        # header only
        fields = ["date","customer","origin","cargo_desc","validity_date","payment_terms","notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "validity_date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "customer": forms.Select(attrs={"class":"form-select"}),
            "origin": forms.TextInput(attrs={"class":"form-control"}),
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
        active = [f for f in self.forms if not f.cleaned_data.get('DELETE', False)
                  and any(f.cleaned_data.get(k) for k in ['destination','incoterms','transit_time_days','schedule','extra_notes'])]
        if len(active) < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal harus ada 1 destination.")

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
        # validasi dilakukan per-destination di view, tapi tetap pastikan ada minimal satu entry terisi
        active = 0
        for f in self.forms:
            if f.cleaned_data.get('DELETE', False):
                continue
            if any(f.cleaned_data.get(k) for k in ['charge_type','description','unit','qty','rate','currency']):
                active += 1
        # jangan raise di sini; validasi full ada di view per-destination

LineFormSetFactory = lambda *args, **kwargs: inlineformset_factory(
    QuotationDestination,
    QuotationLine,
    formset=_LineFormSet,
    fields=["charge_type","description","unit","qty","rate","currency"],
    extra=1,
    can_delete=True
)
"""

need_write_forms = False
if "class QuotationForm" not in forms_txt or "DestinationFormSet" not in forms_txt or "LineFormSetFactory" not in forms_txt:
    forms_txt = BASE_FORMS
    need_write_forms = True

if need_write_forms:
    FORMS.write_text(forms_txt, encoding="utf-8")
    print("  ✓ forms.py written/updated")
else:
    print("  ✓ forms.py already OK")

# 2) Patch views.py: add QuotationWizardView (single-page, atomic save)
print("[VIEWS] adding QuotationWizardView ...")
txt = VIEWS.read_text(encoding="utf-8") if VIEWS.exists() else ""
backup(VIEWS)

if "from django.db import transaction" not in txt:
    txt = "from django.db import transaction\n" + txt
if "from django.shortcuts import" in txt and "redirect" not in txt:
    txt = re.sub(r"from django\.shortcuts import ([^\n]+)",
                 lambda m: f"from django.shortcuts import {m.group(1)}, redirect",
                 txt)
elif "from django.shortcuts import" not in txt:
    txt = "from django.shortcuts import render, get_object_or_404, redirect\n" + txt

if "from .forms import" in txt and "QuotationForm" in txt and "DestinationFormSet" in txt and "LineFormSetFactory" in txt:
    pass
else:
    # ensure import line
    if "from .forms import" in txt:
        txt = re.sub(r"from \.forms import ([^\n]+)",
                     lambda m: f"from .forms import {m.group(1)}, QuotationForm, DestinationFormSet, LineFormSetFactory",
                     txt)
    else:
        txt = "from .forms import QuotationForm, DestinationFormSet, LineFormSetFactory\n" + txt

if "from .models import" in txt and "Quotation" in txt and "QuotationDestination" in txt:
    pass
else:
    if "from .models import" in txt:
        txt = re.sub(r"from \.models import ([^\n]+)",
                     lambda m: f"from .models import {m.group(1)}, Quotation, QuotationDestination",
                     txt)
    else:
        txt = "from .models import Quotation, QuotationDestination\n" + txt

# add the class-based view if missing
if "class QuotationWizardView" not in txt:
    txt += """

class QuotationWizardView:
    \"\"\"Single-page wizard: Header + Destinations + Lines, save once (atomic).\"\"\"
    template_name = "sales/quotation_wizard.html"

    def __call__(self, request):
        return self.dispatch(request)

    def dispatch(self, request):
        if request.method == "POST":
            return self.post(request)
        return self.get(request)

    def get(self, request):
        header_form = QuotationForm()
        dest_formset = DestinationFormSet(prefix="dest")
        # belum buat line formset agar ringan; dibuat dinamis saat user ke Step 3 via JS
        context = {
            "header_form": header_form,
            "dest_formset": dest_formset,
            "line_prefix_base": "line",  # prefix base untuk setiap destination
        }
        return render(request, self.template_name, context)

    def post(self, request):
        header_form = QuotationForm(request.POST)
        dest_formset = DestinationFormSet(request.POST, prefix="dest")

        # Kumpulkan line formset per-destination menggunakan prefix unik per form
        # Prefix baris line akan berupa: f"line-{index}"
        line_formsets = []
        total_dest = int(request.POST.get("dest-TOTAL_FORMS", "0") or "0")

        # Factory untuk LineFormSet
        LFSF = LineFormSetFactory()

        # Bangun formset per-destination (hanya untuk forms yang tidak di-delete)
        for i in range(total_dest):
            # skip baris dest yang dihapus
            if request.POST.get(f"dest-{i}-DELETE") == "on":
                continue
            line_prefix = f"line-{i}"
            # untuk line formset, kita perlu instance destination "sementara" untuk validasi bentuk data;
            # karena belum ada instance DB, gunakan None & validasi manual jumlah aktif
            fs = LFSF(data=request.POST, prefix=line_prefix, instance=None)
            line_formsets.append((i, fs))

        # Validasi semua
        valid = header_form.is_valid() and dest_formset.is_valid()
        for _, fs in line_formsets:
            valid = valid and fs.is_valid()

        # Validasi bisnis: minimal 1 destination aktif dan tiap dest minimal 1 line aktif
        from django.core.exceptions import ValidationError
        dest_active_indices = []
        for i in range(total_dest):
            if request.POST.get(f"dest-{i}-DELETE") == "on":
                continue
            # cek ada field destination terisi
            if any(request.POST.get(f"dest-{i}-{k}", "").strip() for k in ["destination","incoterms","transit_time_days","schedule","extra_notes"]):
                dest_active_indices.append(i)

        if len(dest_active_indices) < 1:
            header_form.add_error(None, ValidationError("Minimal harus ada 1 destination."))
            valid = False

        # cek setiap destination punya minimal 1 line
        for i, fs in line_formsets:
            active_lines = 0
            for form in fs.forms:
                if form.cleaned_data.get("DELETE", False):
                    continue
                if any(form.cleaned_data.get(k) for k in ["charge_type","description","unit","qty","rate","currency"]):
                    active_lines += 1
            if active_lines < 1:
                # sisipkan error ke non_form_errors agar nampak di UI
                fs._non_form_errors = ["Minimal 1 line untuk destination ke-%s." % (i+1)]
                valid = False

        if not valid:
            # render ulang dengan error
            context = {
                "header_form": header_form,
                "dest_formset": dest_formset,
                "line_formsets": line_formsets,
                "line_prefix_base": "line",
            }
            return render(request, self.template_name, context)

        # Save sekali dalam atomic transaction
        from django.db import transaction
        with transaction.atomic():
            q = header_form.save(commit=False)
            # nomor akan diisi otomatis di models.save() jika kosong (auto-number)
            q.save()

            # Simpan destinasi satu per satu
            saved_dest_objs = []
            for i in range(total_dest):
                if request.POST.get(f"dest-{i}-DELETE") == "on":
                    continue
                # kalau kosong semua, skip
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
                saved_dest_objs.append((i, d))

            # simpan lines per destination yang tersimpan
            from .models import QuotationLine
            for i, d in saved_dest_objs:
                line_prefix = f"line-{i}"
                LFSF2 = LineFormSetFactory()
                fs = LFSF2(data=request.POST, prefix=line_prefix, instance=d)
                if fs.is_valid():
                    # save formset (akan assign destination = d)
                    fs.save()
                else:
                    #Jika anehnya invalid di sini, raise untuk trigger rollback
                    raise ValidationError("Data lines invalid pada destination ke-%s." % (i+1))

        return redirect("sales:quotation_detail", pk=q.pk)
"""

    print("  • adding class QuotationWizardView")
    txt += "\n" + "quotation_wizard_view = QuotationWizardView()\n"
else:
    print("  ✓ QuotationWizardView already present")

VIEWS.write_text(txt, encoding="utf-8")
print("  ✓ views.py updated")

# 3) Patch urls.py
print("[URLS] add route /sales/quotations/wizard/new/ ...")
urls = URLS.read_text(encoding="utf-8") if URLS.exists() else ""
backup(URLS)

if "from django.urls import path" not in urls:
    urls = "from django.urls import path\n" + urls
if "from .views import" in urls and "quotation_wizard_view" in urls:
    pass
elif "from .views import" in urls:
    urls = re.sub(r"from \.views import ([^\n]+)",
                  lambda m: f"from .views import {m.group(1)}, quotation_wizard_view",
                  urls)
else:
    urls = "from .views import quotation_wizard_view\n" + urls

if "app_name" not in urls:
    urls += "\napp_name = 'sales'\n"
if "urlpatterns" not in urls:
    urls += "\nurllib = []\nurlpatterns = urllib\n"

if "quotation_wizard" not in urls:
    urls = re.sub(r"urlpatterns\s*=\s*\[",
                  "urlpatterns = [\n    path('quotations/wizard/new/', quotation_wizard_view, name='quotation_wizard'),",
                  urls, count=1)
URLS.write_text(urls, encoding="utf-8")
print("  ✓ urls.py updated")

# 4) Template: quotation_wizard.html (single page, 3 sections + JS)
print("[TEMPLATE] writing quotation_wizard.html ...")
backup(TPL)
TPL.write_text("""\
{% extends "base.html" %}
{% load static %}
{% block title %}New Quotation (Wizard){% endblock %}

{% block content %}
<div class="container-fluid">
  <form method="post" id="wizard-form" novalidate>
    {% csrf_token %}

    <!-- STEP 1: HEADER -->
    <div class="card shadow-sm rounded-2xl mb-3 step" id="step-1">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 1/3 — Header</h3>
        <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_list' %}">Back</a>
      </div>
      <div class="card-body">
        <div class="row g-3">
          <div class="col-md-4">
            <label class="form-label">Date</label>
            {{ header_form.date }}
            {% for e in header_form.date.errors %}<div class="text-danger small">{{ e }}</div>{% endfor %}
          </div>
          <div class="col-md-4">
            <label class="form-label">Validity Date</label>
            {{ header_form.validity_date }}
            {% for e in header_form.validity_date.errors %}<div class="text-danger small">{{ e }}</div>{% endfor %}
          </div>
          <div class="col-md-4">
            <label class="form-label">Customer</label>
            {{ header_form.customer }}
            {% for e in header_form.customer.errors %}<div class="text-danger small">{{ e }}</div>{% endfor %}
          </div>
          <div class="col-md-6">
            <label class="form-label">Origin</label>
            {{ header_form.origin }}
          </div>
          <div class="col-md-6">
            <label class="form-label">Cargo Description</label>
            {{ header_form.cargo_desc }}
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

    <!-- STEP 2: DESTINATIONS -->
    <div class="card shadow-sm rounded-2xl mb-3 step d-none" id="step-2">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 2/3 — Destinations</h3>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary" type="button" onclick="goStep(1)">Back</button>
          <button class="btn btn-primary" type="button" onclick="goStep(3)">Next</button>
        </div>
      </div>
      <div class="card-body">
        {{ dest_formset.management_form }}
        <div id="dest-rows" class="table-responsive">
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

    <!-- STEP 3: LINES (per destination) -->
    <div class="card shadow-sm rounded-2xl step d-none" id="step-3">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h3 class="card-title">Step 3/3 — Lines per Destination</h3>
        <div class="d-flex gap-2">
          <button class="btn btn-outline-secondary" type="button" onclick="goStep(2)">Back</button>
          <!-- Save Final: submit form -->
          <button class="btn btn-success" type="submit">Save Final</button>
        </div>
      </div>
      <div class="card-body" id="lines-container">
        {# Pada POST invalid, server akan kirim line_formsets #}
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
            {% if fs._non_form_errors %}
            <div class="alert alert-danger">
              {% for e in fs._non_form_errors %}<div>{{ e }}</div>{% endfor %}
            </div>
            {% endif %}
          </div>
          {% endfor %}
        {% else %}
          <div class="alert alert-info">Setelah menambahkan destinasi di Step 2, klik Next untuk memunculkan form Lines per destination. Anda bisa menambah baris line per destination di sini sebelum Save Final.</div>
        {% endif %}
      </div>
      <div class="card-footer d-flex justify-content-end">
        <button class="btn btn-success" type="submit">Save Final</button>
      </div>
    </div>

  </form>
</div>

<!-- TEMPLATES untuk cloning (Dest & Line) -->
<template id="dest-empty-row">
  <tr class="dest-row">
    <td><input type="text" name="__NAME__-destination" class="form-control"></td>
    <td><input type="text" name="__NAME__-incoterms" class="form-control"></td>
    <td><input type="text" name="__NAME__-transit_time_days" class="form-control"></td>
    <td><input type="text" name="__NAME__-schedule" class="form-control"></td>
    <td><input type="text" name="__NAME__-extra_notes" class="form-control"></td>
    <td><input type="checkbox" name="__NAME__-DELETE" class="form-check-input"></td>
  </tr>
</template>

<template id="line-empty-row">
  <tr>
    <td><select name="__PREFIX__-__IDX__-charge_type" class="form-select">
      <option value="">---</option>
      <option value="FREIGHT">FREIGHT</option>
      <option value="ORIGIN">ORIGIN</option>
      <option value="DEST">DEST</option>
      <option value="DOC">DOC</option>
      <option value="OTHER">OTHER</option>
    </select></td>
    <td><input name="__PREFIX__-__IDX__-description" class="form-control"></td>
    <td><input name="__PREFIX__-__IDX__-unit" class="form-control"></td>
    <td><input type="number" step="0.001" name="__PREFIX__-__IDX__-qty" class="form-control text-end" value="1"></td>
    <td><input type="number" step="0.0001" name="__PREFIX__-__IDX__-rate" class="form-control text-end"></td>
    <td><input name="__PREFIX__-__IDX__-currency" class="form-control" value="USD"></td>
    <td><input type="checkbox" name="__PREFIX__-__IDX__-DELETE" class="form-check-input"></td>
  </tr>
</template>

<script>
  // step show/hide
  function goStep(n){
    document.querySelectorAll('.step').forEach(s=>s.classList.add('d-none'));
    document.getElementById('step-'+n).classList.remove('d-none');
    // Saat masuk step-3 pertama kali, generate blok line untuk setiap dest aktif
    if(n===3){ ensureLineBlocks(); }
  }

  // DESTINATION dynamic
  function addDest(){
    const totalInput = document.querySelector('input[name="dest-TOTAL_FORMS"]');
    let total = parseInt(totalInput.value || '0');
    const nameBase = `dest-${total}`;
    const tpl = document.getElementById('dest-empty-row').content.cloneNode(true);
    // set nama-nama input
    tpl.querySelectorAll('input').forEach(inp=>{
      inp.name = inp.name.replace('__NAME__', nameBase);
    });
    document.getElementById('dest-tbody').appendChild(tpl);
    totalInput.value = total + 1;
  }

  // LINES dynamic per destination
  function ensureLineBlocks(){
    const container = document.getElementById('lines-container');
    // jika sudah ada blok (POST invalid), biarkan
    if(container.querySelector('[id$="-tbody"]')) return;

    const total = parseInt(document.querySelector('input[name="dest-TOTAL_FORMS"]').value || '0');
    for(let i=0;i<total;i++){
      // skip dest yang dihapus
      const del = document.querySelector(`input[name="dest-${i}-DELETE"]`);
      if(del && del.checked) continue;

      const wrap = document.createElement('div');
      wrap.className = 'border rounded p-3 mb-3';
      const prefix = `line-${i}`;

      // header + tombol add
      const head = document.createElement('div');
      head.className = 'd-flex justify-content-between align-items-center mb-2';
      head.innerHTML = `<div class="fw-bold">Destination #${i+1}</div>
        <button type="button" class="btn btn-sm btn-outline-primary" onclick="addLine('${prefix}')">+ Add Line</button>`;
      wrap.appendChild(head);

      // management form (TOTAL_FORMS etc.)
      wrap.insertAdjacentHTML('beforeend', `
        <input type="hidden" name="${prefix}-TOTAL_FORMS" value="1">
        <input type="hidden" name="${prefix}-INITIAL_FORMS" value="0">
        <input type="hidden" name="${prefix}-MIN_NUM_FORMS" value="0">
        <input type="hidden" name="${prefix}-MAX_NUM_FORMS" value="1000">
      `);

      // table
      const table = document.createElement('div');
      table.className = 'table-responsive';
      table.innerHTML = `
        <table class="table align-middle">
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

      // tambahkan 1 baris awal
      addLine(prefix);
    }
  }

  function addLine(prefix){
    const tbody = document.getElementById(`${prefix}-tbody`);
    const totalInput = document.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`);
    let idx = parseInt(totalInput.value || '0');
    const tpl = document.getElementById('line-empty-row').content.cloneNode(true);
    tpl.querySelectorAll('[name]').forEach(el=>{
      el.name = el.name.replace('__PREFIX__', prefix).replace('__IDX__', idx);
    });
    tbody.appendChild(tpl);
    totalInput.value = idx + 1;
  }
</script>
{% endblock %}
""", encoding="utf-8")
print("  ✓ template created")

print("\nSelesai ✅")
print("- Route baru: /sales/quotations/wizard/new/")
print("- Simpan hanya di akhir (atomic). Kalau gagal validasi, nomor tidak terpakai.")
print("- Jika Anda pakai auto-number di models.save(), penomoran dilakukan saat commit final.")
