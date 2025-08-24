import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari root project (yang ada manage.py)."

SALES = ROOT / "sales"
FORMS = SALES / "forms.py"
VIEWS = SALES / "views.py"
TPL_DIR = SALES / "templates" / "sales"
FORM_TPL = TPL_DIR / "quotation_form.html"

def backup(path: pathlib.Path):
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  • backup {path} -> {bak}")

def ensure_dirs():
    TPL_DIR.mkdir(parents=True, exist_ok=True)

def write_forms_py():
    """Tulis ulang forms.py: header-only, HTML5 date, default today/+14 hari, plus formset destinasi & line."""
    from_text = f'''\
from datetime import date, timedelta
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, QuotationDestination, QuotationLine

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        # Header only — tidak ada field milik destination/line
        fields = ["date", "customer", "origin", "cargo_desc", "validity_date", "payment_terms", "notes"]
        widgets = {{
            # HTML5 date input (native calendar)
            "date": forms.DateInput(attrs={{"type": "date", "class": "form-control"}}),
            "validity_date": forms.DateInput(attrs={{"type": "date", "class": "form-control"}}),
            "customer": forms.Select(attrs={{"class": "form-select"}}),
            "origin": forms.TextInput(attrs={{"class": "form-control"}}),
            "cargo_desc": forms.TextInput(attrs={{"class": "form-control"}}),
            "payment_terms": forms.TextInput(attrs={{"class": "form-control"}}),
            "notes": forms.Textarea(attrs={{"class": "form-control", "rows": 3}}),
        }}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # default saat create
        if not self.instance.pk:
            self.fields["date"].initial = date.today()
            self.fields["validity_date"].initial = date.today() + timedelta(days=14)

# ---- Destination must >= 1
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

# ---- Line per destination must >= 1
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
    print("\n[FORMS] menulis sales/forms.py ...")
    backup(FORMS)
    FORMS.write_text(from_text, encoding="utf-8")
    print("  ✓ forms.py OK")

def patch_views_py():
    """Pastikan QuotationCreateView pakai QuotationForm + redirect ke edit-destinations; impor redirect sudah ada."""
    print("\n[VIEWS] patch views.py ...")
    if not VIEWS.exists():
        raise SystemExit("views.py tidak ditemukan. Pastikan app 'sales' ada.")
    txt = VIEWS.read_text(encoding="utf-8")
    backup(VIEWS)

    # Pastikan import redirect
    if "from django.shortcuts" in txt:
        if "redirect" not in txt:
            txt = re.sub(r"from django\.shortcuts import ([^\n]+)",
                         lambda m: f"from django.shortcuts import {m.group(1)}, redirect" if "redirect" not in m.group(1) else m.group(0),
                         txt)
    else:
        txt = "from django.shortcuts import render, get_object_or_404, redirect\n" + txt

    # Pastikan import CreateView
    if "from django.views.generic" in txt:
        if "CreateView" not in txt:
            txt = re.sub(r"from django\.views\.generic import ([^\n]+)",
                         lambda m: f"from django.views.generic import {m.group(1)}, CreateView" if "CreateView" not in m.group(1) else m.group(0),
                         txt)
    else:
        txt = "from django.views.generic import ListView, DetailView, CreateView\n" + txt

    # Pastikan import QuotationForm
    if "from .forms import QuotationForm" not in txt:
        if "from .forms import" in txt:
            txt = re.sub(r"from \.forms import ([^\n]+)",
                         lambda m: f"from .forms import {m.group(1)}, QuotationForm" if "QuotationForm" not in m.group(1) else m.group(0),
                         txt)
        else:
            txt = "from .forms import QuotationForm\n" + txt

    # Tambal/replace QuotationCreateView
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
    print("  ✓ views.py OK")

def write_form_template():
    """Ganti template header form agar rapi & hanya field header."""
    print("\n[TEMPLATE] menulis templates/sales/quotation_form.html ...")
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
          <button class="btn btn-primary" type="submit">Save & Continue to Destinations</button>
          <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_list' %}">Cancel</a>
        </div>
      </form>
    </div>
  </div>
</div>
{% endblock %}
""", encoding="utf-8")
    print("  ✓ quotation_form.html OK")

def main():
    print("== Update Quotation Header & Datepicker (HTML5) ==")
    ensure_dirs()
    write_forms_py()
    patch_views_py()
    write_form_template()
    print("\nSelesai ✅")
    print("- Buka /sales/quotations/new/ → Date & Validity sudah pakai picker HTML5 + default today/+14 hari.")
    print("- Destination diisi di langkah berikutnya (bukan di header).")

if __name__ == "__main__":
    main()
