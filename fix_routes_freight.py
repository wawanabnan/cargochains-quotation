from pathlib import Path
import re, shutil, datetime

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

# cari di app dan templates
TARGET_DIRS = [
    ROOT / "sales",
    ROOT / "templates",
]

REPLS = [
    (r"'sales:quotation_list'",  "'sales:freight_list'"),
    (r'"sales:quotation_list"',  '"sales:freight_list"'),
    (r"'sales:quotation_detail'", "'sales:freight_view'"),
    (r'"sales:quotation_detail"', '"sales:freight_view"'),
    (r"'sales:freight_quotation_create'", "'sales:freight_create'"),
    (r'"sales:freight_quotation_create"', '"sales:freight_create"'),
]

EXTS = {".py", ".html", ".txt"}

def patch_file(p: Path):
    try:
        txt = p.read_text(encoding="utf-8")
    except Exception:
        return False
    orig = txt
    for pat, rep in REPLS:
        txt = re.sub(pat, rep, txt)
    if txt != orig:
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        p.write_text(txt, encoding="utf-8")
        print(f"[patched] {p} (backup: {bak.name})")
        return True
    return False

def main():
    changed = 0
    for base in TARGET_DIRS:
        if not base.exists(): 
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXTS:
                if patch_file(p):
                    changed += 1
    if changed == 0:
        print("No occurrences found. (Sudah bersih atau lokasi berbeda)")
    else:
        print(f"\n✅ Selesai. File diubah: {changed}")
        print("➡ Restart server dan reload halaman /sales/quotations/freight/")

if __name__ == "__main__":
    main()
