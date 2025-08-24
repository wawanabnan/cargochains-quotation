import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
assert (ROOT / "manage.py").exists(), "Jalankan dari root project (yang ada manage.py)."

VIEWS = ROOT / "sales" / "views.py"
TPL   = ROOT / "sales" / "templates" / "sales" / "quotation_wizard.html"

def backup(p: Path):
    if not p.exists():
        return
    bak = p.with_suffix(p.suffix + ".bak")
    if not bak.exists():
        bak.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  • backup {p} -> {bak}")

print("== Patch Wizard non_form_errors ==")

# ---- 1) Patch TEMPLATE
if not TPL.exists():
    print(f"[TEMPLATE] Lewati: {TPL} tidak ditemukan.")
else:
    print("[TEMPLATE] Patching quotation_wizard.html ...")
    backup(TPL)
    t = TPL.read_text(encoding="utf-8")

    # Ganti semua referensi _non_form_errors -> non_form_errors (aman dipanggil di template)
    t_new = t.replace("fs._non_form_errors", "fs.non_form_errors")

    # Jaga-jaga: jika ada blok if/for yang pakai _non_form_errors tanpa prefix fs (jarang)
    t_new = t_new.replace("._non_form_errors", ".non_form_errors")
    t_new = t_new.replace("_non_form_errors", "non_form_errors")

    if t_new != t:
        TPL.write_text(t_new, encoding="utf-8")
        print("  ✓ Diganti ke fs.non_form_errors di template")
    else:
        print("  ✓ Tidak ada '_non_form_errors' tersisa di template")

# ---- 2) Patch VIEWS
if not VIEWS.exists():
    print(f"[VIEWS] Lewati: {VIEWS} tidak ditemukan.")
else:
    print("[VIEWS] Patching views.py ...")
    backup(VIEWS)
    v = VIEWS.read_text(encoding="utf-8")
    changed = False

    # a) Pastikan import ErrorList ada
    if "from django.forms.utils import ErrorList" not in v:
        # Selipkan dekat import lain
        if "from django.shortcuts" in v:
            v = v.replace("from django.shortcuts", "from django.forms.utils import ErrorList\nfrom django.shortcuts")
        else:
            v = "from django.forms.utils import ErrorList\n" + v
        changed = True
        print("  ✓ Import ErrorList ditambahkan")

    # b) Bungkus penetapan fs._non_form_errors dengan ErrorList([...])
    # Contoh: fs._non_form_errors = ["Minimal 1 line ..."]
    #         fs._non_form_errors = [f"...{i+1}..."]
    pattern = r"(fs\._non_form_errors\s*=\s*)(\[[^\n]*?\])"
    v2 = re.sub(pattern, r"\1ErrorList(\2)", v)
    if v2 != v:
        v = v2
        changed = True
        print("  ✓ Penetapan _non_form_errors dibungkus ErrorList([...])")

    # c) (opsional) kalau ada penggunaan ._non_form_errors lain, biarkan—template sudah diganti pakai accessor method
    #    Namun jika Anda ingin konsisten penuh, bisa ganti akses lainnya.
    #    Tidak kami ubah di sini agar minimal invasive.

    if changed:
        VIEWS.write_text(v, encoding="utf-8")
        print("  ✓ views.py tersimpan")
    else:
        print("  ✓ Tidak ada perubahan diperlukan di views.py")

print("\nSelesai ✅")
print("Reload halaman wizard. Jika masih ada error, kirimkan baris error & potongan kode terkait, saya patch lagi.")
