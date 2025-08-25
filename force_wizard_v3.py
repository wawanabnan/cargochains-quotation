from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP  = ROOT / "sales"
URLS = APP / "urls.py"
VIEWS = APP / "views.py"
TPL  = APP / "templates" / "sales"
TPL.mkdir(parents=True, exist_ok=True)

V3_START = TPL / "quotation_wizard_v3_start.html"
V3_WIZ   = TPL / "quotation_wizard_v3.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup -> {b.name}")

print("== Force Wizard V3 routes, views, templates ==")

# 1) urls.py: add v3 routes
assert URLS.exists(), "sales/urls.py tidak ditemukan"
backup(URLS)
u = URLS.read_text(encoding="utf-8")
if "quotation_wizard_v3_start" not in u:
    if "from . import views" not in u:
        u = "from . import views\n" + u
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('quotations/wizard/v3/start/', views.quotation_wizard_v3_start, name='quotation_wizard_v3_start'),\n"
        "    path('quotations/wizard/v3/', views.quotation_wizard_v3, name='quotation_wizard_v3'),"
    )
    URLS.write_text(u, encoding="utf-8")
    print("✓ urls.py: v3 routes ditambahkan")
else:
    print("• urls.py: v3 routes sudah ada")

# 2) views.py: add lightweight v3 views that render v3 templates
assert VIEWS.exists(), "sales/views.py tidak ditemukan"
backup(VIEWS)
v = VIEWS.read_text(encoding="utf-8")
changed = False

if "def quotation_wizard_v3_start(" not in v:
    v += """

from django.shortcuts import render, redirect
from django.urls import reverse

def quotation_wizard_v3_start(request):
    \"\"\"Step 0 (V3): Pilih mode, service, multi-destination. Hasilnya diteruskan via querystring ke /wizard/v3/\"\"\"
    if request.method == "POST":
        mode = (request.POST.get("mode") or "MULTI").upper()
        multi = request.POST.get("multi_destination") in ("on","true","1","True")
        if mode == "LAND":
            service = "TRUCKING"
        else:
            service = (request.POST.get("service_option") or "").upper()

        url = reverse("sales:quotation_wizard_v3")
        params = f"?mode={mode}&multi={'1' if multi else '0'}&service={service}"
        return redirect(url + params)
    return render(request, "sales/quotation_wizard_v3_start.html", {})

def quotation_wizard_v3(request):
    \"\"\"Step 1 (V3): Header + Cargo. Baca preset dari querystring dan kirim ke template V3.\"\"\"
    # Import sini supaya tidak mengganggu import order proyekmu
    from .forms import QuotationForm, CargoFormSet
    preset_mode = (request.GET.get('mode') or '').upper() or None
    preset_service = (request.GET.get('service') or '').upper() or None
    preset_multi = request.GET.get('multi')
    if preset_multi is not None:
        preset_multi = True if str(preset_multi) in ('1','true','True','on') else False

    if request.method == "POST":
        header_form = QuotationForm(request.POST)
        cargo_formset = CargoFormSet(request.POST, prefix="cg")
        if header_form.is_valid() and cargo_formset.is_valid():
            quotation = header_form.save(commit=False)
            # single destination -> set destination line dari header
            try:
                is_multi = header_form.cleaned_data.get("multi_destination")
            except Exception:
                is_multi = True
            if not is_multi:
                dest_head = header_form.cleaned_data.get("destination_header")
                for f in cargo_formset.forms:
                    if getattr(f, "cleaned_data", None) and not f.cleaned_data.get("DELETE", False):
                        f.instance.destination = dest_head
            quotation.save()
            cargo_formset.instance = quotation
            cargo_formset.save()
            from django.shortcuts import redirect
            return redirect("sales:quotation_detail", pk=quotation.pk)
    else:
        header_form = QuotationForm()
        cargo_formset = CargoFormSet(prefix="cg")
        # apply preset ke initial
        if preset_mode:
            header_form.fields["transport_mode"].initial = preset_mode
        if preset_service is not None:
            header_form.fields["service_option"].initial = preset_service
        if preset_multi is not None:
            header_form.fields["multi_destination"].initial = preset_multi

    return render(request, "sales/quotation_wizard_v3.html", {
        "header_form": header_form,
        "cargo_formset": cargo_formset,
        "preset_mode": preset_mode,
        "preset_service": preset_service,
        "preset_multi": preset_multi,
    })
"""
    changed = True

if changed:
    VIEWS.write_text(v, encoding="utf-8")
    print("✓ views.py: v3 views ditambahkan")
else:
    print("• views.py: v3 views sudah ada")

# 3) templates v3
backup(V3_START)
if not V3_START.exists():
    V3_START.write_text("""{% extends "base.html" %}
{% block title %}New Quotation — Start (V3){% endblock %}
{% block content %}
<div class="container-fluid">
  <h2 class="mb-3">Create Quotation — Step 0 (V3)</h2>
  <form method="post" class="card shadow-sm">
    {% csrf_token %}
    <div class="card-body">
      <div class="row g-4">
        <div class="col-md-4">
          <label class="form-label">Transport Mode</label>
          <div class="list-group" id="mode-group">
            <label class="list-group-item"><input type="radio" name="mode" value="SEA" class="form-check-input me-2"> Sea</label>
            <label class="list-group-item"><input type="radio" name="mode" value="AIR" class="form-check-input me-2"> Air</label>
            <label class="list-group-item"><input type="radio" name="mode" value="LAND" class="form-check-input me-2"> Land</label>
            <label class="list-group-item"><input type="radio" name="mode" value="MULTI" class="form-check-input me-2" checked> Multi</label>
          </div>
        </div>
        <div class="col-md-4">
          <label class="form-label">Service Type</label>
          <select name="service_option" id="service_option" class="form-select">
            <option value="">— (Not required for Multi)</option>
          </select>
          <div class="form-text">Sea: D2D/D2P/P2P · Air: A2A/D2A · Land: fixed 'TRUCKING'</div>
        </div>
        <div class="col-md-4">
          <label class="form-label">Multi Destination?</label>
          <div class="form-check">
            <input class="form-check-input" type="checkbox" id="multi_destination" name="multi_destination" checked>
            <label class="form-check-label" for="multi_destination">Yes (destination per cargo)</label>
          </div>
          <div class="form-text">Uncheck untuk single destination (destination akan di header Step 1)</div>
        </div>
      </div>
    </div>
    <div class="card-footer d-flex justify-content-end gap-2">
      <a href="{% url 'sales:quotation_list' %}" class="btn btn-outline-secondary">Cancel</a>
      <button class="btn btn-primary" type="submit">Continue</button>
    </div>
  </form>
</div>

<script>
const SERVICE_BY_MODE = {
  'SEA': [
    {v:'D2D', t:'Door → Door'},
    {v:'D2P', t:'Door → Port'},
    {v:'P2P', t:'Port → Port'}
  ],
  'AIR': [
    {v:'A2A', t:'Airport → Airport'},
    {v:'D2A', t:'Door → Airport'}
  ],
  'LAND': [ {v:'TRUCKING', t:'Trucking'} ],
  'MULTI': []
};

function fillService(mode){
  const sel = document.getElementById('service_option');
  sel.innerHTML = '';
  (SERVICE_BY_MODE[mode] || []).forEach(o=>{
    const opt = document.createElement('option');
    opt.value = o.v; opt.textContent = o.t;
    sel.appendChild(opt);
  });
  if(mode === 'MULTI'){
    const opt = document.createElement('option');
    opt.value = ''; opt.textContent = '— (Not required for Multi)';
    sel.appendChild(opt);
    sel.value = '';
  }else if(mode === 'LAND'){
    const opt = document.createElement('option');
    opt.value = 'TRUCKING'; opt.textContent = 'Trucking';
    sel.appendChild(opt);
    sel.value = 'TRUCKING';
  }else{
    if(sel.options.length) sel.selectedIndex = 0;
  }
}

document.addEventListener('change', (e)=>{
  if(e.target.name === 'mode'){
    fillService(e.target.value);
  }
});
document.addEventListener('DOMContentLoaded', ()=>{
  fillService(document.querySelector('input[name="mode"]:checked').value);
});
</script>
{% endblock %}
""", encoding="utf-8")
    print("✓ quotation_wizard_v3_start.html dibuat")
else:
    print("• quotation_wizard_v3_start.html sudah ada")

backup(V3_WIZ)
if not V3_WIZ.exists():
    V3_WIZ.write_text("""{% extends "base.html" %}
{% block title %}New Quotation — Wizard (V3){% endblock %}
{% block content %}
<div class="container-fluid">
  <h2 class="mb-3">Create Quotation — Step 1 (V3)</h2>
  <div class="mb-2">
    <span class="badge text-bg-primary">Mode: {{ preset_mode|default:"-" }}</span>
    <span class="badge text-bg-info">Service: {{ preset_service|default:"-" }}</span>
    <span class="badge text-bg-secondary">Multi Dest: {{ preset_multi|yesno:"Yes,No" }}</span>
  </div>

  <form method="post" class="card shadow-sm">
    {% csrf_token %}
    <div class="card-body">
      <h5 class="mb-3">Header</h5>
      <div class="row g-3">
        <div class="col-md-3">
          <label class="form-label">Date</label>
          {{ header_form.date }}
        </div>
        <div class="col-md-3">
          <label class="form-label">Validity Date</label>
          {{ header_form.validity_date }}
        </div>
        <div class="col-md-6">
          <label class="form-label">Customer</label>
          {{ header_form.customer }}
        </div>

        <div class="col-md-4">
          <label class="form-label">Payment Terms</label>
          {{ header_form.payment_terms }}
        </div>
        <div class="col-md-8">
          <label class="form-label">Notes</label>
          {{ header_form.notes }}
        </div>

        <div class="col-md-3">
          <label class="form-label">Transport Mode</label>
          {{ header_form.transport_mode }}
        </div>
        <div class="col-md-3">
          <label class="form-label">Service Option</label>
          {{ header_form.service_option }}
        </div>
        <div class="col-md-3">
          <label class="form-label">Multi Destination?</label><br>
          {{ header_form.multi_destination }}
        </div>
        <div class="col-md-3" id="dest-header-wrap">
          <label class="form-label">Destination (Header)</label>
          {{ header_form.destination_header }}
        </div>
      </div>

      <hr class="my-4">
      <h5 class="mb-3">Cargo Lines</h5>
      {{ cargo_formset.management_form }}
      <div class="table-responsive">
        <table class="table align-middle">
          <thead class="table-light">
            <tr>
              <th>Description</th>
              <th>Pkg</th>
              <th class="text-end">Qty</th>
              <th class="text-end">Weight (kg)</th>
              <th class="text-end">Volume (cbm)</th>
              <th>Origin</th>
              <th>Destination</th>
              <th>Delete</th>
            </tr>
          </thead>
          <tbody id="cg-tbody">
            {% for f in cargo_formset %}
            <tr>
              <td>{{ f.description }}</td>
              <td>{{ f.package_type }}</td>
              <td class="text-end">{{ f.qty }}</td>
              <td class="text-end">{{ f.weight_kg }}</td>
              <td class="text-end">{{ f.volume_cbm }}</td>
              <td>{{ f.origin }}</td>
              <td data-cargo-destination>{{ f.destination }}</td>
              <td class="text-center">{{ f.DELETE }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <button type="button" class="btn btn-outline-primary" onclick="addCargo()">+ Add Line</button>
    </div>
    <div class="card-footer d-flex justify-content-end gap-2">
      <a class="btn btn-outline-secondary" href="{% url 'sales:quotation_wizard_v3_start' %}">Back</a>
      <button class="btn btn-success" type="submit">Save</button>
    </div>
  </form>
</div>

<script>
function addCargo(){
  const totalInput = document.querySelector('input[name="cg-TOTAL_FORMS"]');
  let idx = parseInt(totalInput.value || '0');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input class="form-control" name="cg-${idx}-description"></td>
    <td><input class="form-control" name="cg-${idx}-package_type"></td>
    <td class="text-end"><input class="form-control text-end" type="number" step="0.001" name="cg-${idx}-qty" value="1"></td>
    <td class="text-end"><input class="form-control text-end" type="number" step="0.001" name="cg-${idx}-weight_kg"></td>
    <td class="text-end"><input class="form-control text-end" type="number" step="0.001" name="cg-${idx}-volume_cbm"></td>
    <td><input class="form-control" name="cg-${idx}-origin"></td>
    <td data-cargo-destination><input class="form-control" name="cg-${idx}-destination"></td>
    <td class="text-center"><input type="checkbox" class="form-check-input" name="cg-${idx}-DELETE"></td>
    <input type="hidden" name="cg-${idx}-id">
  `;
  document.getElementById('cg-tbody').appendChild(tr);
  totalInput.value = idx + 1;
}

const SERVICE_BY_MODE = {
  'SEA': [
    {v:'D2D', t:'Door → Door'},
    {v:'D2P', t:'Door → Port'},
    {v:'P2P', t:'Port → Port'}
  ],
  'AIR': [
    {v:'A2A', t:'Airport → Airport'},
    {v:'D2A', t:'Door → Airport'}
  ],
  'LAND': [ {v:'TRUCKING', t:'Trucking'} ],
  'MULTI': []
};

function fillServiceOptions(mode){
  const sel = document.getElementById('id_service_option');
  if(!sel) return;
  const cur = sel.value;
  sel.innerHTML = '';
  (SERVICE_BY_MODE[mode] || []).forEach(o=>{
    const opt = document.createElement('option');
    opt.value = o.v; opt.textContent = o.t;
    sel.appendChild(opt);
  });
  if(mode === 'MULTI'){
    const opt = document.createElement('option');
    opt.value = ''; opt.textContent = '— (Not required)';
    sel.appendChild(opt);
    sel.value = '';
  }else if(mode === 'LAND'){
    const opt = document.createElement('option');
    opt.value = 'TRUCKING'; opt.textContent = 'Trucking';
    sel.appendChild(opt);
    sel.value = 'TRUCKING';
  }else{
    if(sel.options.length) sel.selectedIndex = 0;
  }
}

function applyWizardFlags(){
  const modeSel = document.getElementById('id_transport_mode');
  const multiChk = document.getElementById('id_multi_destination');
  const destHdr = document.getElementById('id_destination_header');
  const destWrap = document.getElementById('dest-header-wrap');

  const mode = modeSel ? modeSel.value : '{{ preset_mode|default:"MULTI" }}';
  const multi = (multiChk ? multiChk.checked : ( '{{ preset_multi|default:"True" }}' === 'True' ));

  fillServiceOptions(mode);
  if(destWrap) destWrap.style.display = multi ? 'none' : '';

  document.querySelectorAll('[data-cargo-destination]').forEach(td=>{
    td.style.display = multi ? '' : 'none';
    if(!multi && destHdr){
      const input = td.querySelector('input,select,textarea');
      if(input) input.value = destHdr.value;
    }
  });
}

document.addEventListener('change', (e)=>{
  if(e.target.id === 'id_transport_mode'){ fillServiceOptions(e.target.value); }
  if(['id_multi_destination','id_destination_header'].includes(e.target.id)){ applyWizardFlags(); }
});
document.addEventListener('DOMContentLoaded', applyWizardFlags);
</script>
{% endblock %}
""", encoding="utf-8")
    print("✓ quotation_wizard_v3.html dibuat")
else:
    print("• quotation_wizard_v3.html sudah ada")

print("\nSelesai ✅")
print("Buka:")
print("  - /sales/quotations/wizard/v3/start/")
print("Jika sudah cocok, nanti kita bisa switch URL lama agar pakai template v3.")
