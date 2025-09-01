# sales/management/commands/warmup_freight_pdfs.py
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.apps import apps
from django.conf import settings
from pathlib import Path
import hashlib
import os

# --- Fallback Playwright helper (pakai core.pdf_service kalau ada) ---
try:
    from core.pdf_service import html_to_pdf_bytes  # gunakan service jika tersedia
except Exception:
    # fallback minimal agar command tetap jalan
    from playwright.sync_api import sync_playwright
    _pw = None
    _browser = None

    def _get_browser():
        global _pw, _browser
        if _browser:
            return _browser
        _pw = sync_playwright().start()
        # prefer channel msedge/chrome di Windows dev
        for ch in [os.getenv("PDF_BROWSER_CHANNEL", "").strip().lower() or None, "msedge", "chrome", None]:
            try:
                kw = dict(headless=True, args=["--disable-gpu", "--disable-extensions", "--no-first-run"])
                if ch:
                    kw["channel"] = ch
                _browser = _pw.chromium.launch(**kw)
                return _browser
            except Exception:
                continue
        _browser = _pw.chromium.launch(headless=True)
        return _browser

    def html_to_pdf_bytes(html: str, base_url: str) -> bytes:
        # sisipkan <base>
        if "<head>" in html:
            html = html.replace("<head>", f'<head><base href="{base_url}">', 1)
        else:
            html = f'<head><base href="{base_url}"></head>{html}'
        browser = _get_browser()
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()

        def _route(route, request):
            u = request.url
            if u.startswith(base_url) or "/static/" in u:
                route.continue_()
            else:
                route.abort()
        page.route("**/*", _route)

        page.set_content(html, wait_until="load")
        page.emulate_media(media="print")
        pdf = page.pdf(
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "12mm", "right": "12mm", "bottom": "12mm", "left": "12mm"},
        )
        page.unroute("**/*", _route)
        context.close()
        return pdf

# --- Fingerprint & cache path (lokal, tidak perlu core/pdf_cache.py) ---
TEMPLATE_VERSION = "v1"

def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]

def quotation_fingerprint(q) -> str:
    parts = [
        str(q.pk or ""),
        str(getattr(q, "number", "")),
        str(getattr(q, "customer_id", "")),
        str(getattr(q, "origin_id", "")),
        str(getattr(q, "destination_id", "")),
        str(getattr(q, "transport_mode", "")),
        str(getattr(q, "updated_at", "")),
        TEMPLATE_VERSION,
    ]
    try:
        parts.append(f"c{getattr(q, 'freightcargo_set').count()}")
    except Exception:
        parts.append("c0")
    try:
        parts.append(f"r{getattr(q, 'freightcharge_set').count()}")
    except Exception:
        parts.append("r0")

    subtotal = getattr(q, "subtotal", 0) or 0
    vat = getattr(q, "vat_amount", 0) or 0
    grand = getattr(q, "grand_total", subtotal + vat) or (subtotal + vat)
    parts += [str(subtotal), str(vat), str(grand)]
    return _hash("|".join(parts))

def cache_path_for(q, safe_basename: str) -> Path:
    media_root = Path(getattr(settings, "MEDIA_ROOT", "."))
    out_dir = media_root / "quotations_pdf"
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = quotation_fingerprint(q)
    return out_dir / f"{safe_basename}__{fp}.pdf"

# --- Model ---
FreightQuotation = apps.get_model("sales", "FreightQuotation")

class Command(BaseCommand):
    help = "Generate & cache all Freight Quotation PDFs into MEDIA_ROOT/quotations_pdf/."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            default="http://127.0.0.1:8000/",
            help="Base URL for resolving static files (default: http://127.0.0.1:8000/)",
        )

    def handle(self, *args, **opts):
        base_url = opts["domain"].rstrip("/") + "/"
        count_gen, count_skip = 0, 0

        for q in FreightQuotation.objects.all():
            safe_name = (q.number or f"Quotation-{q.pk}").replace("/", "-")
            out_file = cache_path_for(q, safe_name)
            if out_file.exists():
                count_skip += 1
                continue

            ctx = {
                "q": q,
                # tambahkan bila template butuh:
                # "cargo_rows": q.freightcargo_set.all(),
                # "charges": q.freightcharge_set.all(),
                "subtotal": getattr(q, "subtotal", 0) or 0,
                "vat": getattr(q, "vat_amount", 0) or 0,
                "grand_total": (getattr(q, "grand_total", None)
                                or (getattr(q, "subtotal", 0) or 0)
                                + (getattr(q, "vat_amount", 0) or 0)),
            }
            html = render_to_string("sales/freight/pdf.html", ctx)
            pdf_bytes = html_to_pdf_bytes(html, base_url)
            out_file.write_bytes(pdf_bytes)
            count_gen += 1

        self.stdout.write(self.style.SUCCESS(
            f"Warm-up done. Generated: {count_gen}, skipped (cached): {count_skip}. "
            f"Output → { (Path(getattr(settings, 'MEDIA_ROOT', '.'))/'quotations_pdf').resolve() }"
        ))
