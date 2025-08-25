from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP  = ROOT / "sales"
URLS = APP / "urls.py"
VIEWS = APP / "views.py"
TPL_DIR = APP / "templates" / "sales"
TPL_DIR.mkdir(parents=True, exist_ok=True)
TPL_START = TPL_DIR / "quotation_wizard_start.html"
TPL_WIZ = TPL_DIR / "quotation_wizard.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup -> {b}")

print("== Pre‑Wizard (Step 0) for Transport Mode / Service / Multi‑Destination ==")

# 1) urls.py -> add start route
assert URLS.exists(), "sales/urls.py tidak ditemukan"
backup(URLS)
u = URLS.read_text(encoding="utf-8")
if "quotation_wizard_start" not in u:
    if "from . import views" not in u:
        u = "from . import views\n" + u
    u = u.replace(
        "urlpatterns = [",
        "urlpatterns = [\n"
        "    path('quotations/wizard/start/', views.quotation_wizard_start, name='quotation_wizard_start'),"
    )
    URLS.write_text(u, encoding="utf-8")
    print("✓ urls.py: route /sales/quotations/wizard/start/ ditambahkan")
else:
    print("• urls.py: route start sudah ada")

# 2) views.py -> add quotation_wizard_start + enhance quotation_wizard
assert VIEWS.exists(), "sales/views.py tidak ditemukan"
backup(VIEWS)
v = VIEWS.read_text(encoding="utf-8")
changed = False

if "def quotation_wizard_start(" not in v:
    inject = """
from django.shortcuts import render, redirect
from django.urls import reverse

def quotation_wizard_start(request):
    \"\"\"Step 0: pilih transport mode, service type, multi-destination.
    Hasilnya diteruskan via querystring ke /wizard/new/.
    \"\"\"
    if request.method == "POST":
        mode = request.POST.get("mode", "MULTI").upper()
        multi = request.POST.get("multi_destination") in ("on","true","1","True")
        # Land -> service fixed 'TRUCKING'; Multi -> service kosong
        if mode == "LAND":
            service = "TRUCKING"
        else:
            service = request.POST.get("service_option","").upper()

        # Redirect ke wizard new dengan parameter
        url = reverse("sales:quotation_wizard")
        # multi sebagai 1/0
        params = f"?mode={mode}&multi={'1' if multi else '0'}&service={service}"
        return redirect(url + params)

    return render(request, "sales/quotation_wizard_start.html", {})
"""
    # sisipkan di akhir file
    v += ("\n\n" + inject)
    changed = True
    print("✓ views.py: quotation_wizard_start ditambahkan")

# Enhance quotation_wizard membaca qs dan set initial + enforce single destination
if "def quotation_wizard(" in v and "## PRESET_FROM_START" not in v:
    v = re.sub(
        r"(def\s+quotation_wizard\(request[^\)]*\):\s*\n)",
        r"\1    # ## PRESET_FROM_START: baca pilihan dari Step 0 (querystring)\n"
        r"    preset_mode = (request.GET.get('mode') or '').upper() or None\n"
        r"    preset_service = (request.GET.get('service') or '').upper() or None\n"
        r"    preset_multi = request.GET.get('multi')\n"
        r"    if preset_multi is not None:\n"
        r"        preset_multi = True if str(preset_multi) in ('1','true','True','on') else False\n",
        v, count=1
    )
    # pada GET: set initial
    v = re.sub(
        r"(else:\s*\n\s*header_form\s*=\s*QuotationForm\(\)\s*\n\s*cargo_formset\s*=\s*CargoFormSet\([^\)]*\)\s*\n)",
        r"\1        # apply initial dari Step 0\n"
        r"        if preset_mode:\n"
        r"            header_form.fields['transport_mode'].initial = preset_mode\n"
        r"        if preset_service is not None:\n"
        r"            header_form.fields['service_option'].initial = preset_service\n"
        r"        if preset_multi is not None:\n"
        r"            header_form.fields['multi_destination'].initial = preset_multi\n",
        v, count=1
    )
    # sebelum save cargo_formset (POST valid): enforce single-destination
    v = re.sub(
        r"(if\s+header_form\.is_valid\(\)\s*and\s*cargo_formset\.is_valid\(\)\s*:\s*\n\s*quotation\s*=\s*header_form\.save\(commit=False\)\s*\n)",
        r"\1            # enforce single destination jika multi_destination = False\n"
        r"            try:\n"
        r"                is_multi = header_form.cleaned_data.get('multi_destination')\n"
        r"            except Exception:\n"
        r"                is_multi = True\n"
        r"            if not is_multi:\n"
        r"                dest_head = header_form.cleaned_data.get('destination_header')\n"
        r"                for f in cargo_formset.forms:\n"
        r"                    if getattr(f, 'cleaned_data', None) and not f.cleaned_data.get('DELETE', False):\n"
        r"                        f.instance.destination = dest_head\n",
        v, count=1
    )
    changed = True
    print("✓ views.py: quotation_wizard disesuaikan (preset + single-destination set)")

if changed:
    VIEWS.write_text(v, encoding="utf-8")

# 3) template: quotation_wizard_start.html
backup(TPL_START)
if not TPL_START.exists():
    TPL_START.write_text(
"""{% extends "base.html" %}
{% block title %}New Quotation — Start{% endblock %}
{% block content %}
<div class="container-fluid">
  <h2 class="mb-3">Create Quotation — Step 0</h2>
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
""",
        encoding="utf-8"
    )
    print("✓ template: quotation_wizard_start.html dibuat")
else:
    print("• quotation_wizard_start.html sudah ada")

# 4) template: quotation_wizard.html -> add badges + hidden inputs (if not present)
if TPL_WIZ.exists():
    backup(TPL_WIZ)
    h = TPL_WIZ.read_text(encoding="utf-8")
    changed = False

    # a) Badge ringkas pilihan step 0 di bagian atas header form
    if "data-wizard-badges" not in h:
        insert = (
            '<div class="d-flex gap-2 align-items-center mb-2" data-wizard-badges>\n'
            '  <span class="badge text-bg-primary">Mode: {{ header_form.transport_mode.value|default:request.GET.mode }}</span>\n'
            '  <span class="badge text-bg-info">Service: {{ header_form.service_option.value|default:request.GET.service }}</span>\n'
            '  <span class="badge text-bg-secondary">Multi Dest: {{ header_form.multi_destination.value|default:request.GET.multi }}</span>\n'
            '</div>\n'
        )
        # selipkan setelah <!-- HEADER FORM START --> jika ada
        if "<!-- HEADER FORM START -->" in h:
            h = h.replace("<!-- HEADER FORM START -->", "<!-- HEADER FORM START -->\n" + insert)
            changed = True
            print("✓ quotation_wizard.html: badges ringkas ditambahkan")

    # b) Hidden inputs agar nilai dari Step 0 terkirim meski field disembunyikan di UI
    if "name=\"_preset_mode\"" not in h:
        hidden = (
            '{% if request.GET.mode %}<input type="hidden" name="transport_mode" value="{{ request.GET.mode }}">{% endif %}\n'
            '{% if request.GET.service %}<input type="hidden" name="service_option" value="{{ request.GET.service }}">{% endif %}\n'
            '{% if request.GET.multi %}<input type="hidden" name="multi_destination" value="{% if request.GET.multi in \'1 true True on\' %}on{% else %}{% endif %}">{% endif %}\n'
            '<input type="hidden" name="_preset_mode" value="1">\n'
        )
        # simpan sesudah opening <form ...>
        h = re.sub(r"(<form[^>]*>)", r"\1\n" + hidden, h, count=1)
        changed = True
        print("✓ quotation_wizard.html: hidden inputs preset ditambahkan")

    # c) Tandai kolom destination agar bisa di-hide saat single
    if 'data-cargo-destination' not in h:
        h = re.sub(r"(<td[^>]*>)(\s*\{\{\s*form\.destination\s*\}\}\s*)(</td>)",
                   r'<td data-cargo-destination>\2</td>', h)
        changed = True
        print("✓ quotation_wizard.html: marker data-cargo-destination ditambahkan")

    # d) Tambah JS applyWizardFlags jika belum ada (untuk hide/show destination header & kolom)
    if "applyWizardFlags()" not in h:
        h += """
<script>
  function applyWizardFlags(){
    const multi = (
      (document.getElementById('id_multi_destination') && document.getElementById('id_multi_destination').checked) ||
      ('{{ request.GET.multi|default:\"1\" }}' === '1')
    );
    const destHeaderWrap = document.getElementById('dest-header-wrap');
    if(destHeaderWrap){ destHeaderWrap.style.display = multi ? 'none' : ''; }

    document.querySelectorAll('[data-cargo-destination]').forEach(td=>{
      td.style.display = multi ? '' : 'none';
      if(!multi){
        const hdr = document.getElementById('id_destination_header');
        const input = td.querySelector('input,select,textarea');
        if(hdr && input) input.value = hdr.value;
      }
    });
  }
  document.addEventListener('change', (e)=>{
    if(['id_multi_destination','id_destination_header'].includes(e.target.id)){ applyWizardFlags(); }
  });
  document.addEventListener('DOMContentLoaded', applyWizardFlags);
</script>
"""
        changed = True
        print("✓ quotation_wizard.html: JS applyWizardFlags() ditambahkan")

    if changed:
        TPL_WIZ.write_text(h, encoding="utf-8")
        print("✓ quotation_wizard.html diperbarui")
    else:
        print("• quotation_wizard.html tidak berubah (mungkin sudah terpasang)")

print("\nSelesai ✅")
print("Buka: /sales/quotations/wizard/start/ → isi Step 0 → Continue → lanjut ke wizard header & lines.")
print("Catatan:")
print(" - Land: service otomatis 'TRUCKING' (disimpan via hidden jika user tidak ubah).")
print(" - Multi=No: kolom Destination di cargo otomatis tersembunyi dan akan diisi dengan Destination Header.")
