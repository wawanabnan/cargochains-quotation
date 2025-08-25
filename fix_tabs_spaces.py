from pathlib import Path

ROOT = Path(__file__).resolve().parent
SALES_DIR = ROOT / "sales"

def fix_file(path: Path):
    text = path.read_text(encoding="utf-8")
    if "\t" not in text:
        return False  # tidak ada tab
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
        print(f"• backup -> {backup.name}")
    # replace tab dengan 4 spasi
    fixed = text.replace("\t", "    ")
    path.write_text(fixed, encoding="utf-8")
    return True

print("== Fix Tabs → Spaces ==")
if not SALES_DIR.exists():
    print(f"Folder {SALES_DIR} tidak ditemukan")
else:
    for pyfile in SALES_DIR.rglob("*.py"):
        if fix_file(pyfile):
            print(f"✓ fixed: {pyfile}")
        else:
            print(f"• ok (no tab): {pyfile}")

print("\nSelesai ✅. Semua tab sudah diganti 4 spasi.")
print("Sekarang coba lagi runserver:")
print("  python manage.py runserver")
