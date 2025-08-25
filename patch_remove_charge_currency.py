from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
API = APP / "api"
MODELS = APP / "models.py"
FORMS = APP / "forms.py"
SER = API / "serializers.py"
TPL_DIR = APP / "templates" / "sales"
TPL_DIR.mkdir(parents=True, exist_ok=True)
TPL_CHG = TPL_DIR / "cargo_charges_edit.html"
TPL_PDF = TPL_DIR / "quotation_pdf.html"
TPL_QDETAIL = TPL_DIR / "quotation_detail.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup {p.name} -> {b.name}")

print("== Patch: drop CargoCharge.currency; Quotation.currency default IDR ==")

# 1) MODELS -------------------------------------------------------------------
assert MODELS.exists(), "models.py tidak ditemukan"
backup(MODELS)
m = MODELS.read_text(encoding="utf-8")
changed = False

# 1a) Tambahkan / set currency di Quotation (choices + default IDR)
if "class Quotation(" in m:
    if "currency =" not in m:
        # sisipkan currency setelah notes
        m2 = re.sub(
            r"(class\s+Quotation\(models\.Model\):[\s\S]*?notes\s*=\s*models\.TextField\(blank=True\)\s*\n)",
            r"\1\n    CURRENCY_CHOICES = [\n"
            r"        ('IDR','IDR'), ('USD','USD'), ('EUR','EUR'), ('GBP','GBP')\n"
            r"    ]\n"
            r"    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='IDR')\n",
            m, count=1
        )
        if m2 != m:
            m = m2; changed = True
            print("✓ models.py: Quotation.currency ditambahkan (default IDR)")
    else:
        # pastikan pilihan & default IDR
        if "CURRENCY_CHOICES" not in m:
            m = re.sub(
                r"(class\s+Quotation\(models\.Model\):)",
                r"\1\n    CURRENCY_CHOICES = [\n"
                r"        ('IDR','IDR'), ('USD','USD'), ('EUR','EUR'), ('GBP','GBP')\n"
                r"    ]",
                m, count=1
            )
            changed = True
        # set default 'IDR'
        m = re.sub(
            r"(currency\s*=\s*models\.CharField\([^\)]*default=)'(?:USD|EUR|GBP)'",
            r"\1'IDR'",
            m
        )
        print("• models.py: Quotation.currency sudah ada (default diset ke IDR jika perlu)")

# 1b) Hapus field currency di CargoCharge + bersihkan referensi
if "class CargoCharge(" in m:
    # hapus definisi currency field
    m2 = re.sub(
        r"\n\s*currency\s*=\s*models\.CharField\([^\)]*\)\s*\n", "\n", m
    )
    # bersihkan __str__ yang menampilkan currency
    m2 = re.sub(r"\|\s*\{\s*self\.charge_type[^}]*\}\s*", "", m2)
    m2 = re.sub(r"currency\}\s*", "", m2)
    # jika ada f-string menyebut currency
    m2 = re.sub(r"f\"[^\"]*currency[^\"]*\"", "\"\"", m2)
    if m2 != m:
        m = m2; changed = True
        print("✓ models.py: CargoCharge.currency dihapus")

    # pastikan save() tidak menyentuh currency
    m2 = re.sub(
        r"\n\s*try:\s*\n\s*self\.currency\s*=\s*self\.cargo\.quotation\.currency\s*\n\s*except\s*Exception:\s*[\s\S]*?\n",
        "\n", m
    )
    if m2 != m:
        m = m2; changed = True
        print("✓ models.py: hapus assignment currency di save()")

# 1c) Pastikan amount dihitung dari qty*rate (jaga-jaga)
if "class CargoCharge(" in m:
    if "def save(" in m and "self.amount" not in re.findall(r"class\s+CargoCharge[\s\S]*?def save\([^\)]*\):[\s\S]*?super\(\)\.save", m):
        m = re.sub(
            r"(class\s+CargoCharge\(models\.Model\):[\s\S]*?)(def\s+save\([^\)]*\):\s*\n\s*)([\s\S]*?super\(\)\.save\([^\)]*\)\s*)",
            r"\1\2        self.amount = (self.qty or 0) * (self.rate or 0)\n        \3",
            m, count=1
        )
        changed = True
        print("✓ models.py: save() menghitung amount (qty*rate)")

if changed:
    MODELS.write_text(m, encoding="utf-8")

# 2) FORMS ---------------------------------------------------------------------
assert FORMS.exists(), "forms.py tidak ditemukan"
backup(FORMS)
f = FORMS.read_text(encoding="utf-8")
changed = False

# 2a) Tambah 'currency' di QuotationForm jika belum
if "class QuotationForm" in f and "currency" not in f:
    f = re.sub(
        r"(class\s+QuotationForm\(forms\.ModelForm\):[\s\S]*?class\s+Meta:\s*[\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
        r"\1\2, 'currency'\3",
        f, count=1
    )
    # tambahkan widget select
    if "widgets = {" in f and "\"currency\"" not in f:
        f = re.sub(
            r"(\"notes\"\s*:\s*forms\.Textarea\([^\)]*\)\s*\}\s*)",
            r"\"notes\": forms.Textarea(attrs={\"class\":\"form-control\",\"rows\":3}),\n"
            r"            \"currency\": forms.Select(attrs={\"class\":\"form-select\"})\n        }\n",
            f, count=1
        )
    changed = True
    print("✓ forms.py: QuotationForm menambahkan field currency")

# 2b) Hilangkan 'currency' dari ChargeFormSet / Factory fields
def strip_field_list(text):
    return re.sub(
        r"(inlineformset_factory\([\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
        lambda mm: mm.group(1) + ", ".join(
            [s for s in [x.strip() for x in mm.group(2).split(",")]
             if s and s.strip("'\"") != "currency"]
        ) + mm.group(3),
        text
    )
f2 = strip_field_list(f)
if f2 != f:
    f = f2; changed = True
    print("✓ forms.py: Currency dihapus dari fields ChargeFormSet/Factory")

if changed:
    FORMS.write_text(f, encoding="utf-8")

# 3) DRF SERIALIZERS -----------------------------------------------------------
if SER.exists():
    backup(SER)
    s = SER.read_text(encoding="utf-8")
    changed = False
    # hapus 'currency' dari CargoChargeSerializer fields & read_only_fields
    s2 = re.sub(
        r"(class\s+CargoChargeSerializer\(serializers\.ModelSerializer\):[\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
        lambda mm: mm.group(1) + ", ".join(
            [tok for tok in [x.strip() for x in mm.group(2).split(",")]
             if tok and tok.strip("'\"") != "currency"]
        ) + mm.group(3),
        s, count=1
    )
    s2 = re.sub(
        r"(read_only_fields\s*=\s*\[)([^\]]*)(\])",
        lambda mm: mm.group(1) + ", ".join(
            [tok for tok in [x.strip() for x in mm.group(2).split(",")]
             if tok and tok.strip("'\"") != "currency"]
        ) + mm.group(3),
        s2
    )
    if s2 != s:
        s = s2; changed = True
        print("✓ serializers.py: hapus currency dari CargoChargeSerializer")

    if changed:
        SER.write_text(s, encoding="utf-8")
else:
    print("• serializers.py tidak ditemukan (abaikan kalau belum pakai API)")

# 4) TEMPLATES -----------------------------------------------------------------
# 4a) Editor charges: hilangkan kolom currency jika masih ada + tampil currency header
if TPL_CHG.exists():
    backup(TPL_CHG)
    t = TPL_CHG.read_text(encoding="utf-8")
    t2 = t
    t2 = t2.replace(
        '<th>Charge</th><th>Description</th><th>Unit</th>\n              <th class="text-end">Qty</th><th class="text-end">Rate</th>\n              <th>Curr</th><th>Delete</th>',
        '<th>Charge</th><th>Unit</th>\n              <th class="text-end">Qty</th><th class="text-end">Rate</th>\n              <th>Delete</th>'
    )
    t2 = t2.replace('<td>{{ f.description }}</td>\n              <td>{{ f.unit }}</td>',
                    '<td>{{ f.unit }}</td>')
    t2 = t2.replace('<th>Curr</th>', '')
    t2 = t2.replace('<td>{{ f.currency }}</td>', '')
    t2 = t2.replace('<td class="text-end">{{ f.rate }}</td>\n              <td class="text-center">{{ f.DELETE }}</td>',
                    '<td class="text-end">{{ f.rate }}</td>\n              <td class="text-center">{{ f.DELETE }}</td>')
    if "Currency:" not in t2:
        t2 = t2.replace(
            '<form method="post" class="card shadow-sm">',
            '<form method="post" class="card shadow-sm">\n'
            '    <div class="px-3 pt-3 text-body-secondary"><strong>Currency:</strong> {{ quotation.currency }}</div>'
        )
    if t2 != t:
        TPL_CHG.write_text(t2, encoding="utf-8")
        print("✓ cargo_charges_edit.html disinkronkan (tanpa currency kolom)")

# 4b) PDF: pastikan tidak ada kolom currency, dan tampilkan currency header
if TPL_PDF.exists():
    backup(TPL_PDF)
    p = TPL_PDF.read_text(encoding="utf-8")
    changed = False
    if "Currency:" not in p:
        p = p.replace(
            "{{ quotation.payment_terms|default:\"-\" }}<br>",
            "{{ quotation.payment_terms|default:\"-\" }}<br>"
            "<div class=\"small mt12\"><strong>Currency:</strong> {{ quotation.currency }}</div>\n"
        )
        changed = True
    # hapus kolom currency di tabel detail jika masih ada
    p = p.replace("<th width=\"8%\" class=\"center\">Curr</th>", "")
    p = p.replace("<td class=\"center\">{{ line.currency }}</td>", "")
    if changed or p != TPL_PDF.read_text(encoding="utf-8"):
        TPL_PDF.write_text(p, encoding="utf-8")
        print("✓ quotation_pdf.html diperbarui (currency di header, kolom currency dihapus)")

# 4c) Quotation detail: tampil currency di header, hilangkan kolom currency di lines
if TPL_QDETAIL.exists():
    backup(TPL_QDETAIL)
    qd = TPL_QDETAIL.read_text(encoding="utf-8")
    changed = False
    if "Currency</div>" not in qd:
        qd = qd.replace(
            '{{ quotation.payment_terms|default:"-" }}</div>',
            '{{ quotation.payment_terms|default:"-" }}</div>\n'
            '<div class="fw-bold mt-2">Currency</div>\n'
            '<div>{{ quotation.currency }}</div>'
        )
        changed = True
    qd = qd.replace('<th class="text-center">Curr</th>', '')
    qd = qd.replace('<td class="text-center">{{ line.currency }}</td>', '')
    if changed or qd != TPL_QDETAIL.read_text(encoding="utf-8"):
        TPL_QDETAIL.write_text(qd, encoding="utf-8")
        print("✓ quotation_detail.html diperbarui (currency di header, kolom currency dihapus)")

print("\nSelesai ✅")
print("Lanjutkan dengan:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("\nCatatan:")
print(" - Migration akan menghapus kolom sales_cargocharge.currency dari DB.")
print(" - Semua tampilan/editor & API sudah tidak memakai field currency di line.")
print(" - Currency sekarang tunggal di Quotation (default IDR).")
