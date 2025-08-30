from pathlib import Path
import re, textwrap

ROOT = Path(__file__).resolve().parent
vp = ROOT / "sales" / "views.py"

src = vp.read_text(encoding="utf-8")

# Ganti seluruh blok SERVICE_OPTIONS_BY_MODE + freight_service_options() dengan versi bersih (4 spasi)
PAT = re.compile(
    r"SERVICE_OPTIONS_BY_MODE\s*=\s*\{[\s\S]*?\}\s*"
    r"@require_GET\s*def\s+freight_service_options\([\s\S]*?\)\s*:\s*[\s\S]*?return\s+JsonResponse\([^\)]*\)\s*",
    re.M
)

REPL = textwrap.dedent("""
    SERVICE_OPTIONS_BY_MODE = {
        "SEA": [("DOOR_TO_DOOR","Door to Door"), ("DOOR_TO_PORT","Door to Port"), ("PORT_TO_PORT","Port to Port")],
        "AIR": [("DOOR_TO_AIRPORT","Door to Airport"), ("AIRPORT_TO_AIRPORT","Airport to Airport")],
        "LAND": [("TRUCKING","Trucking")],
    }

    @require_GET
    def freight_service_options(request):
        mode = (request.GET.get("mode") or "").upper()
        options = [{"value": v, "label": l} for v, l in SERVICE_OPTIONS_BY_MODE.get(mode, [])]
        return JsonResponse({"mode": mode, "options": options})
""").lstrip("\n")

# Jika pola tidak ketemu (mis. karena salah indent), kita suntikkan blok baru tepat setelah import2 teratas
if not PAT.search(src):
    # cari baris import JsonResponse sebagai jangkar
    anchor = re.search(r"from\s+django\.http\s+import\s+JsonResponse\s*\n", src)
    if anchor:
        pos = anchor.end()
        new_src = src[:pos] + "\n" + REPL + "\n" + src[pos:]
    else:
        # fallback: letakkan di paling atas file
        new_src = REPL + "\n" + src
else:
    new_src = PAT.sub(REPL, src)

# Normalisasi: ubah TAB jadi 4 spasi (mencegah IndentationError)
new_src = new_src.replace("\t", "    ")

vp.write_text(new_src, encoding="utf-8")
print("[ok] views.py service-options block fixed.")
