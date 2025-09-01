# core/company_settings.py
from functools import lru_cache

# --- Auto detect model in your "settings" app (DB table) ---
# Supported guesses: settings.models.{Setting, AppSetting, SystemSetting}
SettingModel = None
try:
    from settings.models import Setting as _M
    SettingModel = _M
except Exception:
    try:
        from settings.models import AppSetting as _M
        SettingModel = _M
    except Exception:
        try:
            from settings.models import SystemSetting as _M
            SettingModel = _M
        except Exception:
            SettingModel = None

try:
    from django.conf import settings as dj_settings
except Exception:
    dj_settings = None

DEFAULTS = {
    "COMPANY_NAME": "Perusahaan Anda",
    "COMPANY_TAGLINE": "",
    "COMPANY_LOGO_STATIC": "img/company_logo.png",
    
}

def _read_db():
    data = {}
    if not SettingModel:
        return data
    # deteksi kolom umum: (key,value) atau (name,value)
    candidates = [("key","value"), ("name","value")]
    found = None
    # ambil satu row untuk introspeksi kolom jika perlu
    try:
        obj = SettingModel.objects.first()
        fields = {f.name for f in SettingModel._meta.get_fields()} if SettingModel else set()
    except Exception:
        fields = set()
    for k,v in candidates:
        if k in fields and v in fields:
            found = (k,v); break
    # fallback paksa ke ("key","value")
    if not found:
        found = ("key","value")
    K, V = found
    try:
        qs = SettingModel.objects.all()
        for s in qs:
            key = getattr(s, K, None)
            val = getattr(s, V, None)
            if key:
                data[str(key)] = val
    except Exception:
        pass
    return data

@lru_cache(maxsize=1)
def _snapshot():
    data = DEFAULTS.copy()
    # baca DB
    db = _read_db()
    for k, v in db.items():
        if k in data and (v is not None and v != ""):
            data[k] = v
    # fallback settings.py
    if dj_settings:
        if getattr(dj_settings, "COMPANY_NAME", None):
            data["COMPANY_NAME"] = dj_settings.COMPANY_NAME
        if getattr(dj_settings, "COMPANY_TAGLINE", None) is not None:
            data["COMPANY_TAGLINE"] = dj_settings.COMPANY_TAGLINE
        if getattr(dj_settings, "COMPANY_LOGO_STATIC", None):
            data["COMPANY_LOGO_STATIC"] = dj_settings.COMPANY_LOGO_STATIC
    return data

def get_company_settings():
    """Return dict: COMPANY_NAME, COMPANY_TAGLINE, COMPANY_LOGO_STATIC (from DB settings, with fallback)."""
    return _snapshot()

def invalidate_company_settings_cache():
    _snapshot.cache_clear()
