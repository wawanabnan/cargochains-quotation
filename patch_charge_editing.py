from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
FORMS = APP / "forms.py"
VIEWS = APP / "views.py"
URLS  = APP / "urls.py"
TPL   = APP / "templates" / "sales"
TPL.mkdir(parents=True, exist_ok=True)
TPL_CHG = TPL / "cargo_charges_edit.html"
TPL_CARGO_DETAIL = TPL / "cargo_detail.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup {p.name} -> {b.name}")

print("== Patch: View & Edit Line Charges per Cargo ==")

# 1) Ensure ChargeFormSetFactory exists in forms.py (from earlier rebuild)
assert FORMS.exists(), "forms.py not found"
backup(FORMS)
f = FORMS.read_text(encoding="utf-8")
if "def ChargeFormSetFactory" not in f:
    # minimal factory fallback, in case belum ada
    insert = (
        "\n\nfrom .models import Cargo, CargoCharge\n"
        "from django.forms import inlineformset_factory, BaseInlineFormSet\n"
        "class _ChargeFormSet(BaseInlineFormSet):\n"
        "    def clean(self):\n"
        "        super().clean()\n"
        "        active = 0\n"
        "        for fm in self.forms:\n"
        "            if fm.cleaned_data.get('DELETE', False):\n"
        "                continue\n"
        "            if any(fm.cleaned_data.get(k) for k in ['charge_type','description','unit','qty','rate','currency']):\n"
        "                active += 1\n"
        "        if active < 1:\n"
        "            from django.core.exceptions import ValidationError\n"
        "            raise ValidationError('Minimal 1 charge untuk cargo ini.')\n"
        "\n"
        "def ChargeFormSetFactory():\n"
        "    return inlineformset_factory(\n"
        "        Cargo, CargoCharge,\n"
        "        formset=_ChargeFormSet,\n"
        "        fields=['charge_type','description','unit','qty','rate','currency'],\n"
        "        extra=1, can_delete=True\n"
        "    )\n"
    )
    f += insert
    FORMS.write_text(f, encoding="utf-8")
    print("✓ forms.py: ChargeFormSetFactory ditambahkan (fallback)")

# 2) Add views to edit charges per cargo (inline formset) + single charge edit
assert VIEWS.exists(), "views.py not found"
backup(VIEWS)
v = VIEWS.read_text(encoding="utf-8")

if "def cargo_charges_edit(" not in v:
    add = (
        "\n\nfrom django.shortcuts import get_object_or_404\n"
        "from django.contrib import messages\n"
        "from .models import Cargo, CargoCharge\n"
        "from .forms import ChargeFormSetFactory\n"
        "\n"
        "def cargo_charges_edit(request, cargo_id: int):\n"
        "    cargo = get_object_or_404(Cargo.objects.select_related('quotation'), pk=cargo_id)\n"
        "    CFSF = ChargeFormSetFactory()\n"
        "    if request.method == 'POST':\n"
        "        formset = CFSF(request.POST, instance=cargo, prefix='chg')\n"
        "        if formset.is_valid():\n"
        "            formset.save()\n"
        "            messages.success(request, 'Charges updated.')\n"
        "            return redirect('sales:cargo_charges_edit', cargo_id=cargo.pk)\n"
        "    else:\n"
        "        formset = CFSF(instance=cargo, prefix='chg')\n"
        "    return render(request, 'sales/cargo_charges_edit.html', {\n"
        "        'cargo': cargo,\n"
        "        'quotation': cargo.quotation,\n"
        "        'formset': formset,\n"
        "    })\n"
        "\n"
        "from django.views.generic import UpdateView\n"
        "class ChargeUpdateView(UpdateView):\n"
        "    model = CargoCharge\n"
        "    fields = ['charge_type','description','unit','qty','rate','currency']\n"
        "    template_name = 'sales/cargo_charges_edit.html'\n"
        "    context_object_name = 'charge'\n"
        "    def get_success_url(self):\n"
        "        return self.request.GET.get('next') or self.object.cargo and self.object.cargo.get_absolute_url() or '/'  \n"
    )
    # add helper: get_absolute_url on Cargo if not exists
    from pathlib import Path
    models_path = APP / "models.py"
    if models_path.exists():
        m = models_path.read_text(encoding="utf-8")
        if "def get_absolute_url(self):" not in m and "class Cargo(" in m:
            m = re.sub(
                r"(class\s+Cargo\(models\.Model\):[\s\S]*?__str__\([^\)]*\):[^\n]*\n\s*return[^\n]*\n)",
                r"\1\n    def get_absolute_url(self):\n        from django.urls import reverse\n        return reverse('sales:cargo_detail', args=[self.pk])\n",
                m, count=1
            )
            models_path.write_text(m, encoding="utf-8")
            print("✓ models.py: Cargo.get_absolute_url() ditambahkan")
    v += add
    VIEWS.write_text(v, encoding="utf-8")
    print("✓ views.py: cargo_charges_edit & ChargeUpdateView ditambahkan")
else:
    print("• views.py sudah punya cargo_charges_edit")

# 3) routes
assert URLS.exists(), "urls.py not found"
backup(URLS)
u = URLS.read_text(encoding="utf-8")
changed = False
if "cargo_charges_edit" not in u:
    if "from . import views" not in u:
        u = "from . import views\n" + u
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('cargos/<int:cargo_id>/charges/', views.cargo_charges_edit, name='cargo_charges_edit'),\n"
        "    path('charges/<int:pk>/edit/', views.ChargeUpdateView.as_view(), name='charge_edit'),"
    )
    changed = True
if changed:
    URLS.write_text(u, encoding="utf-8")
    print("✓ urls.py: routes charges ditambahkan")
else:
    print("• urls.py sudah ada routes-nya")

# 4) template cargo_charges_edit.html
backup(TPL_CHG)
if not TPL_CHG.exists():
    TPL_CHG.write_text(
"""{% extends "base.html" %}
{% block title %}Charges — Cargo {{ cargo.pk }}{% endblock %}
{% block content %}
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h2 class="mb-0">
      Charges — {{ cargo.description }}
      <span class="text-body-secondary">({{ cargo.origin }} → {{ cargo.destination }})</span>
    </h2>
    <div class="d-flex gap-2">
      <a class="btn btn-outline-secondary" href="{% url 'sales:cargo_detail' cargo.pk %}">Back to Cargo</a>
      <a class="btn btn-outline-primary" href="{% url 'sales:quotation_detail' quotation.pk %}">Back to Quotation</a>
    </div>
  </div>

  <form method="post" class="card shadow-sm">
    {% csrf_token %}
    <div class="card-body">
      {{ formset.management_form }}
      <div class="table-responsive">
        <table class="table align-middle">
          <thead class="table-light">
            <tr>
              <th>Charge</th><th>Description</th><th>Unit</th>
              <th class="text-end">Qty</th><th class="text-end">Rate</th>
              <th>Curr</th><th>Delete</th>
            </tr>
          </thead>
          <tbody id="chg-tbody">
            {% for f in formset %}
            <tr>
              <td>{{ f.charge_type }}</td>
              <td>{{ f.description }}</td>
              <td>{{ f.unit }}</td>
              <td class="text-end">{{ f.qty }}</td>
              <td class="text-end">{{ f.rate }}</td>
              <td>{{ f.currency }}</td>
              <td class="text-center">{{ f.DELETE }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <button type="button" class="btn btn-outline-primary" onclick="addCharge()">+ Add Charge</button>
    </div>
    <div class="card-footer d-flex justify-content-end gap-2">
      <button class="btn btn-success" type="submit">Save Changes</button>
    </div>
  </form>
</div>

<script>
  function addCharge(){
    const totalInput = document.querySelector('input[name="chg-TOTAL_FORMS"]');
    let idx = parseInt(totalInput.value || '0');
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><select name="chg-${idx}-charge_type" class="form-select">
            <option value="">-</option>
            <option value="FREIGHT">FREIGHT</option>
            <option value="ORIGIN">ORIGIN</option>
            <option value="DEST">DEST</option>
            <option value="DOC">DOC</option>
            <option value="OTHER">OTHER</option>
          </select></td>
      <td><input name="chg-${idx}-description" class="form-control"></td>
      <td><input name="chg-${idx}-unit" class="form-control" placeholder="per MT / per CBM / per SHPT"></td>
      <td class="text-end"><input type="number" step="0.001" name="chg-${idx}-qty" class="form-control text-end" value="1"></td>
      <td class="text-end"><input type="number" step="0.0001" name="chg-${idx}-rate" class="form-control text-end"></td>
      <td><input name="chg-${idx}-currency" class="form-control" value="USD"></td>
      <td class="text-center"><input type="checkbox" name="chg-${idx}-DELETE" class="form-check-input"></td>
      <input type="hidden" name="chg-${idx}-id">
    `;
    document.getElementById('chg-tbody').appendChild(row);
    totalInput.value = idx + 1;
  }
</script>
{% endblock %}
""",
        encoding="utf-8"
    )
    print("✓ template: cargo_charges_edit.html dibuat")
else:
    print("• template cargo_charges_edit.html sudah ada")

# 5) Tambah tombol "Charges" di cargo_detail (kalau belum)
if TPL_CARGO_DETAIL.exists():
    backup(TPL_CARGO_DETAIL)
    cd = TPL_CARGO_DETAIL.read_text(encoding="utf-8")
    if "cargo_charges_edit" not in cd:
        cd = cd.replace(
            'href="{% url \'sales:cargo_edit\' cargo.pk %}">Edit</a>',
            'href="{% url \'sales:cargo_edit\' cargo.pk %}">Edit</a>\n'
            '      <a class="btn btn-sm btn-outline-secondary" href="{% url \'sales:cargo_charges_edit\' cargo.pk %}">Charges</a>'
        )
        TPL_CARGO_DETAIL.write_text(cd, encoding="utf-8")
        print("✓ cargo_detail.html: tombol Charges ditambahkan")
    else:
        print("• cargo_detail.html sudah ada tombol Charges")
else:
    print("• cargo_detail.html tidak ditemukan (lewati)")

print("\nSelesai ✅  Buka: /sales/cargos/<id>/charges/ untuk manage line charges.")
