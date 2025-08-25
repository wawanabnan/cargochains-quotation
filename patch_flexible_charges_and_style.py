from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
API = APP / "api"
MODELS = APP / "models.py"
FORMS = APP / "forms.py"
SERIALIZERS = API / "serializers.py"
TPL = APP / "templates" / "sales"
TPL_DETAIL = TPL / "quotation_detail.html"
TPL_PDF = TPL / "quotation_pdf.html"
TPL_CHG = TPL / "cargo_charges_edit.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup {p} -> {b}")

print("== Patch: Flexible charges (description only), Odoo-like inputs, and currency aggregation fix ==")

# ---------- models.py ----------
assert MODELS.exists(), "models.py tidak ditemukan"
backup(MODELS)
m = MODELS.read_text(encoding="utf-8")
changed = False

# 1) CargoCharge: remove charge_type, ensure description exists
if "class CargoCharge(" in m:
    # remove charge_type field
    m2 = re.sub(r"\n\s*charge_type\s*=\s*models\.CharField\([^\)]*\)\s*\n", "\n", m)
    # ensure description exists
    if "description =" not in m2:
        m2 = re.sub(
            r"(class\s+CargoCharge\(models\.Model\):\s*\n)",
            r"\1    description = models.CharField(max_length=200)\n",
            m2, count=1
        )
    # __str__ friendly
    if re.search(r"class\s+CargoCharge\(models\.Model\):[\s\S]*?def __str__", m2):
        m2 = re.sub(
            r"(class\s+CargoCharge\(models\.Model\):[\s\S]*?def __str__\([^\)]*\):\s*\n\s*)return[^\n]*\n",
            r"\1return f\"{self.cargo} - {self.description}: {self.amount}\"\n",
            m2, count=1
        )
    else:
        m2 = re.sub(
            r"(class\s+CargoCharge\(models\.Model\):[\s\S]*?)\n(\s*def save\()",
            r"\1\n    def __str__(self):\n        return f\"{self.cargo} - {self.description}: {self.amount}\"\n\n\2",
            m2, count=1
        )
    # ensure save() computes amount
    if "def save(" in m2 and "self.amount" not in re.findall(r"class\s+CargoCharge[\s\S]*?def save\([^\)]*\):[\s\S]*?super\(\)\.save", m2):
        m2 = re.sub(
            r"(def\s+save\([^\)]*\):\s*\n\s*)",
            r"\1self.amount = (self.qty or 0) * (self.rate or 0)\n        ",
            m2, count=1
        )
    if m2 != m:
        m = m2; changed = True
        print("✓ models.py: CargoCharge → description-only (charge_type removed)")

# 2) Remove any currency grouping-based helpers & add total_amount helpers
# Quotation.totals_by_currency → replace with total_amount property
if "def totals_by_currency" in m:
    m = re.sub(
        r"def\s+totals_by_currency\(self\):[\s\S]*?return[^\n]*\n",
        "def totals_by_currency(self):\n        # deprecated: kept for compatibility (no currency grouping)\n        from django.db.models import Sum\n        return [{'currency': getattr(self, 'currency', ''), 'total': (self.total_amount or 0)}]\n",
        m, count=1
    )
    changed = True
if "def total_amount(self)" not in m and "class Quotation(" in m:
    m = re.sub(
        r"(class\s+Quotation\(models\.Model\):[\s\S]*?def\s+get_absolute_url\([^\)]*\):[\s\S]*?return[^\n]*\n)",
        r"\1\n    @property\n    def total_amount(self):\n        from django.db.models import Sum\n        agg = (CargoCharge.objects\n               .filter(cargo__quotation=self)\n               .aggregate(total=Sum('amount')))\n        return agg.get('total') or 0\n",
        m, count=1
    ); changed = True

# Cargo.totals_by_currency → replace with total_amount method
if re.search(r"class\s+Cargo\(models\.Model\):[\s\S]*?def totals_by_currency", m):
    m = re.sub(
        r"def\s+totals_by_currency\(self\):[\s\S]*?return[^\n]*\n",
        "def totals_by_currency(self):\n        # deprecated: kept for compatibility (no currency grouping)\n        return [{'currency': getattr(self.quotation, 'currency', ''), 'total': (self.total_amount() or 0)}]\n",
        m, count=1
    ); changed = True
if "def total_amount(self)" not in m and "class Cargo(" in m:
    m = re.sub(
        r"(class\s+Cargo\(models\.Model\):[\s\S]*?def __str__\([^\)]*\):[\s\S]*?return[^\n]*\n)",
        r"\1\n    def total_amount(self):\n        from django.db.models import Sum\n        agg = self.charges.aggregate(total=Sum('amount'))\n        return agg.get('total') or 0\n",
        m, count=1
    ); changed = True

if changed:
    MODELS.write_text(m, encoding="utf-8")

# ---------- forms.py ----------
assert FORMS.exists(), "forms.py tidak ditemukan"
backup(FORMS)
f = FORMS.read_text(encoding="utf-8")
changed = False

# Update ChargeFormSet fields: use description, remove charge_type
f2 = re.sub(
    r"(inlineformset_factory\(\s*Cargo,\s*CargoCharge,[\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
    lambda mm: mm.group(1) + ", ".join(
        [tok for tok in [x.strip() for x in mm.group(2).split(",")]
         if tok and tok.strip("'\"") not in ("charge_type","currency")] + ["'description'"]
    ) + mm.group(3),
    f
)
if f2 != f:
    f = f2; changed = True
    print("✓ forms.py: ChargeFormSet menggunakan description (charge_type removed)")

# Remove uniqueness validation on charge_type (since no longer exists)
f2 = re.sub(
    r"# Unique charge_type per cargo[\s\S]*?seen\.add\(ct\)\n",
    "", f
)
if f2 != f:
    f = f2; changed = True
    print("✓ forms.py: Validasi duplikat charge_type dihapus")

if changed:
    FORMS.write_text(f, encoding="utf-8")

# ---------- serializers.py (DRF) ----------
if SERIALIZERS.exists():
    backup(SERIALIZERS)
    s = SERIALIZERS.read_text(encoding="utf-8")
    changed = False
    # replace 'charge_type' with 'description' in CargoChargeSerializer fields
    s2 = re.sub(
        r"(class\s+CargoChargeSerializer\(serializers\.ModelSerializer\):[\s\S]*?fields\s*=\s*\[)([^\]]*)(\])",
        lambda mm: mm.group(1) + ", ".join(
            [tok for tok in [x.strip() for x in mm.group(2).split(",")]
             if tok and tok.strip("'\"") not in ("charge_type","currency")] + ["'description'"]
        ) + mm.group(3),
        s, count=1
    )
    if s2 != s:
        s = s2; changed = True
        print("✓ serializers.py: gunakan description, hapus charge_type/currency")
    if changed:
        SERIALIZERS.write_text(s, encoding="utf-8")
else:
    print("• serializers.py tidak ditemukan (abaikan kalau belum pakai API)")

# ---------- Templates: quotation_detail.html ----------
if TPL_DETAIL.exists():
    backup(TPL_DETAIL)
    d = TPL_DETAIL.read_text(encoding="utf-8")
    changed = False
    # table header: change Charge column to "Charge"
    d2 = d.replace("<th>Charge</th>", "<th>Charge</th>")
    # body: use line.description instead of line.charge_type
    d2 = d2.replace("{{ line.charge_type }}", "{{ line.description }}")
    # remove Curr column if still there
    d2 = d2.replace('<th class="text-center">Curr</th>', '')
    d2 = d2.replace('<td class="text-center">{{ line.currency }}</td>', '')
    # subtotal block: show single total with quotation.currency
    d2 = re.sub(
        r"\{\% for row in cargo\.totals_by_currency \%\}[\s\S]*?\{\% endfor \%\}",
        "{{ quotation.currency }}: <strong>{{ cargo.total_amount|floatformat:2 }}</strong>",
        d2, count=1
    )
    # grand total block
    d2 = re.sub(
        r"\{\% for row in quotation\.totals_by_currency \%\}[\s\S]*?\{\% endfor \%\}",
        "{{ quotation.currency }}: <strong>{{ quotation.total_amount|floatformat:2 }}</strong>",
        d2, count=1
    )
    if d2 != d:
        TPL_DETAIL.write_text(d2, encoding="utf-8")
        print("✓ quotation_detail.html diperbarui (pakai description & total tunggal)")

# ---------- Templates: quotation_pdf.html ----------
if TPL_PDF.exists():
    backup(TPL_PDF)
    p = TPL_PDF.read_text(encoding="utf-8")
    changed = False
    # kolom charge pakai description, tidak ada currency
    p2 = p.replace("<th>Charge</th>", "<th>Charge</th>")
    p2 = p2.replace("{{ line.charge_type }}", "{{ line.description }}")
    p2 = p2.replace("<th width=\"8%\" class=\"center\">Curr</th>", "")
    p2 = p2.replace("<td class=\"center\">{{ line.currency }}</td>", "")
    # subtotal block (detail mode) -> single total with quotation.currency
    p2 = re.sub(
        r"<strong>Subtotal.*?\</strong\>[\s\S]*?\</ul\>",
        "<strong>Subtotal:</strong> <span class=\"muted\">({{ quotation.currency }})</span>\n"
        "<div><strong>{{ cargo.total_amount|floatformat:2 }}</strong></div>",
        p2, count=1
    )
    # grand total block -> single total with quotation.currency
    p2 = re.sub(
        r"\<div\>\<strong\>Grand Total.*?\</div\>[\s\S]*?\</ul\>",
        "<div><strong>Grand Total:</strong> <span class=\"small muted\">({{ quotation.currency }})</span></div>\n"
        "<div class=\"small\"><strong>{{ quotation.total_amount|floatformat:2 }}</strong></div>",
        p2, count=1
    )
    if p2 != p:
        TPL_PDF.write_text(p2, encoding="utf-8")
        print("✓ quotation_pdf.html diperbarui (description & total tunggal)")

# ---------- Templates: cargo_charges_edit.html (Odoo-like styling + description field) ----------
if TPL_CHG.exists():
    backup(TPL_CHG)
    t = TPL_CHG.read_text(encoding="utf-8")
    changed = False
    # header: use Description, remove currency column if any
    t2 = t.replace(
        '<th>Charge</th><th>Unit</th>\n              <th class="text-end">Qty</th><th class="text-end">Rate</th>\n              <th>Delete</th>',
        '<th>Description</th><th>Unit</th>\n              <th class="text-end">Qty</th><th class="text-end">Rate</th>\n              <th>Delete</th>'
    )
    # body: replace f.charge_type -> f.description
    t2 = t2.replace("{{ f.charge_type }}", "{{ f.description }}")
    # ensure {{ f.description }} exists if not present
    if "{{ f.description }}" not in t2 and "{{ f.charge_type }}" not in t2:
        # insert first cell as description input
        t2 = t2.replace("<tbody id=\"chg-tbody\">", "<tbody id=\"chg-tbody\">\n            <!-- rows will include description -->")
    # add Odoo-like CSS (borderless inputs)
    if "/* odoo-like inputs */" not in t2:
        t2 = t2.replace(
            "{% endblock %}",
            """<style>
/* odoo-like inputs (borderless, only bottom line) */
.table input.form-control, .table select.form-select, .table textarea.form-control {
  border: 0 !important;
  border-bottom: 1px solid #e5e7eb !important; /* tailwind zinc-200 */
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  padding-left: 0.25rem; padding-right: 0.25rem;
}
.table .form-control:focus, .table .form-select:focus {
  outline: none !important;
  box-shadow: none !important;
  border-bottom-color: #94a3b8 !important; /* slate-400 */
}
</style>
{% endblock %}"""
        )
    if t2 != t:
        TPL_CHG.write_text(t2, encoding="utf-8")
        print("✓ cargo_charges_edit.html: pakai description & borderless inputs (Odoo style)")

print("\nSelesai ✅")
print("Lanjutkan:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("\nCatatan:")
print(" - Line charge sekarang pakai field 'description' (free text).")
print(" - Tidak ada lagi 'charge_type'.")
print(" - Error FieldError terkait 'currency' hilang karena aggregation tidak pakai field itu lagi.")
print(" - PDF & halaman detail menampilkan total tunggal per cargo & grand total, label currency ambil dari Quotation.")
