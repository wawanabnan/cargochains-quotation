from pathlib import Path
import re, shutil, datetime

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def fix_urls():
    p = ROOT / "sales" / "urls.py"
    if not p.exists():
        print("[ERR] sales/urls.py not found")
        return
    backup(p)
    src = p.read_text(encoding="utf-8")

    # Pastikan import & app_name ada
    if "from django.urls import path" not in src:
        src = "from django.urls import path\n" + src
    if "from . import views" not in src:
        src = "from . import views\n" + src
    if "app_name =" not in src:
        src = "app_name = 'sales'\n" + src

    # Hapus semua baris path untuk NEW yang tidak sesuai
    # dan sisakan satu dengan name='freight_new'
    lines = src.splitlines()
    new_lines = []
    for line in lines:
        if "path(" in line and "quotations/freight/new/" in line:
            # skip semua baris 'new' dulu; akan kita tulis ulang
            continue
        new_lines.append(line)

    # Sisipkan satu definisi yang benar (kalau belum ada)
    joined = "\n".join(new_lines)
    if "freight_new" not in joined:
        # cari posisi setelah baris urlpatterns = [
        m = re.search(r"(urlpatterns\s*=\s*\[)", joined)
        if m:
            i = m.end()
            joined = joined[:i] + "\n    path('quotations/freight/new/', views.freight_create_wizard, name='freight_new')," + joined[i:]
        else:
            # fallback: tambahkan blok urlpatterns minimal
            joined += "\n\nurlpatterns = [\n    path('quotations/freight/new/', views.freight_create_wizard, name='freight_new'),\n]\n"

    # Rapikan duplikat koma ganda, dll
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    p.write_text(joined, encoding="utf-8")
    print("[ok] sales/urls.py -> hanya pakai name='freight_new' untuk /quotations/freight/new/")

def replace_in_files():
    # Ganti semua referensi 'sales:freight_create' -> 'sales:freight_new'
    # di templates dan views
    targets = []
    for folder in ["templates", "sales"]:
        base = ROOT / folder
        if base.exists():
            for path in base.rglob("*.*"):
                if path.suffix.lower() in {".html", ".py"}:
                    targets.append(path)

    for path in targets:
        txt = path.read_text(encoding="utf-8", errors="ignore")
        new_txt = txt.replace("sales:freight_create", "sales:freight_new") \
                     .replace("reverse('sales:freight_create')", "reverse('sales:freight_new')") \
                     .replace('url "sales:freight_create"', 'url "sales:freight_new"')
        if new_txt != txt:
            backup(path)
            path.write_text(new_txt, encoding="utf-8")
            print(f"[patched] {path}")

if __name__ == "__main__":
    fix_urls()
    replace_in_files()
    print("\n✅ Selesai. Sekarang route create hanya: name='freight_new'.")
    print("   Jika kamu lebih suka nama 'freight_create', bilang ya — saya siapkan skrip kebalikannya.")
