import os, sys, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan skrip ini dari ROOT project (yang ada manage.py)."

SALES = ROOT / "sales"
TPL  = SALES / "templates" / "sales"
BASE_HTML = SALES / "templates" / "base.html"
FORMS = SALES / "forms.py"
VIEWS = SALES / "views.py"
URLS  = SALES / "urls.py"
FORM_TPL = TPL / "quotation_form.html"

def backup(p: pathlib.Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + ".bak")
        if not bak.exists():
            bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  • backup: {p} -> {bak}")

def ensure_dirs():
    (SALES / "templates" / "sales").mkdir(parents=True, exist_ok=True)

def upsert_forms():
    print("\n[FORMS] updating sales/forms.py ...")
    ensure_dirs()
    content = f'''\
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, QuotationDestination, QuotationLine

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        # number sengaja tidak ditampilkan; gunakan auto-number di models.save() jika ada
        fields = ["date", "customer", "origin", "cargo_desc", "validity_date", "payment_terms", "notes"]
        widgets = {{
            "date": forms.DateInput(attrs={{"class":"form-control datepicker","placeholder":"YYYY-MM-DD"}}),
            "validity_date": forms.DateInput(attrs={{"class":"form-control datepicker","placeholder":"YYYY-MM-DD"}}),
            "customer": forms.Select(attrs={{"class":"form-select"}}),
            "origin": forms.TextInput(attrs={{"class":"form-control"}}),
            "cargo_desc": forms.TextInput(attrs={{"class":"form-control"}}),
            "payment_terms": forms.TextInput(attrs={{"class":"form-control"}}),
            "notes": forms.Textarea(attrs={{"class":"form-control","rows":3}}),
        }}

class _DestinationFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = [f for f in self.forms if not f.cleaned_data.get('DELETE', False)
                  and any(f.cleaned_data.get(k) for k in ['destination','incoterms','transit_time_days','schedule','extra_notes'])]
        if len(active) < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal harus ada 1 destination pada quotation ini.")

DestinationFormSet = inlineformset_factory(
    Quotation,
    QuotationDestination,
    formset=_DestinationFormSet,
    fields=["destination","incoterms","transit_time_days","schedule","extra_notes"],
    extra=2,
    can_delete=True
)

class _LineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = 0
        for f in self.forms:
            if f.cleaned_data.get('DELETE', False):
                continue
            if any(f.cleaned_data.get(k) for k in ['charge_type','description','unit','qty','rate','currency']):
                active += 1
        if active < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal 1 line pada setiap destination.")

LineFormSet = inlineformset_factory(
    QuotationDestination,
    QuotationLine,
    formset=_LineFormSet,
    fields=["charge_type","description","unit","qty","rate","currency"],
    extra=3,
    can_delete=True
)
'''
    backup(FORMS)
    FORMS.write_text(content, encoding="utf-8")
    print("  ✓ forms.py written")

def upsert_views():
    print("\n[VIEWS] patching sales/views.py ...")
    ensure_dirs()
    if not VIEWS.exists():
        VIEWS.write_text("", encoding="utf-8")
    txt = VIEWS.read_text(encoding="utf-8")
    backup(VIEWS)

    # Ensure imports
    if "from django.shortcuts" in txt:
        if "redirect" not in txt:
            txt = re.sub(r"from django\.shortcuts import ([^\n]+)",
                         lambda m: f"from django.shortcuts import {m.group(1)}, redirect" if "redirect" not in m.group(1) else m.group(0),
                         txt)
    else:
        txt = "from django.shortcuts import render, get_object_or_404, redirect\n" + txt

    if "from django.views.generic" in txt:
        if "CreateView" not in txt:
            txt = re.sub(r"from django\.views\.generic import ([^\n]+)",
                         lambda m: f"from django.views.generic import {m.group(1)}, CreateView" if "CreateView" not in m.group(1) else m.group(0),
                         txt)
    else:
        txt = "from django.views.generic import ListView, DetailView, CreateView\n" + txt

    if "from django.urls import reverse_lazy" not in txt:
        if "from django.urls import" in txt:
            txt = re.sub(r"from django\.urls import ([^\n]+)",
                         lambda m: f"from django.urls import {m.group(1)}, reverse_lazy",
                         txt)
        else:
            txt = "from django.urls import reverse_lazy, reverse\n" + txt

    if "from .forms import QuotationForm" not in txt:
        if "from .forms import" in txt:
            txt = re.sub(r"from \.forms import ([^\n]+)",
                         lambda m: f"from .forms import {m.group(1)}, QuotationForm" if "QuotationForm" not in m.group(1) else m.group(0),
                         txt)
        else:
            txt = "from .forms import QuotationForm\n" + txt

    if "from .models import Quotation" not in txt:
        if "from .models import" in txt:
            txt = re.sub(r"from \.models import ([^\n]+)",
                         lambda m: f"from .models import {m.group(1)}, Quotation" if "Quotation" not in m.group(1) else m.group(0),
                         txt)
        else:
            txt = "from .models import Quotation\n" + txt

    # Ensure QuotationListView / DetailView exist minimally
    if "class QuotationListView" not in txt:
        txt += '''

class QuotationListView(ListView):
    model = Quotation
    template_name = "sales/quotation_list.html"
    context_object_name = "quotations"
    paginate_by = 20
'''
    if "class QuotationDetailView" not in txt:
        txt += '''

class QuotationDetailView(DetailView):
    model = Quotation
    template_name = "sales/quotation_detail.html"
    context_object_name = "quotation"
'''

    # Add/replace QuotationCreateView
    pattern = r"class\s+QuotationCreateView\s*\(CreateView\):[\s\S]*?(?=\nclass|\Z)"
    block = '''
class QuotationCreateView(CreateView):
    model = Quotation
    form_class = QuotationForm
    template_name = "sales/quotation_form.html"

    def form_valid(self, form):
        q = form.save()
        return redirect("sales:quotation_edit_destinations", pk=q.pk)
'''
    if re.search(pattern, txt):
        txt = re.sub(pattern, block, txt)
    else:
        txt += "\n" + block + "\n"

    VIEWS.write_text(txt, encoding="utf-8")
    print("  ✓ views.py patched")

def upsert_urls():
    print("\n[URLS] patching sales/urls.py ...")
    ensure_dirs()
    if not URLS.exists():
        URLS.write_text("", encoding="utf-8")
    txt = URLS.read_text(encoding="utf-8")
    backup(URLS)

    if "from django.urls import path" not in txt:
        txt = "from django.urls import path\n" + txt

    # import views
    need_imports = ["QuotationListView", "QuotationDetailView", "QuotationCreateView"]
    if "from .views import" in txt:
        for name in need_imports:
            if name not in txt:
                txt = re.sub(r"from \.views import ([^\n]+)",
                             lambda m: f"from .views import {m.group(1)}, {name}",
                             txt, count=1)
    else:
        txt = "from .views import QuotationListView, QuotationDetailView, QuotationCreateView\n" + txt

    if "app_name" not in txt:
        txt += "\napp_name = 'sales'\n"

    if "urlpatterns" not in txt:
        txt += "\nurlpatterns = []\n"

    # ensure paths exist
    def ensure_path(code, name):
        nonlocal txt
        if name not in txt:
            txt = re.sub(r"urlpatterns\s*=\s*\[",
                         f"urlpatterns = [\n    {code},",
                         txt, count=1)

    ensure_path("path('quotations/', QuotationListView.as_view(), name='quotation_list')", "quotation_list")
    ensure_path("path('quotations/new/', QuotationCreateView.as_view(), name='quotation_create')", "quotation_create")
    ensure_path("path('quotations/<int:pk>/', QuotationDetailView.as_view(), name='quotation_detail')", "quotation_detail")

    URLS.write_text(txt, encoding="utf-8")
    print("  ✓ urls.py patched")

def upsert_template_form():
    print("\n[TEMPLATE] writing templates/sales/quotation_form.html ...")
    ensure_dirs()
    backup(FORM_TPL)
    FORM_TPL.write_text("""\
{% extends "base.html" %}
{% block title %}New Quotation{% endblock %}

{% block content %}
<div class="container-fluid">
  <div class="card shadow-sm rounded-2xl">
    <div class="card-header d-flex justify-content-between align-items-center">
      <h3 class="card-title">Step 1/2 — Quotation Header</h3>
      <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_list' %}">Back</a>
    </div>
    <div class="card-body">
      <form method="post" novalidate>
        {% csrf_token %}

        <div class="row g-3">
          <div class="col-md-4">
            <label class="form-label">Date</label>
            {{ form.date }}
            {% for err in form.date.errors %}<div class="text-danger small">{{ err }}</div>{% endfor %}
          </div>
          <div class="col-md-4">
            <label class="form-label">Validity Date</label>
            {{ form.validity_date }}
            {% for err in form.validity_date.errors %}<div class="text-danger small">{{ err }}</div>{% endfor %}
          </div>
          <div class="col-md-4">
            <label class="form-label">Customer</label>
            {{ form.customer }}
            {% for err in form.customer.errors %}<div class="text-danger small">{{ err }}</div>{% endfor %}
          </div>

          <div class="col-md-6">
            <label class="form-label">Origin</label>
            {{ form.origin }}
            {% for err in form.origin.errors %}<div class="text-danger small">{{ err }}</div>{% endfor %}
          </div>
          <div class="col-md-6">
            <label class="form-label">Cargo Description</label>
            {{ form.cargo_desc }}
            {% for err in form.cargo_desc.errors %}<div class="text-danger small">{{ err }}</div>{% endfor %}
          </div>

          <div class="col-md-6">
            <label class="form-label">Payment Terms</label>
            {{ form.payment_terms }}
            {% for err in form.payment_terms.errors %}<div class="text-danger small">{{ err }}</div>{% endfor %}
          </div>
          <div class="col-md-6">
            <label class="form-label">Notes</label>
            {{ form.notes }}
            {% for err in form.notes.errors %}<div class="text-danger small">{{ err }}</div>{% endfor %}
          </div>
        </div>

        {% if form.non_field_errors %}
          <div class="alert alert-danger mt-3">
            {% for err in form.non_field_errors %}<div>{{ err }}</div>{% endfor %}
          </div>
        {% endif %}

        <div class="mt-4 d-flex gap-2">
          <button class="btn btn-primary" type="submit">
            Save & Continue to Destinations
          </button>
          <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_list' %}">Cancel</a>
        </div>
      </form>
    </div>
  </div>
</div>
{% endblock %}
""", encoding="utf-8")
    print("  ✓ quotation_form.html written")

def patch_base_for_flatpickr():
    print("\n[BASE.HTML] ensuring Flatpickr assets ...")
    ensure_dirs()
    if not BASE_HTML.exists():
        print(f"  • base.html tidak ditemukan di {BASE_HTML}. Lewati (optional).")
        return
    txt = BASE_HTML.read_text(encoding="utf-8")
    backup(BASE_HTML)
    changed = False
    if "flatpickr.min.css" not in txt:
        txt = txt.replace("</head>", '  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">\n</head>')
        changed = True
    if "cdn.jsdelivr.net/npm/flatpickr" not in txt:
        txt = txt.replace("</body>", '  <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>\n</body>')
        changed = True
    if "flatpickr(\".datepicker\"" not in txt:
        txt = txt.replace("</body>", """  <script>
  document.addEventListener("DOMContentLoaded", function() {
    if (window.flatpickr) {
      flatpickr(".datepicker", { dateFormat: "Y-m-d", allowInput: true });
    }
  });
  </script>
</body>""")
        changed = True
    if changed:
        BASE_HTML.write_text(txt, encoding="utf-8")
        print("  ✓ Flatpickr added to base.html")
    else:
        print("  ✓ base.html already has Flatpickr")

def main():
    print("== CargoChains Quotation Wizard (Step-1 + Datepicker) ==")
    ensure_dirs()
    upsert_forms()
    upsert_views()
    upsert_urls()
    upsert_template_form()
    patch_base_for_flatpickr()
    print("\nSelesai ✅\n- Jalankan server dan buka /sales/quotations/new/\n- Jika error import, restart server setelah perubahan file.")

if __name__ == "__main__":
    main()
