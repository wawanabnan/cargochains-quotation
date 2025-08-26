# simpan sebagai check_fix_fixture.py lalu: python check_fix_fixture.py
from pathlib import Path
import json
from datetime import datetime, timezone

p = Path("partners/fixtures/partners_sample.json")
txt = p.read_text(encoding="utf-8")
# Validasi JSON
data = json.loads(txt)

# Bersihkan pk & tambahkan timestamp bila kosong
now = datetime.now(timezone.utc).isoformat()
for row in data:
    row.pop("pk", None)
    if row.get("model") != "partners.partner":
        raise SystemExit(f"Model label invalid: {row.get('model')} (harus 'partners.partner')")
    f = row.setdefault("fields", {})
    f.setdefault("name", "Unnamed")
    f.setdefault("is_customer", False)
    f.setdefault("is_vendor", False)
    f.setdefault("is_agent", False)
    f.setdefault("created_at", now)
    f.setdefault("updated_at", now)

p.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("✓ Fixture valid & dirapikan:", p)
