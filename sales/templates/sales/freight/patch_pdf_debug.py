from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

IMPORTS = textwrap.dedent("""
import sys, asyncio
from django.conf import settings
from django.template.loader import render_to_string, get_template
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
""").strip()

HELPERS = textwrap.dedent(r"""
async def _html_to_pdf_playwright(html: str, base_url: str) -> bytes:
    # Sisipkan <base href> agar asset relatif resolve (static/img/css)
    if "<head>" in html:
        html = html.replace("<head>", f"<head><base href=\\"{base_url}\\">", 1)
    else:
        html = f"<head><base href=\\"{base_url}\\"></head>{html}"

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(html, wait_until="networkidle")
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

FUNC = textwrap.dedent(r"""
def freight_pdf(request, pk: int):
    from .models import FreightQuotation, FreightCargo  # FreightCharge tak perlu langsung
    # Ambil data
    q = get_object_or_404(
        FreightQuotation.objects.select_related("customer").prefetch_related(
            Prefetch("cargos", queryset=FreightCargo.objects.prefetch_related("charges"))
        ),
        pk=pk
    )
    # Hitung data untuk template
    cargo_rows, subtotal, vat, grand_total = _compute_totals(q)

    # Pastikan template bisa ditemukan & log asalnya
    tpl_name = "sales/freight/pdf.html"
    tpl = get_template(tpl_name)
    tpl_origin = getattr(getattr(tpl, "origin", None), "name", "(unknown)")
    print(f"PDF DEBUG: using template={tpl_name} origin={tpl_origin}", file=sys.stderr, flush=True)

    ctx = {
        "q": q,
        "cargo_rows": cargo_rows,
        "subtotal": subtotal,
        "vat": vat,
        "grand_total": grand_total,
        "request": request,
        # inject settings agar {{ settings.COMPANY_NAME }} bisa dipakai jika Anda memilih cara cepat
        "settings": settings,
    }
    html = tpl.render(ctx, request=request)

    # Jika ?debug=1 → tampilkan HTML mentah untuk verifikasi branding/isi
    if request.GET.get("debug") == "1":
        # sisipkan banner kecil supaya jelas ini dari DEBUG
        banner = '<div style="background:#fffae6;border:1px solid #eed;padding:8px;margin-bottom:8px;font-size:12px">[DEBUG HTML PREVIEW] Template: ' + tpl_name + ' (' + tpl_origin + ')</div>'
        return HttpResponse(banner + html)

    # Render via Playwright (tanpa fallback) agar error asli terlihat bila gagal
    base_url = request.build_absolute_uri("/")
    pdf_bytes = asyncio.run(_html_to_pdf_playwright(html, base_url))

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
    for line in IMPORTS.splitlines():
        if line and line not in src:
            src = line + "\n" + src
    return src

def inject_helpers(src: str) -> str:
    if "_html_to_pdf_playwright" not in src:
        src += "\n\n" + HELPERS + "\n"
        print("[add]   injected _html_to_pdf_playwright helper")
    return src

def replace_func(src: str) -> str:
    pat = re.compile(r"\ndef\s+freight_pdf\s*\(.*?\):[\s\S]*?(?=\n\ndef\s+|\Z)", re.M)
    if pat.search(src):
        src = pat.sub("\n\n" + FUNC + "\n\n", src)
        print("[edit] replaced freight_pdf() with debug version")
    else:
        src += "\n\n" + FUNC + "\n"
        print("[add]  added freight_pdf() debug version")
    return src

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")
    src = ensure_imports(src)
    src = inject_helpers(src)
    src = replace_func(src)
    src = re.sub(r"\n{3,}", "\n\n", src)
    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] patched sales/views.py (debuggable PDF)")
    print("\nUji:")
    print(" - HTML preview:  /sales/quotations/freight/<id>/pdf/?debug=1")
    print(" - PDF render   : /sales/quotations/freight/<id>/pdf/")
    print("Lihat console untuk log: 'PDF DEBUG: using template=...'")

if __name__ == "__main__":
    main()
