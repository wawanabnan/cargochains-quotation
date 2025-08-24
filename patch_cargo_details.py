from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
MODELS = APP / "models.py"
FORMS = APP / "forms.py"
VIEWS = APP / "views.py"
URLS = APP / "urls.py"
TPL_DIR = APP / "templates" / "sales"
TPL_DIR.mkdir(parents=True, exist_ok=True)
TPL_CARGO_DETAIL = TPL_DIR / "cargo_detail.html"
TPL_QUO_DETAIL = TPL_DIR / "quotation_detail.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup {p.name} -> {b.name}")

print("== Patch: Cargo details (shipper/consignee) + view/edit pages ==")

# 1) models.py: tambah shipper/consignee/notify di Cargo
assert MODELS.exists(), "models.py tidak ditemukan"
backup(MODELS)
m = MODELS.read_text(encoding="utf-8")
changed = False

if "class Cargo(models.Model):" in m and "shipper" not in m:
    m = re.sub(
        r"(class\s+Cargo\(models\.Model\):[\s\S]*?extra_notes\s*=\s*models\.TextField\(blank=True\)\s*\n)",
        r"\1    # Parties\n"
        r"    shipper = models.CharField(max_length=200, blank=True)\n"
        r"    consignee = models.CharField(max_length=200, blank=True)\n"
        r"    notify_party = models.CharField(max_length=200, blank=True)\n",
        m, count=1
    )
    changed = True
    print("✓ models.py: Cargo.add(shipper, consignee, notify_party)")

if changed:
    MODELS.write_text(m, encoding="utf-8")
else:
    print("• models.py sudah ada fields tersebut / tidak perlu diubah")

# 2) forms.py: tambah CargoForm untuk edit; extend CargoFormSet di wizard (opsional tampil)
assert FORMS.exists(), "forms.py tidak ditemukan"
backup(FORMS)
f = FORMS.read_text(encoding="utf-8")
changed = False

if "class CargoForm(" not in f:
    insert_point = f.rfind("ChargeFormSetFactory")
    if insert_point == -1:
        insert_point = len(f)
    addon = (
        "\n\n# ---- Single Cargo Form (detail/edit) ----\n"
        "class CargoForm(forms.ModelForm):\n"
        "    class Meta:\n"
        "        model = Cargo\n"
        "        fields = [\n"
        "            'description','package_type','qty','weight_kg','volume_cbm',\n"
        "            'origin','destination','shipper','consignee','notify_party','extra_notes'\n"
        "        ]\n"
        "        widgets = {\n"
        "            'description': forms.TextInput(attrs={'class':'form-control'}),\n"
        "            'package_type': forms.TextInput(attrs={'class':'form-control'}),\n"
        "            'qty': forms.NumberInput(attrs={'class':'form-control','step':'0.001'}),\n"
        "            'weight_kg': forms.NumberInput(attrs={'class':'form-control','step':'0.001'}),\n"
        "            'volume_cbm': forms.NumberInput(attrs={'class':'form-control','step':'0.001'}),\n"
        "            'origin': forms.TextInput(attrs={'class':'form-control'}),\n"
        "            'destination': forms.TextInput(attrs={'class':'form-control'}),\n"
        "            'shipper': forms.TextInput(attrs={'class':'form-control'}),\n"
        "            'consignee': forms.TextInput(attrs={'class':'form-control'}),\n"
        "            'notify_party': forms.TextInput(attrs={'class':'form-control'}),\n"
        "            'extra_notes': forms.Textarea(attrs={'class':'form-control','rows':3}),\n"
        "        }\n"
    )
    f = f + addon
    changed = True
    print("✓ forms.py: add CargoForm")

# (opsional) tampilkan shipper/consignee di CargoFormSet (wizard) jika fields list ada
if "CargoFormSet" in f and "shipper" not in f:
    f = re.sub(
        r"(CargoFormSet\s*=\s*inlineformset_factory\([\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
        lambda m: m.group(1) + (m.group(2)+", 'shipper','consignee','notify_party'") + m.group(3),
        f, count=1
    )
    changed = True
    print("✓ forms.py: CargoFormSet fields ditambah shipper/consignee/notify_party")

if changed:
    FORMS.write_text(f, encoding="utf-8")
else:
    print("• forms.py tidak berubah")

# 3) views.py: CargoDetailView & CargoUpdateView
assert VIEWS.exists(), "views.py tidak ditemukan"
backup(VIEWS)
v = VIEWS.read_text(encoding="utf-8")
changed = False

if "class CargoDetailView" not in v:
    v += (
        "\n\nfrom django.views.generic import DetailView, UpdateView\n"
        "from django.urls import reverse\n"
        "from .models import Cargo\n"
        "from .forms import CargoForm\n"
        "\n"
        "class CargoDetailView(DetailView):\n"
        "    model = Cargo\n"
        "    template_name = 'sales/cargo_detail.html'\n"
        "    context_object_name = 'cargo'\n"
        "\n"
        "class CargoUpdateView(UpdateView):\n"
        "    model = Cargo\n"\
        "    form_class = CargoForm\n"
        "    template_name = 'sales/cargo_detail.html'\n"
        "\n"
        "    def get_success_url(self):\n"
        "        return reverse('sales:cargo_detail', args=[self.object.pk])\n"
    )
    changed = True
    print("✓ views.py: add CargoDetailView & CargoUpdateView")

if changed:
    VIEWS.write_text(v, encoding="utf-8")
else:
    print("• views.py tidak berubah")

# 4) urls.py: tambahkan routes cargo detail/edit
assert URLS.exists(), "urls.py tidak ditemukan"
backup(URLS)
u = URLS.read_text(encoding="utf-8")
changed = False
if "cargo_detail" not in u or "cargo_edit" not in u:
    if "from . import views" not in u:
        u = "from . import views\n" + u
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('cargos/<int:pk>/', views.CargoDetailView.as_view(), name='cargo_detail'),\n"
        "    path('cargos/<int:pk>/edit/', views.CargoUpdateView.as_view(), name='cargo_edit'),"
    )
    changed = True
    print("✓ urls.py: add /cargos/<id>/ and /cargos/<id>/edit/")

if changed:
    URLS.write_text(u, encoding="utf-8")
else:
    print("• urls.py tidak berubah")

# 5) cargo_detail.html: template reuse (view & edit)
backup(TPL_CARGO_DETAIL)
if not TPL_CARGO_DETAIL.exists():
    TPL_CARGO_DETAIL.write_text(
"""{% extends "base.html" %}
{% block title %}Cargo {{ cargo.pk }}{% endblock %}
{% block content %}
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">Cargo {{ cargo.description }} <span class="text-body-secondary">({{ cargo.origin }} → {{ cargo.destination }})</span></h2>
    <div class="d-flex gap-2">
      <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_detail' cargo.quotation.pk %}">Back to Quotation</a>
      {% if view.action == 'edit' %}{% else %}
      <a class="btn btn-primary" href="{% url 'sales:cargo_edit' cargo.pk %}">Edit</a>
      {% endif %}
    </div>
  </div>

  {% if form %}
  <form method="post" class="card shadow-sm">
    {% csrf_token %}
    <div class="card-body">
      <div class="row g-3">
        <div class="col-md-6">
          <label class="form-label">Description</label>
          {{ form.description }}
        </div>
        <div class="col-md-3">
          <label class="form-label">Package</label>
          {{ form.package_type }}
        </div>
        <div class="col-md-3">
          <label class="form-label">Qty</label>
          {{ form.qty }}
        </div>
        <div class="col-md-4">
          <label class="form-label">Weight (kg)</label>
          {{ form.weight_kg }}
        </div>
        <div class="col-md-4">
          <label class="form-label">Volume (cbm)</label>
          {{ form.volume_cbm }}
        </div>
        <div class="col-md-4">
          <label class="form-label">Unit Route</label>
          <div class="input-group">
            {{ form.origin }}
            <span class="input-group-text">→</span>
            {{ form.destination }}
          </div>
        </div>
        <div class="col-md-4">
          <label class="form-label">Shipper</label>
          {{ form.shipper }}
        </div>
        <div class="col-md-4">
          <label class="form-label">Consignee</label>
          {{ form.consignee }}
        </div>
        <div class="col-md-4">
          <label class="form-label">Notify Party</label>
          {{ form.notify_party }}
        </div>
        <div class="col-12">
          <label class="form-label">Extra Notes</label>
          {{ form.extra_notes }}
        </div>
      </div>
    </div>
    <div class="card-footer d-flex justify-content-end gap-2">
      <a class="btn btn-outline-secondary" href="{% url 'sales:cargo_detail' cargo.pk %}">Cancel</a>
      <button class="btn btn-success" type="submit">Save</button>
    </div>
  </form>
  {% else %}
  <div class="row g-3">
    <div class="col-md-6">
      <div class="border rounded p-3">
        <div class="fw-bold">Parties</div>
        <div class="mt-2"><strong>Shipper:</strong> {{ cargo.shipper|default:"-" }}</div>
        <div><strong>Consignee:</strong> {{ cargo.consignee|default:"-" }}</div>
        <div><strong>Notify:</strong> {{ cargo.notify_party|default:"-" }}</div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="border rounded p-3">
        <div class="fw-bold">Specs</div>
        <div class="mt-2">Package: {{ cargo.package_type|default:"-" }}</div>
        <div>Qty: {{ cargo.qty|floatformat:3 }}</div>
        <div>Weight: {{ cargo.weight_kg|floatformat:3 }} kg</div>
        <div>Volume: {{ cargo.volume_cbm|floatformat:3 }} cbm</div>
        {% if cargo.extra_notes %}<div class="mt-2"><em>{{ cargo.extra_notes }}</em></div>{% endif %}
      </div>
    </div>
  </div>

  <div class="mt-3">
    <a class="btn btn-primary" href="{% url 'sales:cargo_edit' cargo.pk %}">Edit Cargo</a>
  </div>
  {% endif %}
</div>
{% endblock %}
""", encoding="utf-8")
    print("✓ templates: cargo_detail.html dibuat")
else:
    print("• templates: cargo_detail.html sudah ada (tidak diubah)")

# 6) quotation_detail.html: tambah tombol View/Edit pada setiap kartu cargo
if TPL_QUO_DETAIL.exists():
    backup(TPL_QUO_DETAIL)
    d = TPL_QUO_DETAIL.read_text(encoding="utf-8")
    changed = False

    if "href=\"{% url 'sales:cargo_detail' cargo.pk %}\"" not in d:
        d = d.replace(
            '<div class="card-header bg-body-secondary">',
            '<div class="card-header bg-body-secondary">'
        )
        # tambahkan tombol di header card (kanan)
        d = d.replace(
            '</div>\n    </div>\n    <div class="card-body p-0">',
            '        <div>\n'
            '          <a class="btn btn-sm btn-outline-primary" href="{% url \'sales:cargo_detail\' cargo.pk %}">View</a>\n'
            '          <a class="btn btn-sm btn-outline-success" href="{% url \'sales:cargo_edit\' cargo.pk %}">Edit</a>\n'
            '        </div>\n'
            '      </div>\n    </div>\n    <div class="card-body p-0">'
        )
        changed = True

    if changed:
        TPL_QUO_DETAIL.write_text(d, encoding="utf-8")
        print("✓ quotation_detail.html: tombol View/Edit cargo ditambahkan")
    else:
        print("• quotation_detail.html sudah ada tombolnya / tidak diubah")
else:
    print("• templates: quotation_detail.html tidak ditemukan (lewati)")

print("\nSelesai ✅")
print("Jalankan:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("  python manage.py runserver")
