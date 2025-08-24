import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari root project (selevel manage.py)."

APP = ROOT / "sales"
MODELS = APP / "models.py"
FORMS = APP / "forms.py"
TPL_WIZ = APP / "templates" / "sales" / "quotation_wizard.html"
TPL_DETAIL = APP / "templates" / "sales" / "quotation_detail.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  • backup {p} -> {b}")

print("== Enable Multi-Cargo at Line Level ==")

# 1) MODELS: tambah kolom cargo_* di QuotationLine + pastikan origin tetap di line
if not MODELS.exists():
    raise SystemExit("sales/models.py tidak ditemukan")
backup(MODELS)
m = MODELS.read_text(encoding="utf-8")
changed = False

# Pastikan class QuotationLine ada
if "class QuotationLine" not in m:
    raise SystemExit("Class QuotationLine tidak ditemukan. Pastikan modul sales sudah dibuat.")

# a) Tambahkan origin jika belum ada (sesuai kesepakatan sebelumnya)
if not re.search(r"QuotationLine[\s\S]*?\n\s+origin\s*=\s*models\.CharField", m):
    m = re.sub(
        r"(class\s+QuotationLine\s*\(models\.Model\):[\s\S]*?destination\s*=\s*models\.[^\n]+\n)",
        r"\1    origin = models.CharField(max_length=100, blank=True)\n",
        m, count=1
    )
    changed = True
    print("  ✓ Ditambahkan QuotationLine.origin (CharField, blank=True)")

# b) Tambahkan cargo fields di QuotationLine jika belum ada
if not re.search(r"QuotationLine[\s\S]*?\n\s+cargo_name\s*=", m):
    m = re.sub(
        r"(class\s+QuotationLine\s*\(models\.Model\):)",
        r"\1\n    # ---- Cargo fields (multi-cargo per destination) ----\n"
        r"    cargo_name = models.CharField(max_length=120, blank=True)\n"
        r"    pkg_type = models.CharField(max_length=60, blank=True)  # e.g., CTN, PLT, BAG\n"
        r"    weight_kg = models.DecimalField(max_digits=12, decimal_places=3, default=0)\n"
        r"    volume_cbm = models.DecimalField(max_digits=12, decimal_places=3, default=0)\n",
        m, count=1
    )
    changed = True
    print("  ✓ Ditambahkan cargo fields di QuotationLine (cargo_name, pkg_type, weight_kg, volume_cbm)")

# c) Pastikan amount dihitung di save()
if not re.search(r"def save\(self, \*args, \*\*kwargs\):[\s\S]*?self\.amount", m):
    # cari field amount; jika tidak ada, tambahkan sekalian
    if "amount =" not in m:
        # Tambahkan field amount default
        m = re.sub(
            r"(class\s+QuotationLine\s*\(models\.Model\):[\s\S]*?currency\s*=\s*models\.CharField[^\n]+\n)",
            r"\1    amount = models.DecimalField(max_digits=14, decimal_places=2, editable=False, default=0)\n",
            m, count=1
        )
    # tambahkan save()
    m = re.sub(
        r"(class\s+QuotationLine\s*\(models\.Model\):[\s\S]*?)(\n\s*def __str__|$)",
        r"\1\n    def save(self, *args, **kwargs):\n"
        r"        # hitung amount per baris = qty * rate\n"
        r"        try:\n"
        r"            self.amount = (self.qty or 0) * (self.rate or 0)\n"
        r"        except Exception:\n"
        r"            pass\n"
        r"        super().save(*args, **kwargs)\n\n"
        r"\2",
        m, count=1
    )
    changed = True
    print("  ✓ Ditambahkan perhitungan amount di save()")

if changed:
    MODELS.write_text(m, encoding="utf-8")
else:
    print("  • models.py tidak perlu diubah (sudah sesuai)")

# 2) FORMS: tambahkan cargo fields ke LineFormSet/Factory
if not FORMS.exists():
    raise SystemExit("sales/forms.py tidak ditemukan")
backup(FORMS)
f = FORMS.read_text(encoding="utf-8")
changed = False

def ensure_line_fields(text: str) -> str:
    def inject_fields(block: str) -> str:
        # pastikan origin + cargo fields ada di fields=[...]
        return re.sub(
            r"fields\s*=\s*\[([^\]]*)\]",
            lambda m: "fields=[\"origin\", \"cargo_name\", \"pkg_type\", \"weight_kg\", \"volume_cbm\", " +
                      m.group(1).strip() + "]" if "cargo_name" not in m.group(1) else m.group(0),
            block, count=1
        )
    # LineFormSet =
    text2 = re.sub(
        r"(LineFormSet\s*=\s*inlineformset_factory\([\s\S]*?QuotationLine[\s\S]*?\))",
        lambda m: inject_fields(m.group(1)),
        text
    )
    # LineFormSetFactory =
    text3 = re.sub(
        r"(LineFormSetFactory\s*=\s*lambda[\s\S]*?inlineformset_factory\([\s\S]*?QuotationLine[\s\S]*?\))",
        lambda m: inject_fields(m.group(1)),
        text2
    )
    return text3

f2 = ensure_line_fields(f)
if f2 != f:
    f = f2
    changed = True
    print("  ✓ cargo fields ditambahkan ke LineFormSet/Factory")

# Pastikan _LineFormSet.clean() menghitung baris aktif dengan cargo fields
if "class _LineFormSet" in f and "cargo_name" not in f:
    f = re.sub(
        r"(class\s+_LineFormSet\(BaseInlineFormSet\):[\s\S]*?any\(\s*f\.cleaned_data\.get\(k\)\s*for k in\s*\[)([^\]]*)(\]\))",
        r"\1\2, \"cargo_name\", \"pkg_type\", \"weight_kg\", \"volume_cbm\"\3",
        f, count=1
    )
    changed = True
    print("  ✓ validator LineFormSet ikut mempertimbangkan cargo fields")

if changed:
    FORMS.write_text(f, encoding="utf-8")
else:
    print("  • forms.py tidak perlu diubah (sudah sesuai)")

# 3) TEMPLATE DETAIL: tampilkan cargo kolom di tabel lines
if TPL_DETAIL.exists():
    backup(TPL_DETAIL)
    t = TPL_DETAIL.read_text(encoding="utf-8")
    t_changed = False

    # header kolom cargo (setelah No)
    if "<th>Cargo</th>" not in t:
        t = t.replace(
            '<th style="width:60px;">No</th>',
            '<th style="width:60px;">No</th><th>Cargo</th>'
        )
        t_changed = True
    # tambahkan cell cargo_name (setelah nomor)
    if "{{ line.cargo_name }}" not in t:
        t = t.replace(
            '<td>{{ forloop.counter }}</td>\n              <td>{{ line.origin }}</td>',
            '<td>{{ forloop.counter }}</td>\n              <td>{{ line.cargo_name }}</td>\n              <td>{{ line.origin }}</td>'
        )
        t_changed = True

    # (opsional) tampilkan detail cargo kecil di deskripsi
    if "{{ line.pkg_type }}" not in t:
        t = t.replace(
            '<td>{{ line.description }}</td>',
            '<td>{% if line.pkg_type or line.weight_kg or line.volume_cbm %}'
            '<div class="small text-body-secondary">'
            '{% if line.pkg_type %}{{ line.pkg_type }} · {% endif %}'
            '{% if line.weight_kg %}{{ line.weight_kg }} kg · {% endif %}'
            '{% if line.volume_cbm %}{{ line.volume_cbm }} cbm{% endif %}'
            '</div>{% endif %}{{ line.description }}</td>'
        )
        t_changed = True

    if t_changed:
        TPL_DETAIL.write_text(t, encoding="utf-8")
        print("  ✓ quotation_detail.html ditambah kolom Cargo")
    else:
        print("  • quotation_detail.html sudah menampilkan Cargo")
else:
    print("  • template detail tidak ditemukan — lewati")

# 4) TEMPLATE WIZARD: tambahkan kolom cargo di Step 3 (Lines per Destination)
if TPL_WIZ.exists():
    backup(TPL_WIZ)
    w = TPL_WIZ.read_text(encoding="utf-8")
    w_changed = False

    # Tambah header kolom Cargo di tabel lines
    if "<th>Cargo</th>" not in w and "Lines per Destination" in w:
        w = w.replace(
            "<th>Origin</th><th>Charge</th><th>Description</th><th>Unit</th>",
            "<th>Cargo</th><th>Origin</th><th>Charge</th><th>Description</th><th>Unit</th>"
        )
        w_changed = True

    # Tambah input form cargo_name sebelum origin
    if "{{ lf.cargo_name }}" not in w:
        w = w.replace(
            "<td>{{ lf.origin }}</td>",
            "<td>{{ lf.cargo_name }}</td><td>{{ lf.origin }}</td>"
        )
        w_changed = True

    # (opsional) tambahkan pkg_type/weight/volume di kolom description baris input
    if "{{ lf.pkg_type }}" not in w:
        w = w.replace(
            "<td>{{ lf.description }}</td>",
            "<td><div class=\"row g-2\">"
            "<div class=\"col-12\">{{ lf.description }}</div>"
            "<div class=\"col-4\">{{ lf.pkg_type }}</div>"
            "<div class=\"col-4\">{{ lf.weight_kg }}</div>"
            "<div class=\"col-4\">{{ lf.volume_cbm }}</div>"
            "</div></td>"
        )
        w_changed = True

    if w_changed:
        TPL_WIZ.write_text(w, encoding="utf-8")
        print("  ✓ quotation_wizard.html: kolom Cargo ditambahkan")
    else:
        print("  • wizard template sudah memuat Cargo")

print("\nSelesai ✅")
print("Jalankan:")
print("  python manage.py makemigrations sales")
print("  python manage.py migrate")
print("  python manage.py runserver")
