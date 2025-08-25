from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP  = ROOT / "sales"
MODELS = APP / "models.py"
FORMS  = APP / "forms.py"
VIEWS  = APP / "views.py"
TPL    = APP / "templates" / "sales" / "quotation_wizard_v3.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup -> {b.name}")

print("== Patch V3: Lock Step 1, Header Origin/Destination for Single, Lines for Multi ==")

# 1) models.py — tambah origin_header (kalau belum)
assert MODELS.exists(), "sales/models.py tidak ditemukan"
backup(MODELS)
m = MODELS.read_text(encoding="utf-8")
changed = False

if "class Quotation(" in m and "origin_header" not in m:
    m = re.sub(
        r"(class\s+Quotation\(models\.Model\):[\s\S]*?multi_destination\s*=\s*models\.BooleanField\(default=True\)\s*\n\s*destination_header\s*=\s*models\.CharField\(max_length=200,\s*blank=True\)\s*\n?)",
        r"\1    origin_header = models.CharField(max_length=200, blank=True)\n",
        m, count=1
    )
    changed = True
    print("✓ models.py: Quotation.origin_header ditambahkan")

if changed:
    MODELS.write_text(m, encoding="utf-8")

# 2) forms.py — tambahkan origin_header ke QuotationForm
assert FORMS.exists(), "sales/forms.py tidak ditemukan"
backup(FORMS)
f = FORMS.read_text(encoding="utf-8")
changed = False

if "class QuotationForm" in f and "origin_header" not in f:
    # tambahkan ke fields
    f = re.sub(
        r"(class\s+QuotationForm\(forms\.ModelForm\):[\s\S]*?class\s+Meta:\s*[\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
        r"\1\2, 'origin_header'\3",
        f, count=1
    )
    # tambahkan widget
    if "widgets =" in f:
        f = re.sub(
            r"(widgets\s*=\s*\{\s*)",
            r"\1'origin_header': forms.TextInput(attrs={'class':'form-control','id':'id_origin_header'}), ",
            f, count=1
        )
    else:
        # fallback: buat widgets
        f = re.sub(
            r"(class\s+QuotationForm\(forms\.ModelForm\):[\s\S]*?class\s+Meta:\s*[\s\S]*?model\s*=\s*Quotation\s*)",
            r"\1\n        widgets = {\n            'origin_header': forms.TextInput(attrs={'class':'form-control','id':'id_origin_header'})\n        }\n",
            f, count=1
        )
    changed = True
    print("✓ forms.py: QuotationForm menambahkan origin_header")

if changed:
    FORMS.write_text(f, encoding="utf-8")

# 3) views.py — enforce copy origin/destination header ke semua cargo saat single
assert VIEWS.exists(), "sales/views.py tidak ditemukan"
backup(VIEWS)
v = VIEWS.read_text(encoding="utf-8")
changed = False

# Cari fungsi quotation_wizard_v3 dan sisipkan copy origin_header/destination_header
pattern = re.compile(r"def\s+quotation_wizard_v3\s*\([\s\S]*?\):[\s\S]*?(?=\n\ndef\s|\Z)", re.MULTILINE)
mfunc = pattern.search(v)
if mfunc:
    body = mfunc.group(0)
    if "f.instance.origin = dest_origin" not in body:
        body = re.sub(
            r"(if\s+header_form\.is_valid\(\)\s*and\s*cargo_formset\.is_valid\(\)\s*:\s*\n\s*# Enforce single destination[\s\S]*?if\s+not\s+is_multi:\s*\n)",
            r"\1            dest_origin = header_form.cleaned_data.get('origin_header')\n"
            r"            dest_header = header_form.cleaned_data.get('destination_header')\n",
            body, count=1
        )
        body = re.sub(
            r"(for\s+f\s+in\s+cargo_formset\.forms:\s*\n\s*if\s+getattr\(f,\s*'cleaned_data',\s*None\)\s*and\s*not\s*f\.cleaned_data\.get\('DELETE',\s*False\)\s*:\s*\n\s*)f\.instance\.destination\s*=\s*dest_head",
            r"\1f.instance.origin = dest_origin\n                f.instance.destination = dest_header",
            body, count=1
        )
        v = v[:mfunc.start()] + body + v[mfunc.end():]
        changed = True
        print("✓ views.py: single-destination → copy origin_header & destination_header ke semua cargo")

if changed:
    VIEWS.write_text(v, encoding="utf-8")

# 4) template v3 — kunci Step 1 & atur tampil/hidden origin/dest sesuai multi
assert TPL.exists(), "sales/templates/sales/quotation_wizard_v3.html tidak ditemukan"
backup(TPL)
t = TPL.read_text(encoding="utf-8")
changed = False

# a) Hapus/sembyikan kontrol Step 0 di Step 1: ganti field visible dengan hidden + badges
#   - Pastikan ada badge; tambahkan hidden inputs agar nilai terkirim
if "name=\"transport_mode\"" not in t:
    t = re.sub(r"(<form[^>]*>)", r"""\1
    <!-- Step 0 selections as hidden inputs -->
    {% if preset_mode %}<input type="hidden" name="transport_mode" value="{{ preset_mode }}">{% endif %}
    {% if preset_service %}<input type="hidden" name="service_option" value="{{ preset_service }}">{% endif %}
    {% if preset_multi is not None %}
      <input type="hidden" name="multi_destination" value="{% if preset_multi %}on{% endif %}">
    {% endif %}
    """, t, count=1)
    changed = True
    print("✓ template v3: hidden inputs untuk mode/service/multi ditambahkan")

#   - Sembunyikan kontrol visible untuk transport_mode/service_option/multi_destination di header (kalau ada)
t2 = t
t2 = re.sub(r"<label[^>]*>Transport Mode<\/label>[\s\S]*?header_form\.transport_mode[\s\S]*?(<\/div>)", r"<!-- Transport Mode hidden in v3 step1 -->\1", t2)
t2 = re.sub(r"<label[^>]*>Service Option<\/label>[\s\S]*?header_form\.service_option[\s\S]*?(<\/div>)", r"<!-- Service Option hidden in v3 step1 -->\1", t2)
t2 = re.sub(r"<label[^>]*>Multi Destination\?<\/label>[\s\S]*?header_form\.multi_destination[\s\S]*?(<\/div>)", r"<!-- Multi Destination hidden in v3 step1 -->\1", t2)
if t2 != t:
    t = t2; changed = True
    print("✓ template v3: kontrol Step 0 disembunyikan di Step 1")

# b) Tambah blok header origin/destination (untuk single). Jika belum ada, sisipkan setelah header section.
if "id_origin_header" not in t or "id_destination_header" not in t:
    # sisipkan UI origin/destination header
    insert_hdr = """
      <div class="row g-3" id="hdr-route-row">
        <div class="col-md-6">
          <label class="form-label">Origin (Header)</label>
          {{ header_form.origin_header }}
        </div>
        <div class="col-md-6">
          <label class="form-label">Destination (Header)</label>
          {{ header_form.destination_header }}
        </div>
      </div>
    """
    # letakkan sebelum <hr class="my-4">
    t = t.replace("<hr class=\"my-4\">", insert_hdr + "\n<hr class=\"my-4\">")
    changed = True
    print("✓ template v3: blok Origin/Destination Header ditambahkan")

# c) Tandai kolom origin/destination pada cargo lines
if 'data-cargo-origin' not in t:
    t = re.sub(r"(<td[^>]*>)(\s*\{\{\s*f\.origin\s*\}\}\s*)(</td>)", r'<td data-cargo-origin>\2</td>', t)
    changed = True
    print("✓ template v3: kolom origin cargo diberi marker")
if 'data-cargo-destination' not in t:
    t = re.sub(r"(<td[^>]*>)(\s*\{\{\s*f\.destination\s*\}\}\s*)(</td>)", r'<td data-cargo-destination>\2</td>', t)
    changed = True
    print("✓ template v3: kolom destination cargo diberi marker")

# d) JS: sembunyikan header origin/destination saat multi; sembunyikan kolom origin/destination di lines saat single & copy nilai
if "function applyV3RouteFlags()" not in t:
    t += """
<script>
function applyV3RouteFlags(){
  // multi = true => origin/dest di line; single => origin/dest di header
  const multi = {{ preset_multi|yesno:"true,false" }};
  const hdrRow = document.getElementById('hdr-route-row');
  if(hdrRow){ hdrRow.style.display = multi ? 'none' : ''; }

  const originHdr = document.getElementById('id_origin_header');
  const destHdr = document.getElementById('id_destination_header');

  document.querySelectorAll('[data-cargo-origin]').forEach(td=>{
    td.style.display = multi ? '' : 'none';
    if(!multi && originHdr){
      const inp = td.querySelector('input,select,textarea');
      if(inp) inp.value = originHdr.value;
    }
  });
  document.querySelectorAll('[data-cargo-destination]').forEach(td=>{
    td.style.display = multi ? '' : 'none';
    if(!multi && destHdr){
      const inp = td.querySelector('input,select,textarea');
      if(inp) inp.value = destHdr.value;
    }
  });
}
document.addEventListener('DOMContentLoaded', applyV3RouteFlags);
document.addEventListener('change', (e)=>{
  if(e.target && (e.target.id === 'id_origin_header' || e.target.id === 'id_destination_header')){
    applyV3RouteFlags();
  }
});
</script>
"""
    changed = True
    print("✓ template v3: JS applyV3RouteFlags() ditambahkan")

if changed:
    TPL.write_text(t, encoding="utf-8")
    print(f"✓ template diperbarui: {TPL.name}")
else:
    print("• template tidak berubah (mungkin sudah terpasang)")

print("\nSelesai ✅")
print("Lanjutkan:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("  python manage.py runserver")
print("\nHasil:")
print(" - Step 1 tidak lagi menampilkan kontrol Step 0 (mode/service/multi), hanya badge/hidden.")
print(" - Multi=YES → origin/destination hanya di cargo lines; header route disembunyikan.")
print(" - Multi=NO  → origin/destination ada di header; kolom origin/destination di lines disembunyikan dan disalin dari header saat submit.")
