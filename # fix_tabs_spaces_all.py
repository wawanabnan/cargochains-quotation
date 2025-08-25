# fix_tabs_spaces_all.py
# python fix_tabs_spaces_all.py --dry-run
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    "venv", ".venv", "env", ".env",
    "node_modules",
}

def should_skip(path: Path) -> bool:
    parts = set(p.name for p in path.parents)
    return bool(parts & SKIP_DIRS)

def fix_file(path: Path, dry_run: bool = False) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        print(f"! gagal baca: {path}")
        return False

    if "\t" not in text:
        return False

    if dry_run:
        return True

    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    fixed = text.replace("\t", "    ")
    path.write_text(fixed, encoding="utf-8")
    return True

def main():
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    changed = 0
    scanned = 0

    print("== Fix Tabs → Spaces (project-wide) ==")
    for py in ROOT.rglob("*.py"):
        # lewati file di folder yang di-skip
        if should_skip(py):
            continue
        scanned += 1
        will_change = fix_file(py, dry_run=dry_run)
        if will_change:
            changed += 1
            print(("• would fix: " if dry_run else "✓ fixed: ") + str(py))

    print("\nSelesai ✅")
    print(f"File .py dipindai: {scanned}")
    if dry_run:
        print(f"File yang butuh perbaikan (ada TAB): {changed}")
        print("Jalankan tanpa --dry-run untuk menerapkan perubahan.")
    else:
        print(f"File yang diperbaiki (TAB → 4 spasi): {changed}")
        print("Backup .bak dibuat untuk setiap file yang diubah.")

    print("\nOpsional, cek lagi konsistensi indentasi:")
    print("  python -m tabnanny .")

if __name__ == "__main__":
    main()
