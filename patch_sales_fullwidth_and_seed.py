from pathlib import Path
import re
import json
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parent
SALES = ROOT / "sales"
TPL = SALES / "templates" / "sales"
PARTNERS = ROOT / "partners"

def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")
    print("• write", path)

def patch_views():
    vp = SALES / "views.py"
    assert vp.exists(), f"{vp} not found"
    src = vp.read_text(encoding="utf-8")
    orig = src

    # rename template calls:
    # v3 start
    src = re.sub(
        r'render\(request,\s*"sales/quotation_wizard_v3_start\.html"',
        'render(request, "sales/quotation_freight_start.html"',
        src,
        flags=re.M,
    )
    # freight wizard step templates
    src = re.sub(
        r'render\(request,\s*"sales/quotation_wizard\.html"',
        'render(request, "sales/quotation_freight.html"',
        src,
        flags=re.M,
    )

    if src != orig:
        vp.write_text(src, encoding="utf-8")
        print("✓ views.py updated to use new template names")
    else:
        print("• views.py already uses new template names (or no changes needed)")

def write_templates():
    # base.html (full width, flat)
    base_html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{% block title %}Sales{% endblock %}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    :root{
      --muted:#6c757d;
      --brand:#0d6efd;
      --soft-border:#e9ecef;
    }
    body{ background:#fff; }
    .cc-container{ max-width: 100% !important; width: 100% !important; }
    .cc-card{
      border: 1px solid var(--soft-border);
      border-radius: 0 !important;      /* flat */
      box-shadow: none !important;      /* flat */
      background:#fff;
    }
    .cc-toolbar{
      display:flex; align-items:center; justify-content:space-between;
      margin: 18px 0;
    }
    .cc-title{ margin:0; font-weight:600; letter-spacing:.2px; }
    .cc-muted{ color: var(--muted); }
    /* Borderless inputs (odoo-like) */
    .o-form .o-field{ margin-bottom: 10px; }
    .o-field input[type="text"],
    .o-field input[type="number"],
    .o-field input[type="date"],
    .o-field select,
    .o-field textarea{
      display:block; width:100%;
      border: none !important;
      border-bottom: 1px dashed #dee2e6 !important;
      padding: 6px 2px;
      background: transparent;
      border-radius: 0;
      outline: none;
    }
    .o-field label{ font-size:.86rem; color:#6c757d; margin-bottom:3px; }
    /* Stepper */
    .cc-steps{ display:flex; gap:8px; margin-bottom:14px; align-items:center; flex-wrap:wrap; }
    .cc-step{ padding:6px 10px; font-size:.85rem; background:#e9ecef; color:#495057; border:1px solid #dee2e6; border-radius:0; }
    .cc-step.active{ background:#dee2e6; color:#212529; font-weight:600; }
    .cc-step.sep{ background:transparent; border:none; color:#adb5bd; padding:0 2px; }
    /* table */
    .table.cc-table> :not(caption)>*>*{ padding:.5rem .6rem; }
    .cc-btn{ border-radius:0; padding:.45rem .9rem; }
  </style>
  {% block extra_head %}{% endblock %}
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
"""
    w(TPL / "base.html", base_html)

    # quotation_list (full width)
    list_html = """
{% extends "sales/base.html" %}
{% block title %}Quotations{% endblock %}
{% block content %}
<div class="container-fluid cc-container">
  <div class="cc-toolbar">
    <h4 class="cc-title">Quotations</h4>
    <a class="btn btn-primary cc-btn" href="{% url 'sales:quotation_wizard_v3_start' %}">+ New Quotation</a>
  </div>
  <div class="cc-card">
    <div class="p-3">
      <div class="table-responsive">
        <table class="table table-sm cc-table align-middle">
          <thead class="table-light">
            <tr>
              <th style="width:140px;">Number</th>
              <th style="width:120px;">Date</th>
              <th>Customer</th>
              <th style="width:140px;">Type</th>
              <th style="width:120px;"></th>
            </tr>
          </thead>
          <tbody>
          {% for q in page_obj.object_list %}
            <tr>
              <td class="text-nowrap">{{ q.number|default:"-" }}</td>
              <td class="text-nowrap">{{ q.date }}</td>
              <td>{{ q.customer }}</td>
              <td>{{ q.get_business_type_display }}</td>
              <td class="text-end">
                <a class="btn btn-outline-primary btn-sm cc-btn" href="{% url 'sales:quotation_detail' pk=q.pk %}">View</a>
              </td>
            </tr>
          {% empty %}
            <tr><td colspan="5" class="text-center cc-muted">No quotations</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
      <div class="d-flex justify-content-end">
        <nav>
          <ul class="pagination pagination-sm mb-0">
            {% if page_obj.has_previous %}
              <li class="page-item"><a class="page-link" href="?page={{ page_obj.previous_page_number }}">«</a></li>
            {% else %}
              <li class="page-item disabled"><span class="page-link">«</span></li>
            {% endif %}
            <li class="page-item disabled"><span class="page-link">Page {{ page_obj.number }} / {{ page_obj.paginator.num_pages }}</span></li>
            {% if page_obj.has_next %}
              <li class="page-item"><a class="page-link" href="?page={{ page_obj.next_page_number }}">»</a></li>
            {% else %}
              <li class="page-item disabled"><span class="page-link">»</span></li>
            {% endif %}
          </ul>
        </nav>
      </div>
    </div>
  </div>
</div>
{% endblock %}
"""
    w(TPL / "quotation_list.html", list_html)

    # NEW: quotation_freight_start.html (rename of v3_start)
    start_html = """
{% extends "sales/base.html" %}
{% block title %}Start New Quotation{% endblock %}
{% block content %}
<div class="container-fluid cc-container">
  <div class="cc-card">
    <div class="p-3">
      <div class="cc-steps">
        <span class="cc-step active">Start</span>
        <span class="cc-step sep">›</span>
        <span class="cc-step">Header</span>
        <span class="cc-step sep">›</span>
        <span class="cc-step">Lines</span>
      </div>
      <h5 class="mb-3">Start New Quotation</h5>
      <form method="post" class="o-form">{% csrf_token %}
        <div class="row g-3">
          <div class="col-md-4">
            <div class="o-field">
              <label>Business Type</label>
              <div class="d-flex gap-4">
                <label class="form-check">
                  <input class="form-check-input" type="radio" name="business_type" value="FREIGHT" checked>
                  <span class="form-check-label">Freight</span>
                </label>
                <label class="form-check">
                  <input class="form-check-input" type="radio" name="business_type" value="SHIP_CHARTER">
                  <span class="form-check-label">Ship Charter</span>
                </label>
              </div>
              <div class="text-muted small mt-1">Saat ini wizard fokus Freight.</div>
            </div>
          </div>
          <div class="col-md-4">
            <div class="o-field">
              <label>Transportation Mode</label>
              <select class="form-select" name="transport_mode" id="transport_mode">
                <option value="LAND">Land</option>
                <option value="SEA" selected>Sea</option>
                <option value="AIR">Air</option>
                <option value="MULTI">Multi</option>
              </select>
            </div>
          </div>
          <div class="col-md-4">
            <div class="o-field">
              <label>Service Option</label>
              <select class="form-select" name="service_option" id="service_option">
                <option value="DOOR_TO_DOOR">Door to Door</option>
                <option value="DOOR_TO_PORT">Door to Port</option>
                <option value="PORT_TO_DOOR">Port to Door</option>
                <option value="PORT_TO_PORT" selected>Port to Port</option>
                <option value="DOOR_TO_AIRPORT">Door to Airport</option>
                <option value="AIRPORT_TO_AIRPORT">Airport to Airport</option>
                <option value="AIRPORT_TO_DOOR">Airport to Door</option>
                <option value="TRUCKING">Trucking</option>
                <option value="MIXED">Multi-modal</option>
              </select>
              <div class="helptext">Opsi layanan disarankan berdasarkan mode.</div>
            </div>
          </div>
          <div class="col-12">
            <div class="form-check">
              <input class="form-check-input" type="checkbox" name="multi_destination" id="multi_destination" checked>
              <label class="form-check-label" for="multi_destination">Multi Destination</label>
            </div>
          </div>
        </div>
        <div class="mt-3 d-flex justify-content-end">
          <button class="btn btn-primary cc-btn">Start</button>
        </div>
      </form>
    </div>
  </div>
</div>
<script>
(function(){
  const tm = document.getElementById('transport_mode');
  const so = document.getElementById('service_option');
  function refreshSO(){
    const map = {
      SEA:['DOOR_TO_DOOR','DOOR_TO_PORT','PORT_TO_DOOR','PORT_TO_PORT'],
      AIR:['DOOR_TO_AIRPORT','AIRPORT_TO_AIRPORT','AIRPORT_TO_DOOR'],
      LAND:['TRUCKING'],
      MULTI:['MIXED']
    };
    const label = {
      DOOR_TO_DOOR:'Door to Door', DOOR_TO_PORT:'Door to Port', PORT_TO_DOOR:'Port to Door', PORT_TO_PORT:'Port to Port',
      DOOR_TO_AIRPORT:'Door to Airport', AIRPORT_TO_AIRPORT:'Airport to Airport', AIRPORT_TO_DOOR:'Airport to Door',
      TRUCKING:'Trucking', MIXED:'Multi-modal'
    };
    const arr = map[tm.value] || map.SEA;
    so.innerHTML = '';
    arr.forEach(k=>{ const o=document.createElement('option'); o.value=k; o.textContent=label[k]; so.appendChild(o); });
  }
  tm.addEventListener('change', refreshSO); refreshSO();
})();
</script>
{% endblock %}
"""
    w(TPL / "quotation_freight_start.html", start_html)

    # NEW: quotation_freight.html (rename of wizard)
    wizard_html = """
{% extends "sales/base.html" %}
{% block title %}Quotation Wizard{% endblock %}
{% block content %}
<div class="container-fluid cc-container">
  <div class="cc-card">
    <div class="p-3">

      <div class="cc-steps">
        <span class="cc-step {% if step == 1 %}active{% endif %}">Header</span>
        <span class="cc-step sep">›</span>
        <span class="cc-step {% if step == 2 %}active{% endif %}">Lines</span>
      </div>

      {% if step == 1 %}
      <form method="post" class="o-form">
        {% csrf_token %}
        <h5 class="mb-3">Step 1 — Header (Freight)</h5>

        {{ qform.non_field_errors }}
        <div class="row g-3">
          {% for field in qform.visible_fields %}
          <div class="col-md-4">
            <div class="o-field">
              <label for="{{ field.id_for_label }}">{{ field.label }}</label>
              {{ field }}
              {% if field.help_text %}<div class="helptext">{{ field.help_text }}</div>{% endif %}
              {{ field.errors }}
            </div>
          </div>
          {% endfor %}
        </div>

        <div class="alert alert-info mt-2 py-2" style="border-radius:0;">
          {% if show_od_in_header %}
            <small>Single-destination: Origin/Destination diisi di Header. Field O/D pada Cargo disembunyikan.</small>
          {% else %}
            <small>Multi-destination: Origin/Destination diisi per Cargo. Field O/D Header disembunyikan.</small>
          {% endif %}
        </div>

        <div class="text-end mt-3">
          <button class="btn btn-primary cc-btn">Next</button>
        </div>
      </form>

      <script>
      (function(){
        var showOD = {{ show_od_in_header|yesno:"true,false" }};
        if(!showOD){
          var ids=["id_origin","id_destination"];
          ids.forEach(function(id){
            var el=document.getElementById(id);
            if(el){ var grp=el.closest(".o-field"); if(grp) grp.style.display="none"; }
          });
        }
      })();
      </script>

      {% elif step == 2 %}
      <form method="post" class="o-form">
        {% csrf_token %}
        <h5 class="mb-3">Step 2 — Cargo Lines</h5>
        {{ fs.management_form }}
        {% for f in fs %}
          <div class="cc-card mb-2">
            <div class="p-3">
              <div class="row g-3">
                {% for field in f.visible_fields %}
                <div class="col-md-3">
                  <div class="o-field">
                    <label for="{{ field.id_for_label }}">{{ field.label }}</label>
                    {{ field }}
                    {{ field.errors }}
                  </div>
                </div>
                {% endfor %}
              </div>
              <div class="form-check mt-2">
                {{ f.DELETE }} <label class="form-check-label">Delete</label>
              </div>
            </div>
          </div>
        {% endfor %}
        <div class="d-flex justify-content-between mt-2">
          <button name="_action" value="back" class="btn btn-outline-secondary cc-btn">Back</button>
          <button class="btn btn-primary cc-btn">Save</button>
        </div>
      </form>
      <script>
      (function(){
        var hideInCargo = {{ show_od_in_header|yesno:"true,false" }};
        if(hideInCargo){
          document.querySelectorAll("input[id$='-origin'], input[id$='-destination']").forEach(function(el){
            var grp=el.closest(".o-field"); if(grp){grp.style.display="none";}
          });
        }
      })();
      </script>
      {% endif %}

    </div>
  </div>
</div>
{% endblock %}
"""
    w(TPL / "quotation_freight.html", wizard_html)

def write_fixtures_and_seed():
    # partners fixture
    fx_dir = PARTNERS / "fixtures"
    fx_dir.mkdir(parents=True, exist_ok=True)
    partners = [
        {"model":"partners.partner","pk":1001,"fields":{"name":"PT. ABC Mining","is_customer":True,"is_vendor":False,"is_agent":False}},
        {"model":"partners.partner","pk":1002,"fields":{"name":"PT. Nusantara Logistik","is_customer":True,"is_vendor":True,"is_agent":False}},
        {"model":"partners.partner","pk":1003,"fields":{"name":"PT. Samudera Raya","is_customer":True,"is_vendor":False,"is_agent":True}},
        {"model":"partners.partner","pk":1004,"fields":{"name":"CV. Berkah Jaya","is_customer":True,"is_vendor":False,"is_agent":False}},
        {"model":"partners.partner","pk":1005,"fields":{"name":"PT. Lintas Benua","is_customer":True,"is_vendor":True,"is_agent":True}},
    ]
    w(fx_dir / "partners_sample.json", json.dumps(partners, indent=2))

    # quotation seeder
    seed_py = """
from datetime import date, timedelta
from decimal import Decimal
from sales.models import Quotation, Cargo, CargoCharge
from partners.models import Partner

def get_customer(name):
    return Partner.objects.filter(name=name, is_customer=True).first()

def make_single(customer_name, origin, dest, cargos):
    c = get_customer(customer_name)
    q = Quotation.objects.create(
        customer=c, currency="IDR", business_type="FREIGHT",
        transport_mode="SEA", service_option="PORT_TO_PORT",
        multi_destination=False, origin=origin, destination=dest,
        date=date.today(), validity_date=date.today()+timedelta(days=14),
        notes=f"Single-destination test for {customer_name}"
    )
    for desc, qty in cargos:
        cg = Cargo.objects.create(quotation=q, description=desc, qty=qty, origin=origin, destination=dest)
        CargoCharge.objects.create(cargo=cg, description="Ocean Freight", qty=qty, rate=Decimal("250000"))
        CargoCharge.objects.create(cargo=cg, description="THC", qty=1, rate=Decimal("150000"))
    return q

def make_multi(customer_name, cargos):
    c = get_customer(customer_name)
    q = Quotation.objects.create(
        customer=c, currency="IDR", business_type="FREIGHT",
        transport_mode="SEA", service_option="DOOR_TO_PORT",
        multi_destination=True, origin="", destination="",
        date=date.today(), validity_date=date.today()+timedelta(days=21),
        notes=f"Multi-destination test for {customer_name}"
    )
    for desc, origin, dest, qty in cargos:
        cg = Cargo.objects.create(quotation=q, description=desc, qty=qty, origin=origin, destination=dest)
        CargoCharge.objects.create(cargo=cg, description="Pickup Trucking", qty=1, rate=Decimal("500000"))
        CargoCharge.objects.create(cargo=cg, description="Ocean Freight", qty=qty, rate=Decimal("275000"))
    return q

def run():
    if not Partner.objects.filter(is_customer=True).exists():
        print("! No customers, please load partners fixtures first: python manage.py loaddata partners_sample.json")
        return

    Qs = []
    Qs.append(make_single("PT. ABC Mining", "Jakarta", "Surabaya", [("Steel Coil", 10), ("Machinery", 2)]))
    Qs.append(make_single("PT. Nusantara Logistik", "Semarang", "Makassar", [("Textile Rolls", 30)]))
    Qs.append(make_multi("PT. Samudera Raya", [("Fertilizer", "Jakarta", "Medan", 20), ("Fertilizer", "Jakarta", "Balikpapan", 15)]))
    Qs.append(make_multi("CV. Berkah Jaya", [("Electronics", "Bandung", "Batam", 5), ("Electronics", "Bandung", "Banjarmasin", 3)]))
    Qs.append(make_single("PT. Lintas Benua", "Surabaya", "Belawan", [("Paper Reels", 12)]))

    print(f"✓ Seeded {len(Qs)} quotations. IDs: {[q.id for q in Qs]}")
"""
    w(ROOT / "seed_sample_quotations.py", seed_py)

def main():
    patch_views()
    write_templates()
    write_fixtures_and_seed()
    print("\n=== NEXT ===")
    print("1) Load sample partners:")
    print("   python manage.py loaddata partners_sample.json")
    print("2) Seed sample quotations:")
    print("   python manage.py shell -c \"import seed_sample_quotations as s; s.run()\"")
    print("3) Jalankan server dan cek:")
    print("   /sales/quotations/  (full width, flat)")
    print("   /sales/quotations/wizard/v3/start/  (pakai template: quotation_freight_start.html)")
    print("   Wizard Freight step 1/2 pakai: quotation_freight.html")

if __name__ == "__main__":
    main()
