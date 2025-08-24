from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari ROOT project (yang ada manage.py)."

SALES = ROOT / "sales"
FORMS = SALES / "forms.py"
WIZ   = SALES / "templates" / "sales" / "quotation_wizard.html"
DETAIL= SALES / "templates" / "sales" / "quotation_detail.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

print("== Remove Cargo Description from HEADER (forms + wizard template) ==")

# --- 1) Bersihkan QuotationForm agar TIDAK ada 'cargo_desc' ---
if FORMS.exists():
    backup(FORMS)
    txt = FORMS.read_text(encoding="utf-8")
    changed = False

    # (a) Hilangkan 'cargo_desc' dari Meta.fields QuotationForm
    def drop_from_fields(match):
        before, inner, after = match.groups()
        items = [s.strip() for s in inner.split(",") if s.strip()]
        items = [s for s in items if s.strip("'\" ") != "cargo_desc"]
        return before + ", ".join(items) + after

    txt2 = re.sub(
        r"(class\s+QuotationForm[\s\S]*?class\s+Meta[\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
        drop_from_fields,
        txt, count=1
    )
    if txt2 != txt:
        txt = txt2; changed = True
        print("  • Removed 'cargo_desc' from QuotationForm.fields")

    # (b) Hapus widget cargo_desc kalau ada
    txt2 = re.sub(
        r'^\s*"cargo_desc"\s*:\s*forms\.[A-Za-z]+Input\([^\)]*\),?\s*$',
        "",
        txt, flags=re.MULTILINE
    )
    if txt2 != txt:
        txt = txt2; changed = True
        print("  • Removed 'cargo_desc' widget from QuotationForm.widgets")

    if changed:
        FORMS.write_text(txt, encoding="utf-8")
        print("  ✓ forms.py updated")
    else:
        print("  • forms.py already clean (no cargo_desc in header)")
else:
    print("  ! sales/forms.py tidak ditemukan")

# --- 2) Hapus blok 'Cargo Description' di Step 1 wizard template ---
if WIZ.exists():
    backup(WIZ)
    t = WIZ.read_text(encoding="utf-8")
    changed = False

    # (a) coba hapus div kolom cargo yang umum
    patterns = [
        # pola 2 kolom (col-md-6)
        r'\s*<div class="col-md-6">\s*<label class="form-label">Cargo Description</label>\s*\{\{\s*header_form\.cargo_desc\s*\}\}\s*</div>\s*',
        # pola 12 kolom (col-12)
        r'\s*<div class="col-12">\s*<label class="form-label">Cargo Description</label>\s*\{\{\s*header_form\.cargo_desc\s*\}\}\s*</div>\s*',
        # pola generik: label + field dalam satu baris apa pun
        r'\s*<div class="[^"]*">\s*<label class="form-label">Cargo Description</label>\s*\{\{\s*header_form\.cargo_desc\s*\}\}\s*</div>\s*',
    ]
    t2 = t
    for p in patterns:
        t2 = re.sub(p, "\n", t2)
    if t2 != t:
        t = t2; changed = True
        print("  • Removed Cargo Description block from wizard Step 1")

    # (b) jaga-jaga: hapus sisa {{ header_form.cargo_desc }}
    t2 = re.sub(r"\s*\{\{\s*header_form\.cargo_desc\s*\}\}\s*", "\n", t)
    if t2 != t:
        t = t2; changed = True
        print("  • Removed stray {{ header_form.cargo_desc }} usages")

    if changed:
        WIZ.write_text(t, encoding="utf-8")
        print("  ✓ quotation_wizard.html updated")
    else:
        print("  • wizard template already clean")
else:
    print("  ! wizard template tidak ditemukan:", WIZ)

# --- 3) (Opsional) Hapus display cargo di header pada detail page ---
if DETAIL.exists():
    backup(DETAIL)
    d = DETAIL.read_text(encoding="utf-8")
    d2 = d.replace(
        '<div class="fw-bold mb-2">Cargo</div>',
        ''
    ).replace(
        '{{ quotation.cargo_desc|default:"-" }}',
        ''
    )
    if d2 != d:
        DETAIL.write_text(d2, encoding="utf-8")
        print("  ✓ quotation_detail.html header cargo removed (optional)")
else:
    print("  • detail template (optional) tidak ditemukan, lewati")

print("\nSelesai ✅")
print("Refresh halaman wizard. Cargo Description seharusnya tidak ada lagi di Step 1 (Header).")
