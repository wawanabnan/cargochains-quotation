# patch_pdf_brand_fix.py
from pathlib import Path
import re, shutil, datetime, textwrap, os

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "sales" / "views.py"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

BRAND_IMPORTS = """from django.conf import settings
from django.contrib.staticfiles import finders
import os
"""

BRAND_FUNC = r"""
def _brand_header(c, W, H, margin_x, company_name=None, company_tagline=None, logo_static_path="img/company_logo.png"):
    y_top = H - 18*mm
    x = margin_x

    # 1) resolve logo path: staticfiles → BASE_DIR/static
    logo_path = None
    try:
        logo_path = finders.find(logo_static_path)
    except Exception:
        logo_path = None
    if not logo_path:
        try:
            base = getattr(settings, "BASE_DIR", None)
            if base:
                cand = os.path.join(base, "static", *logo_static_path.split("/"))
                if os.path.exists(cand):
                    logo_path = cand
        except Exception:
            logo_path = None

    # 2) draw logo (optional)
    if logo_path:
        try:
            target_h = 12*mm
            c.drawImage(logo_path, x, y_top - target_h + 2,
                        height=target_h, preserveAspectRatio=True, mask='auto')
            x += (target_h * 3) + 6  # geser teks setelah logo (perkiraan aspek)
        except Exception:
            pass

    # 3) company name/tagline (selalu tampil)
    if not company_name:
        company_name = getattr(settings, "COMPANY_NAME", "Your Company Name")
    if company_tagline is None:
        company_tagline = getattr(settings, "COMPANY_TAGLINE", "")

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y_top, str(company_name))

    if company_tagline:
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawString(x, y_top - 12, str(company_tagline))
        c.setFillColor(colors.black)

    # 4) date on right
    c.setFont("Helvetica", 9)
    c.drawRightString(W - margin_x, y_top, f"Date: {datetime.date.today().isoformat()}")

    # underline
    c.line(margin_x, y_top - 16, W - margin_x, y_top - 16)
    return y_top - 20
"""

def backup(fp: Path):
    if fp.exists():
        bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
        shutil.copy2(fp, bak)
        print(f"[backup] {fp.name} -> {bak.name}")

def ensure_imports(src: str) -> str:
    for line in BRAND_IMPORTS.splitlines():
        if line and line not in src:
            src = line + "\n" + src
    return src

def replace_brand_func(src: str) -> str:
    # hapus definisi _brand_header lama (jika ada) lalu sisipkan baru
    pat = re.compile(r"\ndef\s+_brand_header\s*\(.*?\):[\s\S]*?(?=\n\ndef\s+|\Z)", re.M)
    if pat.search(src):
        src = pat.sub("\n\n" + BRAND_FUNC + "\n\n", src)
        print("[edit] _brand_header replaced")
    else:
        src += "\n\n" + BRAND_FUNC + "\n"
        print("[add]  _brand_header added")
    return src

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")
    src = ensure_imports(src)
    src = replace_brand_func(src)
    src = re.sub(r"\n{3,}", "\n\n", src)
    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] Patched branding in sales/views.py")
    print("\nKonfigurasi opsional di settings.py:")
    print('  COMPANY_NAME = "PT. Nusantara Logistik"')
    print('  COMPANY_TAGLINE = "Integrated Freight & Charter Services"')
    print('  COMPANY_LOGO_STATIC = "img/company_logo.png"  # path relatif ke static/')
    print("\nPastikan file logo ada di: <BASE_DIR>/static/img/company_logo.png (atau ubah COMPANY_LOGO_STATIC).")

if __name__ == "__main__":
    main()
