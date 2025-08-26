from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parent
fx_dir = ROOT / "partners" / "fixtures"
fx_dir.mkdir(parents=True, exist_ok=True)
fx = fx_dir / "partners_sample.json"

# backup
if fx.exists():
    b = fx.with_suffix(".json.bak")
    b.write_text(fx.read_text(encoding="utf-8"), encoding="utf-8")
    print("• backup ->", b)

now = datetime.now(timezone.utc).isoformat()

data = [
  {"model":"partners.partner","fields":{"name":"PT. ABC Mining","is_customer":True,"is_vendor":False,"is_agent":False,"created_at":now,"updated_at":now}},
  {"model":"partners.partner","fields":{"name":"PT. Nusantara Logistik","is_customer":True,"is_vendor":True,"is_agent":False,"created_at":now,"updated_at":now}},
  {"model":"partners.partner","fields":{"name":"PT. Samudera Raya","is_customer":True,"is_vendor":False,"is_agent":True,"created_at":now,"updated_at":now}},
  {"model":"partners.partner","fields":{"name":"CV. Berkah Jaya","is_customer":True,"is_vendor":False,"is_agent":False,"created_at":now,"updated_at":now}},
  {"model":"partners.partner","fields":{"name":"PT. Lintas Benua","is_customer":True,"is_vendor":True,"is_agent":True,"created_at":now,"updated_at":now}}
]

fx.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("✓ wrote", fx)

# sanity check (parse kembali)
json.loads(fx.read_text(encoding="utf-8"))
print("✓ JSON valid")
