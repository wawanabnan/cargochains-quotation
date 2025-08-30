import re
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
views_file = ROOT / "sales" / "views.py"

backup = views_file.with_suffix(".bak")
shutil.copy2(views_file, backup)
print(f"[backup] {views_file} -> {backup}")

text = views_file.read_text(encoding="utf-8")

# ---- Tambahkan import datetime & helpers
if "def _header_to_session" not in text:
    inject = """
from datetime import date

def _header_to_session(cleaned):
    return {
        "date": cleaned.get("date").isoformat() if cleaned.get("date") else None,
        "validity_date": cleaned.get("validity_date").isoformat() if cleaned.get("validity_date") else None,
        "customer_id": cleaned.get("customer").pk if cleaned.get("customer") else None,
        "currency": cleaned.get("currency"),
        "notes": cleaned.get("notes"),
        "origin": cleaned.get("origin"),
        "destination": cleaned.get("destination"),
    }

def _header_from_session(sess):
    if not sess:
        return {}
    data = {
        "date": date.fromisoformat(sess["date"]) if sess.get("date") else None,
        "validity_date": date.fromisoformat(sess["validity_date"]) if sess.get("validity_date") else None,
        "customer": sess.get("customer_id"),
        "currency": sess.get("currency"),
        "notes": sess.get("notes"),
        "origin": sess.get("origin"),
        "destination": sess.get("destination"),
    }
    return data
"""
    # taruh setelah import paling bawah
    text = re.sub(r'(WKEY\s*=\s*["\']freight_wizard["\'])',
                  r'\1\n' + inject, text)

# ---- Patch step=header POST (gunakan _header_to_session)
text = re.sub(
    r'wiz\["header"\]\s*=\s*form\.cleaned_data',
    'wiz["header"] = _header_to_session(form.cleaned_data)',
    text
)
# ---- Patch step=header GET (initial)
text = re.sub(
    r'initial=wiz\.get\("header"\)',
    'initial=_header_from_session(wiz.get("header"))',
    text
)
# ---- Patch step=lines awal header
text = re.sub(
    r'header\s*=\s*wiz\["header"\]',
    'header = _header_from_session(wiz["header"])',
    text
)

# ---- Patch Quotation create: set customer
pattern_q = r'(q\s*=\s*Quotation\([^)]+\)\s*)'
replacement_q = r"\1\n                q.customer_id = header.get('customer')"
text = re.sub(pattern_q, replacement_q, text)

views_file.write_text(text, encoding="utf-8")
print(f"[patched] {views_file}")
