from pathlib import Path
import re, shutil, datetime

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
SETTINGS = ROOT / "config" / "settings.py"  # ⬅️ sesuaikan kalau nama/settings path berbeda

def backup(fp: Path):
    if fp.exists():
        bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
        shutil.copy2(fp, bak)
        print(f"[backup] {fp} -> {bak.name}")

def main():
    if not SETTINGS.exists():
        print(f"[ERR] {SETTINGS} tidak ditemukan, sesuaikan path di script.")
        return

    backup(SETTINGS)
    src = SETTINGS.read_text(encoding="utf-8")

    if "core.context_processors.company" in src:
        print("[skip] Sudah ada context processor company.")
    else:
        pattern = r"('django\.contrib\.messages\.context_processors\.messages',)"
        repl = r"\1\n                'core.context_processors.company',"
        new_src, n = re.subn(pattern, repl, src)
        if n == 0:
            print("[warn] Tidak ketemu posisi context_processors, sisipkan manual.")
            return
        SETTINGS.write_text(new_src, encoding="utf-8")
        print("[ok] Ditambahkan 'core.context_processors.company' ke settings.py")

if __name__ == "__main__":
    main()
