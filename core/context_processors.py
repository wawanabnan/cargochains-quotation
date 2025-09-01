# core/context_processors.py
from .company_settings import get_company_settings
from django.templatetags.static import static

def company(request):
    data = get_company_settings()

    raw = (data.get("COMPANY_LOGO_STATIC") or "").strip()
    # buang kutip yg tak sengaja disimpan
    raw = raw.strip().strip("'").strip('"')

    # Jika sudah URL absolut (http/https/data), pakai apa adanya.
    if raw.startswith(("http://", "https://", "data:")):
        logo_url = raw
    else:
        # anggap ini path static → bangun URL static
        logo_url = static(raw) if raw else ""

    data["COMPANY_LOGO_URL"] = logo_url
    return data
