import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari root project (yang ada manage.py)."

SALES = ROOT / "sales"
MODELS = SALES / "models.py"
FORMS = SALES / "forms.py"
TPL_DETAIL = SALES / "templates" / "sales" / "quotation_detail.html"
TPL_LINES = SALES / "templates" / "sales" / "quotation_lines_form.html"

def backup(p: pathlib.Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  • backup {p} -> {b}")

print("== Move origin to QuotationLine + update forms & templates ==")

# 1) Update models.py -> tambah field origin di QuotationLine (CharField, blank=True)
print("[MODELS] patching models.py …")
txt = MODELS.read_text(encoding="utf-8")
backup(MODELS)

if "class QuotationLine" not in txt:
    sys.exit("Tidak menemukan class QuotationLine di sales/models.py.")

# a) jika sudah ada origin di QuotationLine, tidak perlu tambah
if re.search(r"class\s+QuotationLine.*?:[\s\S]*?origin\s*=\s*models\.CharField", txt):
    print("  ✓ QuotationLine.origin sudah ada")
else:
    # cari posisi field 'destination =' di dalam QuotationLine, sisipkan origin setelahnya
    pattern = r"(class\s+QuotationLine\s*\(models\.Model\):[\s\S]*?destination\s*=\s*models\.[^\n]+\n)"
    if re.search(pattern, txt):
        txt = re.sub(pattern,
                     r"\1    origin = models.CharField(max_length=100, blank=True)\n",
                     txt, count=1)
        MODELS.write_text(txt, encoding="utf-8")
        print("  ✓ Ditambahkan field QuotationLine.origin (CharField)")
    else:
        # fallback: sisipkan setelah class line
        txt = re.sub(r"(class\s+QuotationLine\s*\(models\.Model\):\n)",
                     r"\1    origin = models.CharField(max_length=100, blank=True)\n",
                     txt, count=1)
        MODELS.write_text(txt, encoding="utf-8")
        print("  ✓ Ditambahkan field QuotationLine.origin (fallback)")

# 2) Update forms.py -> pastikan LineFormSet/Factory menyertakan 'origin' di fields
print("[FORMS] patching forms.py …")
f = FORMS.read_text(encoding="utf-8")
backup(FORMS)

# Ubah semua kemunculan inlineformset_factory untuk QuotationLine agar fields berisi origin
def ensure_origin_in_fields(block: str) -> str:
    # block mengandung 'fields=[...]'
    return re.sub(
        r"fields\s*=\s*\[([^\]]*)\]",
        lambda m: (
            "fields=[" +
            (
                ("\"origin\", " + m.group(1)) if "origin" not in m.group(1) else m.group(1)
            ) +
            "]"
        ),
        block, count=1
    )

changed = False

# Case 1: LineFormSet = inlineformset_factory(QuotationDestination, QuotationLine, fields=[...])
pattern1 = r"(LineFormSet\s*=\s*inlineformset_factory\([\s\S]*?QuotationLine[\s\S]*?\))"
if re.search(pattern1, f):
    def repl1(m):
        block = m.group(1)
        if "fields=" in block and "origin" not in block:
            nonlocal changed
            changed = True
            return ensure_origin_in_fields(block)
        return block
    f = re.sub(pattern1, repl1, f)

# Case 2: LineFormSetFactory = lambda … inlineformset_factory(…, fields=[...])
pattern2 = r"(LineFormSetFactory\s*=\s*lambda[\s\S]*?inlineformset_factory\([\s\S]*?QuotationLine[\s\S]*?\))"
if re.search(pattern2, f):
    def repl2(m):
        block = m.group(1)
        if "fields=" in block and "origin" not in block:
            nonlocal changed
            changed = True
            return ensure_origin_in_fields(block)
        return block
    f = re.sub(pattern2, repl2, f)

if changed:
    FORMS.write_text(f, encoding="utf-8")
    print("  ✓ Ditambahkan 'origin' ke fields LineFormSet/Factory")
else:
    # Jika tidak ketemu, coba tambahkan baris definisi default LineFormSet
    if "LineFormSet" not in f and "LineFormSetFactory" not in f:
        inject = """
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import QuotationDestination, QuotationLine

class _LineFormSet(BaseInlineFormSet):
    pass

LineFormSet = inlineformset_factory(
    QuotationDestination,
    QuotationLine,
    formset=_LineFormSet,
    fields=["origin","charge_type","description","unit","qty","rate","currency"],
    extra=3,
    can_delete=True
)
"""
        f += "\n" + inject
        FORMS.write_text(f, encoding="utf-8")
        print("  ✓ Ditambahkan definisi LineFormSet default dengan 'origin'")
    else:
        print("  ✓ Tidak ada perubahan fields diperlukan (mungkin sudah termasuk 'origin')")

# 3) Update templates: quotation_detail.html -> tambah kolom Origin
print("[TEMPLATE] updating quotation_detail.html …")
if TPL_DETAIL.exists():
    t = TPL_DETAIL.read_text(encoding="utf-8")
    backup(TPL_DETAIL)

    if "<th>Origin</th>" not in t:
        # sisipkan kolom header Origin setelah "No"
        t = t.replace(
            "<tr><th style=\"width:60px;\">No</th><th>Charge Type</th>",
            "<tr><th style=\"width:60px;\">No</th><th>Origin</th><th>Charge Type</th>"
        )
        # sisipkan cell {{ line.origin }} setelah nomor
        t = t.replace(
            "<td>{{ forloop.counter }}</td>\n                  <td><span class=\"badge text-bg-secondary\">{{ line.charge_type }}</span></td>",
            "<td>{{ forloop.counter }}</td>\n                  <td>{{ line.origin }}</td>\n                  <td><span class=\"badge text-bg-secondary\">{{ line.charge_type }}</span></td>"
        )
        TPL_DETAIL.write_text(t, encoding="utf-8")
        print("  ✓ Kolom 'Origin' ditambahkan ke detail table")
    else:
        print("  ✓ quotation_detail.html sudah menampilkan Origin")
else:
    print("  • Lewati: templates/sales/quotation_detail.html tidak ditemukan")

# 4) Update templates: quotation_lines_form.html -> tambah input Origin di formset
print("[TEMPLATE] updating quotation_lines_form.html …")
if TPL_LINES.exists():
    t2 = TPL_LINES.read_text(encoding="utf-8")
    backup(TPL_LINES)

    # Tambah kolom header
    if "<th>Origin</th>" not in t2:
        t2 = t2.replace(
            "<tr><th>Charge Type</th><th>Description</th><th>Unit</th><th class=\"text-end\">Qty</th><th class=\"text-end\">Rate</th><th>Curr</th><th>Delete?</th></tr>",
            "<tr><th>Origin</th><th>Charge Type</th><th>Description</th><th>Unit</th><th class=\"text-end\">Qty</th><th class=\"text-end\">Rate</th><th>Curr</th><th>Delete?</th></tr>"
        )
    # Tambah cell form.origin
    if "{{ form.origin }}" not in t2:
        t2 = t2.replace(
            "<tr>\n                <td>{{ form.charge_type }}</td>\n                <td>{{ form.description }}</td>\n                <td>{{ form.unit }}</td>\n                <td class=\"text-end\">{{ form.qty }}</td>\n                <td class=\"text-end\">{{ form.rate }}</td>\n                <td>{{ form.currency }}</td>\n                <td>{{ form.DELETE }}</td>\n              </tr>",
            "<tr>\n                <td>{{ form.origin }}</td>\n                <td>{{ form.charge_type }}</td>\n                <td>{{ form.description }}</td>\n                <td>{{ form.unit }}</td>\n                <td class=\"text-end\">{{ form.qty }}</td>\n                <td class=\"text-end\">{{ form.rate }}</td>\n                <td>{{ form.currency }}</td>\n                <td>{{ form.DELETE }}</td>\n              </tr>"
        )
        # alternatif pola lain (jaga-jaga struktur berbeda):
        t2 = t2.replace(
            "<td>{{ form.charge_type }}</td>",
            "<td>{{ form.origin }}</td><td>{{ form.charge_type }}</td>"
        )
    TPL_LINES.write_text(t2, encoding="utf-8")
    print("  ✓ quotation_lines_form.html diperbarui (Origin field)")
else:
    print("  • Lewati: templates/sales/quotation_lines_form.html tidak ditemukan")

print("\nSelesai ✅")
print("- Lanjutkan dengan:")
print("  python manage.py makemigrations && python manage.py migrate")
print("  python manage.py runserver")
