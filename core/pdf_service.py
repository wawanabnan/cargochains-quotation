# core/pdf_service.py
import atexit
import os
from threading import Lock
from playwright.sync_api import sync_playwright

_playwright = None
_browser = None
_lock = Lock()

def _launch_browser(pw):
    """
    Urutan prioritas channel (Windows dev):
    1. ENV PDF_BROWSER_CHANNEL (mis: 'msedge' atau 'chrome')
    2. msedge
    3. chrome
    4. Chromium default
    """
    channel_env = os.getenv("PDF_BROWSER_CHANNEL", "").strip().lower()
    channels = [c for c in [channel_env, "msedge", "chrome", None] if c != ""]
    last_err = None
    for ch in channels:
        try:
            kwargs = dict(headless=True, args=[
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
            ])
            if ch:  # gunakan browser terinstall (lebih cepat startup di Windows)
                kwargs["channel"] = ch
            return pw.chromium.launch(**kwargs)
        except Exception as e:
            last_err = e
    # Kalau semua gagal, raise error terakhir
    raise last_err

def get_browser():
    global _playwright, _browser
    if _browser:
        return _browser
    with _lock:
        if _browser:
            return _browser
        _playwright = sync_playwright().start()
        _browser = _launch_browser(_playwright)
        return _browser

def _shutdown():
    global _playwright, _browser
    try:
        if _browser:
            _browser.close()
    finally:
        _browser = None
        if _playwright:
            _playwright.stop()
            _playwright = None

atexit.register(_shutdown)

def html_to_pdf_bytes(html: str, base_url: str) -> bytes:
    # sisipkan <base> agar static resolve
    if "<head>" in html:
        html = html.replace("<head>", f'<head><base href="{base_url}">', 1)
    else:
        html = f'<head><base href="{base_url}"></head>{html}'

    browser = get_browser()
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()

    # block request eksternal di luar base_url & static
    def _route(route, request):
        url = request.url
        if url.startswith(base_url) or "/static/" in url:
            route.continue_()
        else:
            route.abort()
    page.route("**/*", _route)

    page.set_content(html, wait_until="load")
    page.emulate_media(media="print")
    pdf_bytes = page.pdf(
        format="A4",
        print_background=True,
        prefer_css_page_size=True,
        margin={"top": "12mm", "right": "12mm", "bottom": "12mm", "left": "12mm"},
    )

    page.unroute("**/*", _route)
    context.close()
    return pdf_bytes
