from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

REPORTLAB_IMPORTS = textwrap.dedent("""
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
""").strip()

PDF_FUNC = textwrap.dedent("""
def freight_pdf(request, pk: int):
    # PDF minimal dan stabil (tanpa HTML renderer)
    q = get_object_or_404(FreightQuotation, pk=pk)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    x, y = 20*mm, H - 25*mm

    # Header ringkas
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, "Quotation")
    c.setFont("Helvetica", 10)
    y -= 6*mm; c.drawString(x, y, f"Number   : {q.number or q.id}")
    y -= 6*mm; c.drawString(x, y, f"Date     : {q.date}")
    y -= 6*mm; c.drawString(x, y, f"Customer : {q.customer}")
    y -= 6*mm; c.drawString(x, y, f"Mode     : {q.get_transport_mode_display()} / {q.get_service_option_display()}")

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()

    filename = f"{q.number or f'Quotation-{q.id}'}.pdf"
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
""").strip()

def backup(fp: Path):
    if fp.exists():
        bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
        shutil.copy2(fp, bak)
        print(f"[backup] {fp} -> {bak.name}")

def add_missing_imports(src: str) -> str:
    # Pastikan import umum ada
    needed = [
        ("from django.http import HttpResponse", r"\bHttpResponse\b"),
        ("from django.shortcuts import get_object_or_404", r"\bget_object_or_404\b"),
    ]
    for line, token in needed:
        if not re.search(token, src):
            if line not in src:
                src = line + "\n" + src

    # Tambah import ReportLab & BytesIO kalau belum ada
    if "reportlab.pdfgen" not in src:
        src = REPORTLAB_IMPORTS + "\n" + src
    # Pastikan BytesIO terimport
    if "from io import BytesIO" not in src:
        src = "from io import BytesIO\n" + src

    return src

def strip_conflicting_imports(src: str) -> str:
    # Hapus import WeasyPrint dan xhtml2pdf kalau ada
    src = re.sub(r"^.*from\s+weasyprint\s+import\s+.*?$", "", src, flags=re.M)
    src = re.sub(r"^.*from\s+xhtml2pdf\s+import\s+.*?$", "", src, flags=re.M)
    return src

def replace_freight_pdf(src: str) -> str:
    # Ganti definisi freight_pdf lama dengan yang baru
    pat = re.compile(r"\ndef\s+freight_pdf\s*\(request\s*,\s*pk\s*:\s*int\)\s*:[\s\S]*?(?=\n\ndef\s+|\Z)", re.M)
    if pat.search(src):
        src = pat.sub("\n\n" + PDF_FUNC + "\n\n", src)
        print("[edit] Replaced existing freight_pdf()")
    else:
        # Tidak ketemu; append di akhir
        if not src.endswith("\n"): src += "\n"
        src += "\n\n" + PDF_FUNC + "\n"
        print("[add]   Appended new freight_pdf()")
    return src

def tidy_blank_lines(src: str) -> str:
    # Rapikan blank lines berlebih
    src = re.sub(r"\n{3,}", "\n\n", src)
    return src

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return

    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")

    src = strip_conflicting_imports(src)
    src = add_missing_imports(src)
    src = replace_freight_pdf(src)
    src = tidy_blank_lines(src)

    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] Patched sales/views.py -> ReportLab minimal PDF")

    print("\n✅ Selesai. Coba akses lagi /sales/quotations/freight/<id>/pdf/")
    print("Jika masih loading, cek console server: pastikan request masuk ke freight_pdf baru ini.")

if __name__ == "__main__":
    main()
