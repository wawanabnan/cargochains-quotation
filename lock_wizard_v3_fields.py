from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "sales" / "views.py"
TPL   = ROOT / "sales" / "templates" / "sales" / "quotation_wizard_v3.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup -> {b.name}")

# ---------- Patch views.py: force lock on POST ----------
assert VIEWS.exists(), "sales/views.py tidak ditemukan"
backup(VIEWS)
src = VIEWS.read_text(encoding="utf-8")

# Temukan fungsi quotation_wizard_v3
pattern = re.compile(r"def\s+quotation_wizard_v3\s*\([\s\S]*?\):[\s\S]*?(?=\n\ndef\s|\Z)", re.MULTILINE)
m = pattern.search(src)
if m:
    body = m.group(0)
    if "## LOCK_STEP1_FIELDS" not in body:
        # Pastikan preset dibaca (kalau belum)
        if "preset_mode" not in body:
            # Tambahan ini jarang perlu, karena preset sudah ada. Skip untuk aman.
            pass
        # Sisipkan override POST di awal blok POST
        body = re.sub(
            r"(if\s+request\.method\s*==\s*\"POST\":\s*\n\s*)header_form\s*=\s*QuotationForm\(request\.POST\)",
            r"\1## LOCK_STEP1_FIELDS: override POST from Step 0 presets\n"
            r"        preset_mode = (request.GET.get('mode') or '').upper() or None\n"
            r"        preset_service = (request.GET.get('service') or '').upper() or None\n"
            r"        preset_multi = request.GET.get('multi')\n"
            r"        if preset_multi is not None:\n"
            r"            preset_multi = True if str(preset_multi) in ('1','true','True','on') else False\n"
            r"        _post = request.POST.copy()\n"
            r"        if preset_mode:\n"
            r"            _post['transport_mode'] = preset_mode\n"
            r"        if preset_service is not None:\n"
            r"            _post['service_option'] = preset_service\n"
            r"        if preset_multi is not None:\n"
            r"            _post['multi_destination'] = 'on' if preset_multi else ''\n"
            r"        header_form = QuotationForm(_post)",
            body, count=1
        )
        src = src[:m.start()] + body + src[m.end():]
        VIEWS.write_text(src, encoding="utf-8")
        print("✓ views.py: POST kini mengunci nilai mode/service/multi dari Step 0")
    else:
        print("• views.py: override POST sudah ada (LOCK_STEP1_FIELDS)")
else:
    print("! Tidak menemukan fungsi quotation_wizard_v3 — pastikan sudah dibuat sebelumnya.")

# ---------- Patch template: disable + hidden ----------
assert TPL.exists(), "quotation_wizard_v3.html tidak ditemukan"
backup(TPL)
html = TPL.read_text(encoding="utf-8")
changed = False

# 1) Sisipkan hidden inputs untuk memastikan nilai terkirim, dekat tag <form>
if 'name="transport_mode"' not in html or 'name="service_option"' not in html or 'name="multi_destination"' not in html:
    html = re.sub(
        r"(<form[^>]*>)",
        r"""\1
    <!-- Step 0 selections as hidden inputs (locked in Step 1) -->
    {% if preset_mode %}<input type="hidden" name="transport_mode" value="{{ preset_mode }}">{% endif %}
    {% if preset_service %}<input type="hidden" name="service_option" value="{{ preset_service }}">{% endif %}
    {% if preset_multi is not None %}<input type="hidden" name="multi_destination" value="{% if preset_multi %}on{% endif %}">{% endif %}
""",
        html, count=1
    )
    changed = True
    print("✓ template: hidden inputs ditambahkan")

# 2) Tambahkan atribut disabled ke kontrol visible (kalau masih tampil)
# transport_mode
html2 = re.sub(
    r"(\{\{\s*header_form\.transport_mode\s*\}\})",
    r'<div class="lock-field">{{ header_form.transport_mode }}</div>',
    html
)
# service_option
html2 = re.sub(
    r"(\{\{\s*header_form\.service_option\s*\}\})",
    r'<div class="lock-field">{{ header_form.service_option }}</div>',
    html2
)
# multi_destination
html2 = re.sub(
    r"(\{\{\s*header_form\.multi_destination\s*\}\})",
    r'<div class="lock-field">{{ header_form.multi_destination }}</div>',
    html2
)

if html2 != html:
    html = html2
    changed = True
    print("✓ template: wrapper lock-field ditambahkan (akan di-disable via JS/CSS)")

# 3) Tambahkan CSS + JS untuk disable interaksi & memaksa revert jika user utak‑atik devtools
if "/* lock step1 fields */" not in html:
    html += """
<style>
/* lock step1 fields */
.lock-field select,
.lock-field input[type="checkbox"],
.lock-field input[type="radio"] {
  pointer-events: none;
}
.lock-field select:disabled,
.lock-field input:disabled {
  opacity: 0.85;
}
</style>
<script>
// Hard lock via JS: set disabled=true & revert perubahan
(function(){
  function lock(){
    // transport mode & service option
    document.querySelectorAll('.lock-field select').forEach(el=>{
      el.setAttribute('disabled', 'disabled');
    });
    // multi_destination checkbox
    document.querySelectorAll('.lock-field input[type="checkbox"]').forEach(el=>{
      el.setAttribute('disabled', 'disabled');
    });

    // Revert jika ada perubahan paksa
    const presetMode = "{{ preset_mode|default_if_none:'' }}";
    const presetService = "{{ preset_service|default_if_none:'' }}";
    const presetMulti = "{{ preset_multi|yesno:'on,' }}"; // 'on' or ''

    const modeSel = document.getElementById('id_transport_mode');
    if(modeSel && presetMode){ modeSel.value = presetMode; }

    const svcSel = document.getElementById('id_service_option');
    if(svcSel && presetService !== ''){ svcSel.value = presetService; }

    const multiChk = document.getElementById('id_multi_destination');
    if(multiChk){
      multiChk.checked = (presetMulti === 'on');
    }
  }
  document.addEventListener('DOMContentLoaded', lock);
})();
</script>
"""
    changed = True
    print("✓ template: CSS/JS pengunci ditambahkan")

if changed:
    TPL.write_text(html, encoding="utf-8")
    print(f"Selesai ✅  Template terkunci: {TPL.name}")
else:
    print("• Template tidak berubah (mungkin sudah terkunci sebelumnya)")

print("\nDone. Saat Step 1, kontrol tetap tampil namun tidak bisa diubah; server juga mengunci nilainya saat POST.")
