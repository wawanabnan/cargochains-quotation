# patch_use_db_settings.py
from pathlib import Path
import re, sys, shutil, datetime

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(fp: Path):
    if not fp.exists(): return
    bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
    shutil.copy2(fp, bak)
    print(f"[backup] {fp} -> {bak.name}")

def find_settings_py():
    # cari settings.py yg relevan (hindari venv)
    cands = []
    for p in ROOT.rglob("settings.py"):
        p_str = str(p).lower()
        if "\\venv\\" in p_str or "/venv/" in p_str: 
            continue
        if "\\site-packages\\" in p_str or "/site-packages/" in p_str:
            continue
        # prefer yang 1 level dari manage.py (umum)
        if p.parent.parent == ROOT:
            cands.insert(0, p)
        else:
            cands.append(p)
    if not cands:
        print("[ERR] settings.py not found. Set SETTINGS_PATH manually.")
        sys.exit(1)
    print("[info] using settings.py:", cands[0])
    return cands[0]

def ensure_package_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    initf = d / "__init__.py"
    if not initf.exists():
        initf.write_text("", encoding="utf-8")

COMPANY_SETTINGS_PY = '''# core/company_settings.py
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
'''

CONTEXT_PROCESSOR_PY = '''# core/context_processors.py
from .company_settings import get_company_settings

def company(request):
    # inject ke semua template:
    # COMPANY_NAME, COMPANY_TAGLINE, COMPANY_LOGO_STATIC
    return get_company_settings()
'''

def patch_settings_py(settings_py: Path):
    backup(settings_py)
    src = settings_py.read_text(encoding="utf-8")

    # pastikan 'core.context_processors.company' ada di TEMPLATES[0]['OPTIONS']['context_processors']
    if "core.context_processors.company" in src:
        print("[skip] context processor already present in settings.py")
        return

    # cari blok context_processors
    pat = re.compile(
        r"(TEMPLATES\s*=\s*\[\s*\{\s*.*?['\"]OPTIONS['\"]\s*:\s*\{\s*['\"]context_processors['\"]\s*:\s*\[)(.*?)(\])",
        re.S
    )
    m = pat.search(src)
    if not m:
        print("[ERR] Could not locate TEMPLATES -> OPTIONS -> context_processors in", settings_py)
        print("      Please add 'core.context_processors.company' manually.")
        return

    head, mid, tail_br = m.group(1), m.group(2), m.group(3)
    # sisipkan dengan indentasi konsisten
    # cari indent dari baris terakhir di mid
    indent = "                "
    insertion = f"{indent}'core.context_processors.company',\n"
    if "core.context_processors.company" in mid:
        print("[skip] context processor already present")
        return

    new_mid = mid.rstrip() + "\n" + insertion
    new_src = src[:m.start()] + head + new_mid + tail_br + src[m.end():]
    settings_py.write_text(new_src, encoding="utf-8")
    print("[ok] added core.context_processors.company to settings.py")

def patch_views_py():
    # rapikan sales/views.py agar tidak lagi mengirim 'settings' manual, dan pastikan request=request digunakan
    views = ROOT / "sales" / "views.py"
    if not views.exists():
        print("[warn] sales/views.py not found, skip view patch.")
        return
    backup(views)
    src = views.read_text(encoding="utf-8")

    # pastikan render_to_string/Template.render dipanggil dg request=request
    # kasus 1: render_to_string("tpl", ctx) -> tambahkan request=request bila belum ada
    src = re.sub(
        r'render_to_string\(\s*("|\')([^"\']+)("|\')\s*,\s*([^)]+?)\)',
        r'render_to_string(\1\2\3, \4, request=request)',
        src
    )

    # kasus 2: tpl.render(ctx) -> gantikan jadi tpl.render(ctx, request=request)
    src = re.sub(
        r'(\.render\()\s*([^\),]+)\s*\)',
        r'\1\2, request=request)',
        src
    )

    # hilangkan pengiriman "settings": settings di context PDF bila ada (tidak perlu lagi)
    src = re.sub(r'("|\')settings("|\')\s*:\s*settings\s*,?', "", src)

    # rapikan koma ganda
    src = re.sub(r",\s*,", ", ", src)
    src = re.sub(r"\n{3,}", "\n\n", src)

    views.write_text(src, encoding="utf-8")
    print("[ok] patched sales/views.py (use request=request; drop manual settings)")

def main():
    # 1) core package + files
    core_dir = ROOT / "core"
    ensure_package_dir(core_dir)
    (core_dir / "company_settings.py").write_text(COMPANY_SETTINGS_PY, encoding="utf-8")
    print("[ok] wrote core/company_settings.py")
    (core_dir / "context_processors.py").write_text(CONTEXT_PROCESSOR_PY, encoding="utf-8")
    print("[ok] wrote core/context_processors.py")

    # 2) settings.py
    settings_py = find_settings_py()
    patch_settings_py(settings_py)

    # 3) views.py (rapikan render template)
    patch_views_py()

    print("\n✅ Selesai.")
    print("• Pastikan di DB settings terdapat kunci: COMPANY_NAME, COMPANY_TAGLINE, COMPANY_LOGO_STATIC.")
    print("• Template gunakan variabel: {{ COMPANY_NAME }}, {{ COMPANY_TAGLINE }}, {% load static %}<img src=\"{% static COMPANY_LOGO_STATIC %}\">")
    print("• Jika Anda update nilai di DB saat runtime, panggil:")
    print("    from core.company_settings import invalidate_company_settings_cache; invalidate_company_settings_cache()")
    print("  (Bisa ditrigger di signal post_save model Setting).")

if __name__ == "__main__":
    main()
