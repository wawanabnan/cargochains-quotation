# patch_pdf_speed.py
from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

IMPORTS = textwrap.dedent("""
import asyncio
from django.template.loader import render_to_string, get_template
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
""").strip()

HELPER = textwrap.dedent(r"""
# ========== FAST PLAYWRIGHT SINGLETON ==========
# Reuse 1 browser/context untuk semua request → hemat ~0.5–2 detik/request.
_PW_BROWSER = None
_PW_CONTEXT = None

async def _ensure_pw():
    global _PW_BROWSER, _PW_CONTEXT
    if _PW_BROWSER is not None and _PW_CONTEXT is not None:
        return _PW_BROWSER, _PW_CONTEXT

    from playwright.async_api import async_playwright
    _pw = await async_playwright().start()
    # headless True default; kalau butuh debug ganti ke False
    _PW_BROWSER = await _pw.chromium.launch()
    # JS dimatikan agar lebih cepat & deterministik (kalau template tidak perlu JS)
    _PW_CONTEXT = await _PW_BROWSER.new_context(
        java_script_enabled=False,            # <= percepat
        device_scale_factor=1.0
    )
    return _PW_BROWSER, _PW_CONTEXT

async def _html_to_pdf_playwright_fast(html: str, base_url: str) -> bytes:
    # Sisip <base> agar URL relatif resolve ke host Anda
    if "<head>" in html:
        html = html.replace("<head>", f"<head><base href=\\"{base_url}\\">", 1)
    else:
        html = f"<head><base href=\\"{base_url}\\"></head>{html}"

    browser, context = await _ensure_pw()
    page = await context.new_page()

    # Blok semua request yang bukan dari base_url (mis. analytics/CDN) → lebih cepat & stabil
    async def _route(route):
        url = route.request.url
        if url.startswith(base_url) or "/static/" in url:
            await route.continue_()
        else:
            await route.abort()
    await page.route("**/*", _route)

    # Muat konten; 'load' cukup (lebih cepat dari 'networkidle')
    await page.set_content(html, wait_until="load")

    # Media print agar ukuran/margin konsisten
    await page.emulate_media(media="print")

    pdf_bytes = await page.pdf(
        format="A4",
        print_background=True,
        prefer_css_page_size=True,
        margin={"top": "12mm", "right": "12mm", "bottom": "12mm", "left": "12mm"},
    )

    await page.unroute("**/*", _route)
    await page.close()
    return pdf_bytes
# ========== /FAST PLAYWRIGHT SINGLETON ==========
""").strip()

FUNC = textwrap.dedent(r"""
def freight_pdf(request, pk: int):
    from .models import FreightQuotation, FreightCargo
    q = get_object_or_404(
        FreightQuotation.objects.select_related("customer").prefetch_related(
            Prefetch("cargos", queryset=FreightCargo.objects.prefetch_related("charges"))
        ),
        pk=pk
    )
    cargo_rows, subtotal, vat, grand_total = _compute_totals(q)

    # Render HTML (pakai request=request agar context processors aktif)
    ctx = {
        "q": q,
        "cargo_rows": cargo_rows,
        "subtotal": subtotal,
        "vat": vat,
        "grand_total": grand_total,
        "request": request,
    }
    html = render_to_string("sales/freight/pdf.html", ctx, request=request)

    base_url = request.build_absolute_uri("/")
    # Pakai versi cepat yang reuse browser
    pdf_bytes = asyncio.run(_html_to_pdf_playwright_fast(html, base_url))

    filename = f"{q.number or f'Quotation-{q.id}'}.pdf"
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    # inline (tab baru tergantung link target="_blank")
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

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")

    # Tambah import bila belum ada
    for line in IMPORTS.splitlines():
        if line and line not in src:
            src = line + "\n" + src

    # Sisip/replace helper
    if "_html_to_pdf_playwright_fast" in src:
        # replace block lama
        src = re.sub(
            r"# ========== FAST PLAYWRIGHT SINGLETON ==========[\s\S]*?# ========== /FAST PLAYWRIGHT SINGLETON ==========",
            HELPER,
            src,
            flags=re.M
        )
        print("[edit] updated fast Playwright helper")
    else:
        src += "\n\n" + HELPER + "\n"
        print("[add]  inserted fast Playwright helper")

    # Replace freight_pdf()
    if re.search(r"\ndef\s+freight_pdf\s*\(", src):
        src = re.sub(r"\ndef\s+freight_pdf\s*\(.*?\):[\s\S]*?(?=\n\ndef\s+|\Z)", "\n\n" + FUNC + "\n\n", src, flags=re.M)
        print("[edit] replaced freight_pdf with fast version")
    else:
        src += "\n\n" + FUNC + "\n"
        print("[add]  added freight_pdf fast version")

    # Rapikan
    src = re.sub(r"\n{3,}", "\n\n", src)
    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] Patched views for faster PDF via Playwright.")

if __name__ == "__main__":
    main()
