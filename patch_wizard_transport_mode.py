from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
MODELS = APP / "models.py"
FORMS  = APP / "forms.py"
VIEWS  = APP / "views.py"
TPL    = APP / "templates" / "sales" / "quotation_wizard.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup {p} -> {b}")

print("== Patch: Flexible Wizard (Transport Mode, Service Option, Multi‑Destination) ==")

# 1) MODELS ----------------------------------------------------------------
assert MODELS.exists(), "models.py tidak ditemukan"
backup(MODELS)
m = MODELS.read_text(encoding="utf-8")
changed = False

# a) Tambah field di Quotation: transport_mode, service_option, multi_destination, destination_header
if "class Quotation(" in m:
    if "transport_mode" not in m:
        m = re.sub(
            r"(class\s+Quotation\(models\.Model\):[\s\S]*?notes\s*=\s*models\.TextField\(blank=True\)\s*\n)",
            r"\1\n"
            r"    TRANSPORT_CHOICES = [\n"
            r"        ('LAND','Land'), ('SEA','Sea'), ('AIR','Air'), ('MULTI','Multi')\n"
            r"    ]\n"
            r"    transport_mode = models.CharField(max_length=10, choices=TRANSPORT_CHOICES, default='MULTI')\n"
            r"    service_option = models.CharField(max_length=30, blank=True)  # depends on mode\n"
            r"    multi_destination = models.BooleanField(default=True)\n"
            r"    destination_header = models.CharField(max_length=200, blank=True)\n",
            m, count=1
        )
        changed = True
        print("✓ models.py: Quotation fields added (transport_mode, service_option, multi_destination, destination_header)")

# b) (opsional) __str__ tidak diubah; helpers tetap seperti sebelumnya

if changed:
    MODELS.write_text(m, encoding="utf-8")

# 2) FORMS -----------------------------------------------------------------
assert FORMS.exists(), "forms.py tidak ditemukan"
backup(FORMS)
f = FORMS.read_text(encoding="utf-8")
changed = False

# a) Pastikan QuotationForm memuat fields baru + clean() validasi logika
if "class QuotationForm" in f:
    # tambahkan fields bila belum ada
    if "transport_mode" not in f:
        f = re.sub(
            r"(class\s+QuotationForm\(forms\.ModelForm\):[\s\S]*?class\s+Meta:\s*[\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
            r"\1\2, 'transport_mode', 'service_option', 'multi_destination', 'destination_header'\3",
            f, count=1
        )
        # widgets
        f = re.sub(
            r"(class\s+QuotationForm\(forms\.ModelForm\):[\s\S]*?widgets\s*=\s*\{)",
            r"\1\n            'transport_mode': forms.Select(attrs={'class':'form-select'}),\n"
            r"            'service_option': forms.Select(attrs={'class':'form-select'}),\n"
            r"            'multi_destination': forms.CheckboxInput(attrs={'class':'form-check-input'}),\n"
            r"            'destination_header': forms.TextInput(attrs={'class':'form-control'}),",
            f, count=1
        )
        changed = True
        print("✓ forms.py: QuotationForm include fields baru + widgets")

    # tambahkan clean() untuk enforce rules
    if "def clean(self)" not in f or "transport_mode" not in f.split("def clean",1)[1]:
        f += """

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('transport_mode') or 'MULTI'
        multi_dest = cleaned.get('multi_destination')
        service = cleaned.get('service_option') or ''
        dest_head = cleaned.get('destination_header') or ''

        # Mapping service option per mode (server-side)
        SERVICE_BY_MODE = {
            'SEA': ['D2D', 'D2P', 'P2P'],      # Door-to-Door, Door-to-Port, Port-to-Port
            'AIR': ['A2A', 'D2A'],             # Airport-to-Airport, Door-to-Airport
            'LAND': ['D2D', 'H2H'],            # Door-to-Door, Hub-to-Hub (opsional)
            'MULTI': [],                       # bebas, tidak wajib
        }

        if mode != 'MULTI':
            # service option wajib & harus valid
            if not service:
                from django.core.exceptions import ValidationError
                raise ValidationError({'service_option': 'Service option wajib untuk mode selain MULTI.'})
            if service not in SERVICE_BY_MODE.get(mode, []):
                from django.core.exceptions import ValidationError
                raise ValidationError({'service_option': f'Service option tidak valid untuk mode {mode}.'})

        # single destination → destination header wajib
        if not multi_dest and not dest_head:
            from django.core.exceptions import ValidationError
            raise ValidationError({'destination_header': 'Destination (header) wajib jika single destination.'})

        return cleaned
"""
        changed = True
        print("✓ forms.py: QuotationForm.clean menegakkan rules wizard")

# b) CargoFormSet: jika ada daftar fields, biarkan (destination tetap ada — nanti disembunyikan via template/JS)

if changed:
    FORMS.write_text(f, encoding="utf-8")

# 3) VIEWS (wizard) -----------------------------------------------------------
assert VIEWS.exists(), "views.py tidak ditemukan"
backup(VIEWS)
v = VIEWS.read_text(encoding="utf-8")
changed = False

# Tambahkan util untuk sembunyikan destination & pewarisan saat POST
if "def quotation_wizard" in v and "WIZARD_FLAGS" not in v:
    v = re.sub(
        r"(def\s+quotation_wizard\(request[^\)]*\):\s*\n)",
        r"\1    # Wizard flags injected into context & used for behavior\n"
        r"    WIZARD_FLAGS = {}\n",
        v, count=1
    )
    # Pada blok GET/POST, set flags & propagate
    # 1) setelah valid header form di POST:
    v = re.sub(
        r"(if\s+request\.method\s*==\s*\"POST\":\s*\n\s*header_form\s*=\s*QuotationForm\(request\.POST\)\s*\n\s*if\s+header_form\.is_valid\(\):\s*\n)",
        r"\1            mode = header_form.cleaned_data.get('transport_mode')\n"
        r"            multi_dest = header_form.cleaned_data.get('multi_destination')\n"
        r"            dest_head = header_form.cleaned_data.get('destination_header')\n"
        r"            WIZARD_FLAGS.update({'mode': mode, 'multi_dest': multi_dest, 'dest_head': dest_head})\n",
        v, count=1
    )
    # 2) sebelum save cargo formset, kalau single dest → set destination = header
    v = re.sub(
        r"(if\s+cargo_formset\.is_valid\(\):\s*\n\s*quotation\s*=\s*header_form\.save\(commit=False\)\s*\n)",
        r"\1            # apply single-destination inheritance\n"
        r"            if not header_form.cleaned_data.get('multi_destination'):\n"
        r"                for form in cargo_formset.forms:\n"
        r"                    if hasattr(form, 'cleaned_data') and not form.cleaned_data.get('DELETE', False):\n"
        r"                        form.instance.destination = header_form.cleaned_data.get('destination_header')\n",
        v, count=1
    )
    # 3) pada GET, pasang flag default
    v = re.sub(
        r"(else:\s*\n\s*header_form\s*=\s*QuotationForm\(\)\s*\n\s*cargo_formset\s*=\s*CargoFormSet\(\)\s*\n)",
        r"\1        WIZARD_FLAGS.update({'mode': 'MULTI', 'multi_dest': True, 'dest_head': ''})\n",
        v, count=1
    )
    # 4) masukkan flags ke context render()
    v = re.sub(
        r"(return\s+render\(request,\s*\"sales/quotation_wizard\.html\",\s*\{)",
        r"\1\n            'WIZARD_FLAGS': WIZARD_FLAGS,",
        v, count=1
    )
    changed = True
    print("✓ views.py: Wizard set flags + pewarisan single destination")

# 4) TEMPLATE wizard ----------------------------------------------------------
assert TPL.exists(), "quotation_wizard.html tidak ditemukan"
backup(TPL)
t = TPL.read_text(encoding="utf-8")
changed = False

# a) Tambah blok UI di header step: Transport Mode, Service Option, Multi‑Destination, Destination Header
if "Transport Mode" not in t:
    t = t.replace(
        '<!-- HEADER FORM START -->',
        '<!-- HEADER FORM START -->\n'
        '<div class="row g-3">\n'
        '  <div class="col-md-3">\n'
        '    <label class="form-label">Transport Mode</label>\n'
        '    {{ header_form.transport_mode }}\n'
        '  </div>\n'
        '  <div class="col-md-3">\n'
        '    <label class="form-label">Service Option</label>\n'
        '    {{ header_form.service_option }}\n'
        '    <div class="form-text">Wajib untuk mode selain MULTI.</div>\n'
        '  </div>\n'
        '  <div class="col-md-3">\n'
        '    <label class="form-label">Multi Destination?</label>\n'
        '    <div class="form-check mt-2">{{ header_form.multi_destination }}</div>\n'
        '    <div class="form-text">Uncheck untuk single destination.</div>\n'
        '  </div>\n'
        '  <div class="col-md-3" id="dest-header-wrap">\n'
        '    <label class="form-label">Destination (Header)</label>\n'
        '    {{ header_form.destination_header }}\n'
        '  </div>\n'
        '</div>\n'
    )
    changed = True
    print("✓ quotation_wizard.html: UI header (mode/service/multi-dest/destination header)")

# b) Tambah JS: dynamic options + hide destination di cargo saat single dest
if "function applyWizardFlags()" not in t:
    t += """
<script>
  // Service options per mode
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
    'LAND': [
      {v:'D2D', t:'Door → Door'},
      {v:'H2H', t:'Hub → Hub'}
    ],
    'MULTI': []
  };

  function fillServiceOptions(mode){
    const sel = document.getElementById('id_service_option');
    if(!sel) return;
    const current = sel.value;
    sel.innerHTML = '';
    (SERVICE_BY_MODE[mode] || []).forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.v; o.textContent = opt.t;
      sel.appendChild(o);
    });
    if(mode === 'MULTI'){
      const o = document.createElement('option');
      o.value = ''; o.textContent = '— (Not required)';
      sel.appendChild(o);
      sel.value = '';
    }else{
      // pilih pertama jika kosong
      if(!sel.value && sel.options.length) sel.selectedIndex = 0;
    }
  }

  function applyWizardFlags(){
    const modeSel = document.getElementById('id_transport_mode');
    const multiChk = document.getElementById('id_multi_destination');
    const destHeaderWrap = document.getElementById('dest-header-wrap');

    const mode = modeSel ? modeSel.value : 'MULTI';
    const multi = multiChk ? multiChk.checked : true;

    // service options for selected mode
    fillServiceOptions(mode);

    // hide/show header destination
    if(destHeaderWrap){
      destHeaderWrap.style.display = multi ? 'none' : '';
    }

    // hide destination column & inputs in cargo table when single destination
    const cargoDestCells = document.querySelectorAll('[data-cargo-destination]');
    cargoDestCells.forEach(td => {
      td.style.display = multi ? '' : 'none';
      // if single → copy header destination into each hidden input
      if(!multi){
        const input = td.querySelector('input,select,textarea');
        const hdr = document.getElementById('id_destination_header');
        if(input && hdr){ input.value = hdr.value; }
      }
    });
  }

  document.addEventListener('change', function(e){
    if(e.target.id === 'id_transport_mode' || e.target.id === 'id_multi_destination' || e.target.id === 'id_destination_header'){
      applyWizardFlags();
    }
  });
  document.addEventListener('DOMContentLoaded', function(){
    try { applyWizardFlags(); } catch(_){}
  });
</script>
"""
    changed = True
    print("✓ quotation_wizard.html: JS dinamis (service per mode + hide dest line saat single)")

# c) Tandai kolom destination cargo agar bisa di-hide via JS
#   Cari render input destination di table cargo, bungkus td dengan data-cargo-destination
tt = t
tt = re.sub(
    r"(<td>)(\s*\{\{\s*form\.destination\s*\}\}\s*)(</td>)",
    r'<td data-cargo-destination>\2</td>',
    tt
)
if tt != t:
    t = tt; changed = True
    print("✓ quotation_wizard.html: kolom destination cargo diberi marker")

if changed:
    TPL.write_text(t, encoding="utf-8")

print("\nSelesai ✅")
print("Langkah berikut:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("\nCatatan:")
print(" - Header kini punya Transport Mode, Service Option (tergantung mode), Multi‑Destination, dan Destination (Header).")
print(" - Jika mode ≠ MULTI → service option wajib (SEA: D2D/D2P/P2P, AIR: A2A/D2A, LAND: D2D/H2H).")
print(" - Jika Multi‑Destination = No → Destination tiap line disembunyikan & akan diset otomatis ke nilai header saat simpan.")
print(" - Mode (LAND/SEA/AIR) berlaku untuk seluruh cargo (user tidak perlu input per line).")
