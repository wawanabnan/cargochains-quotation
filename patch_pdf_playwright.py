from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

PLAYWRIGHT_IMPORTS = textwrap.dedent("""
import asyncio
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
""").strip()

PLAYWRIGHT_HELPERS = textwrap.dedent(r"""
# === Playwright PDF helpers ===

def _render_pdf_reportlab_min(q):
    # Fallback super-minimal (anti hang)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    x, y = 20*mm, H - 25*mm
    c.setFont("Helvetica-Bold", 14); c.drawString(x, y, "Quotation")
    c.setFont("Helvetica", 10)
    y -= 6*mm; c.drawString(x, y, f"Number   : {q.number or q.id}")
    y -= 6*mm; c.drawString(x, y, f"Date     : {q.date}")
    y -= 6*mm; c.drawString(x, y, f"Customer : {q.customer}")
    y -= 6*mm; c.drawString(x, y, f"Mode     : {q.get_transport_mode_display()} / {q.get_service_option_display()}")
    c.showPage(); c.save()
    pdf = buf.getvalue(); buf.close()
    return pdf

async def _html_to_pdf_playwright(html: str, base_url: str) -> bytes:
    # Render HTML -> PDF via headless Chromium (Playwright).
    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        raise RuntimeError("Playwright tidak tersedia") from e

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(html, base_url=base_url, wait_until="networkidle")
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "12mm", "right": "12mm", "bottom": "12mm", "left": "12mm"},
        )
        await context.close()
        await browser.close()
        return pdf_bytes
""").strip()

FREIGHT_PDF_FN = textwrap.dedent(r"""
def freight_pdf(request, pk: int):
    from .models import FreightQuotation, FreightCargo, FreightCharge
    q = get_object_or_404(
        FreightQuotation.objects.select_related("customer").prefetch_related(
            Prefetch("cargos", queryset=FreightCargo.objects.prefetch_related("charges"))
        ),
        pk=pk
    )
    cargo_rows, subtotal, vat, grand_total = _compute_totals(q)

    # Render template HTML
    ctx = {
        "q": q,
        "cargo_rows": cargo_rows,
        "subtotal": subtotal,
        "vat": vat,
        "grand_total": grand_total,
        "request": request,
    }
    html = render_to_string("sales/freight/pdf.html", ctx)
    base_url = request.build_absolute_uri("/")

    try:
        pdf_bytes = asyncio.run(_html_to_pdf_playwright(html, base_url))
    except Exception:
        pdf_bytes = _render_pdf_reportlab_min(q)

    filename = f"{q.number or f'Quotation-{q.id}'}.pdf"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    if request.GET.get("dl") == "1":
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    else:
        resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp
""").strip()

def backup(fp: Path):
    if fp.exists():
        bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
        shutil.copy2(fp, bak)
        print(f"[backup] {fp} -> {bak.name}")

def ensure_imports(src: str) -> str:
    for line in PLAYWRIGHT_IMPORTS.splitlines():
        if line and line not in src:
            src = line + "\n" + src
    return src

def inject_helpers(src: str) -> str:
    if "_html_to_pdf_playwright" not in src:
        src += "\n\n" + PLAYWRIGHT_HELPERS + "\n"
        print("[add]   Playwright helpers injected")
    return src

def replace_pdf_func(src: str) -> str:
    pat = re.compile(r"\ndef\s+freight_pdf\s*\(.*?\):[\s\S]*?(?=\n\ndef\s+|\Z)", re.M)
    if pat.search(src):
        src = pat.sub("\n\n" + FREIGHT_PDF_FN + "\n\n", src)
        print("[edit] Replaced freight_pdf() with Playwright version")
    else:
        src += "\n\n" + FREIGHT_PDF_FN + "\n"
        print("[add]  Added freight_pdf() Playwright version")
    return src

def tidy(src: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", src)

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")
    src = ensure_imports(src)
    src = inject_helpers(src)
    src = replace_pdf_func(src)
    src = tidy(src)
    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] Patched sales/views.py: Playwright PDF + ReportLab fallback")
    print("\n✅ Done. Test: /sales/quotations/freight/<id>/pdf/")
    print("  - inline by default, add ?dl=1 to force download.")
    print("  - If Playwright not available, fallback ReportLab minimal will be used.")

if __name__ == "__main__":
    main()
