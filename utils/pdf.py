import pdfkit
from django.conf import settings
import shutil

def _wkhtml_cmd():
    if getattr(settings, "WKHTMLTOPDF_CMD", None):
        return settings.WKHTMLTOPDF_CMD
    return shutil.which("wkhtmltopdf")

def render_pdf_from_html(html: str) -> bytes:
    cmd = _wkhtml_cmd()
    config = pdfkit.configuration(wkhtmltopdf=cmd) if cmd else None
    options = {
        "page-size": "A4",
        "margin-top": "12mm",
        "margin-right": "12mm",
        "margin-bottom": "12mm",
        "margin-left": "12mm",
        "print-media-type": None,
        "enable-local-file-access": None,
    }
    return pdfkit.from_string(html, False, options=options, configuration=config)
