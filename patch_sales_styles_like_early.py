from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
TPL = APP / "templates" / "sales"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print("• backup ->", b)

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s.strip() + "\n", encoding="utf-8")
    print("• write ", p)

print("== Patch: Sales templates styling (Odoo-like, clean) ==")

# ---------- base.html ----------
base_html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{% block title %}Sales{% endblock %}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Bootstrap (minimal, hanya grid & utilities) -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">

  <style>
    :root{
      --card-radius: 14px;
      --soft-shadow: 0 6px 18px rgba(0,0,0,.06);
      --soft-border: 1px solid #e9ecef;
      --muted:#6c757d;
      --brand:#0d6efd;
    }
    body{ background:#fafafa; }
    .cc-container{ max-width: 1080px; }
    .cc-card{
      border: var(--soft-border);
      border-radius: var(--card-radius);
      box-shadow: var(--soft-shadow);
      background:#fff;
    }
    .cc-card .card-body{ padding: 20px 20px; }
    .cc-toolbar{
      display:flex; align-items:center; justify-content:space-between;
      margin-bottom: 16px;
    }
    .cc-title{ margin:0; font-weight:600; letter-spacing:.2px; }
    .cc-muted{ color: var(--muted); }

    /* Odoo-like form (borderless inputs) */
    .o-form p, .o-form .mb-3{ margin-bottom: 10px !important; }
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
    .o-field textarea{ resize: vertical; }
    .o-field label{ font-size:.86rem; color:#6c757d; margin-bottom:3px; }
    .o-field .helptext{ font-size:.8rem; color:#999; }

    /* Stepper */
    .cc-steps{
      display:flex; gap:8px; margin-bottom:14px; align-items:center; flex-wrap:wrap;
    }
    .cc-step{
      padding:6px 10px; border-radius: 999px; font-size:.85rem;
      background:#eef2ff; color:#3141b7; border:1px solid #e0e7ff;
    }
    .cc-step.active{ background:#dbeafe; color:#0b5ed7; border-color:#bfdbfe; font-weight:600; }
    .cc-step.sep{ background:transparent; border:none; color:#adb5bd; padding:0 2px; }

    /* Tables */
    .table.cc-table> :not(caption)>*>*{ padding: .5rem .6rem; }
    .cc-shadow{ box-shadow: var(--soft-shadow); }
    .cc-btn{
      border-radius: 999px;
      padding:.45rem .9rem;
    }
    .btn-outline-primary.cc-btn{ border-color:#cfe2ff; color:#0d6efd; }
    .btn-outline-primary.cc-btn:hover{ background:#e7f1ff; }
  </style>
  {% block extra_head %}{% endblock %}
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
"""

# ---------- quotation_list.html ----------
list_html = """
{% extends "sales/base.html" %}
{% block title %}Quotations{% endblock %}
{% block content %}
<div class="container cc-container my-4">
  <div class="cc-toolbar">
    <h4 class="cc-title">Quotations</h4>
    <a class="btn btn-primary cc-btn" href="{% url 'sales:quotation_wizard_v3_start' %}">+ New Quotation</a>
  </div>

  <div class="cc-card">
    <div class="card-body">
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

# ---------- quotation_wizard_v3_start.html ----------
start_html = """
{% extends "sales/base.html" %}
{% block title %}Start New Quotation{% endblock %}
{% block content %}
<div class="container cc-container my-4">
  <div class="cc-card">
    <div class="card-body">
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
          <div class="col-md-6">
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
            </div>
          </div>

          <div class="col-md-6">
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

          <div class="col-md-6">
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

          <div class="col-md-6 d-flex align-items-end">
            <div class="form-check">
              <input class="form-check-input" type="checkbox" name="multi_destination" id="multi_destination" checked>
              <label class="form-check-label" for="multi_destination">Multi Destination</label>
            </div>
          </div>
        </div>

        <div class="mt-4 d-flex justify-content-end">
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
      SEA:  ['DOOR_TO_DOOR','DOOR_TO_PORT','PORT_TO_DOOR','PORT_TO_PORT'],
      AIR:  ['DOOR_TO_AIRPORT','AIRPORT_TO_AIRPORT','AIRPORT_TO_DOOR'],
      LAND: ['TRUCKING'],
      MULTI:['MIXED']
    };
    const label = {
      DOOR_TO_DOOR:'Door to Door', DOOR_TO_PORT:'Door to Port', PORT_TO_DOOR:'Port to Door', PORT_TO_PORT:'Port to Port',
      DOOR_TO_AIRPORT:'Door to Airport', AIRPORT_TO_AIRPORT:'Airport to Airport', AIRPORT_TO_DOOR:'Airport to Door',
      TRUCKING:'Trucking', MIXED:'Multi-modal'
    };
    const arr = map[tm.value] || map.SEA;
    so.innerHTML = '';
    arr.forEach(k=>{ const o=document.createElement('option'); o.value=k; o.textContent=label[k]; so.appendChild(o);})
  }
  tm.addEventListener('change', refreshSO);
  refreshSO();
})();
</script>
{% endblock %}
"""

# ---------- quotation_wizard.html ----------
wizard_html = """
{% extends "sales/base.html" %}
{% block title %}Quotation Wizard{% endblock %}
{% block content %}
<div class="container cc-container my-4">
  <div class="cc-card">
    <div class="card-body">

      <div class="cc-steps">
        <span class="cc-step {% if step == 1 %}active{% endif %}">Header</span>
        <span class="cc-step sep">›</span>
        <span class="cc-step {% if step == 2 %}active{% endif %}">Lines</span>
      </div>

      {% if step == 1 %}
      <form method="post" class="o-form">
        {% csrf_token %}
        <h5 class="mb-3">Step 1 — Header (Freight)</h5>

        {# Render field tanpa border dengan label ringan #}
        {{ qform.non_field_errors }}
        <div class="row g-3">
          {% for field in qform.visible_fields %}
          <div class="col-md-6">
            <div class="o-field">
              <label for="{{ field.id_for_label }}">{{ field.label }}</label>
              {{ field }}
              {% if field.help_text %}<div class="helptext">{{ field.help_text }}</div>{% endif %}
              {{ field.errors }}
            </div>
          </div>
          {% endfor %}
        </div>

        <div class="alert alert-info mt-2 py-2">
          {% if show_od_in_header %}
            <small>Single-destination: Origin/Destination diisi di Header. Field O/D pada Cargo akan disembunyikan.</small>
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
            <div class="card-body">
              <div class="row g-3">
                {% for field in f.visible_fields %}
                <div class="col-md-4">
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

# ---------- quotation_detail.html (tambahan styling + tombol PDF) ----------
detail_html = """
{% extends "sales/base.html" %}
{% block title %}Quotation {{ q.number }}{% endblock %}
{% block content %}
<div class="container cc-container my-4">

  <div class="cc-toolbar">
    <h4 class="cc-title">Quotation {{ q.number|default:"(draft)" }}</h4>
    <div class="d-flex gap-2">
      <a class="btn btn-outline-primary cc-btn" target="_blank" href="{% url 'sales:quotation_pdf' pk=q.pk kind='summary' %}">PDF Summary</a>
      <a class="btn btn-outline-primary cc-btn" target="_blank" href="{% url 'sales:quotation_pdf' pk=q.pk kind='detail' %}">PDF Detail</a>
      <a class="btn btn-outline-secondary cc-btn" href="{% url 'sales:quotation_list' %}">Back</a>
    </div>
  </div>

  <div class="cc-card mb-3">
    <div class="card-body">
      <div class="row">
        <div class="col-md-7">
          <div class="cc-muted mb-1">{{ q.date }} · {{ q.customer }} · {{ q.currency }}</div>
          <div><strong>Mode:</strong> {{ q.transport_mode }} &middot; <strong>Service:</strong> {{ q.service_option }}</div>
          <div><strong>Multi-destination:</strong> {{ q.multi_destination }}</div>
          {% if q.origin or q.destination %}
          <div><strong>Header O/D:</strong> {{ q.origin|default:"-" }} → {{ q.destination|default:"-" }}</div>
          {% endif %}
        </div>
        {% if q.notes %}
        <div class="col-md-5">
          <div class="border-start ps-3">
            <div class="cc-muted small">Notes</div>
            <div>{{ q.notes }}</div>
          </div>
        </div>
        {% endif %}
      </div>
    </div>
  </div>

  {% if q.business_type == 'FREIGHT' %}
    <div class="cc-card">
      <div class="card-body">
        <h6 class="mb-2">Cargos</h6>
        <div class="table-responsive">
          <table class="table table-sm cc-table">
            <thead class="table-light">
              <tr>
                <th>Description</th><th>Origin</th><th>Destination</th>
                <th class="text-end">Qty</th><th class="text-end">Weight</th><th class="text-end">Volume</th>
              </tr>
            </thead>
            <tbody>
            {% for c in q.cargos.all %}
              <tr>
                <td>{{ c.description }}</td>
                <td>{{ c.origin }}</td>
                <td>{{ c.destination }}</td>
                <td class="text-end">{{ c.qty|default:"" }}</td>
                <td class="text-end">{{ c.weight_kg|default:"" }}</td>
                <td class="text-end">{{ c.volume_cbm|default:"" }}</td>
              </tr>
            {% empty %}
              <tr><td colspan="6" class="text-center cc-muted">No cargos</td></tr>
            {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  {% endif %}

</div>
{% endblock %}
"""

# ---------- quotation_pdf_detail.html & quotation_pdf_summary.html ----------
pdf_detail = """
<!doctype html><html><head><meta charset="utf-8"><title>{{ q.number }} - Detail</title>
<style>
  body{ font-family: Arial, sans-serif; font-size:12px; }
  h2{ margin:0 0 6px 0; }
  table{ width:100%; border-collapse:collapse; margin-top:8px; }
  th,td{ border:1px solid #ccc; padding:6px; }
  thead{ background:#f5f5f5; }
  .muted{ color:#666; }
</style></head><body>
  <h2>Quotation {{ q.number }}</h2>
  <div class="muted">{{ q.date }} · Customer: {{ q.customer }} · Currency: {{ q.currency }}</div>
  <div class="muted">Mode: {{ q.transport_mode }} · Service: {{ q.service_option }} · Multi-destination: {{ q.multi_destination }}</div>
  {% if q.origin or q.destination %}
  <div class="muted">Header O/D: {{ q.origin|default:"-" }} → {{ q.destination|default:"-" }}</div>
  {% endif %}
  {% if q.notes %}<p>{{ q.notes }}</p>{% endif %}

  <h3>Cargo & Charges (Detail)</h3>
  {% for c in q.cargos.all %}
    <h4 style="margin-top:12px">{{ c.description }} ({{ c.origin }} → {{ c.destination }})</h4>
    <table>
      <thead><tr><th>Description</th><th style="text-align:right">Qty</th><th style="text-align:right">Rate</th><th style="text-align:right">Amount</th></tr></thead>
      <tbody>
        {% for ch in c.charges.all %}
        <tr>
          <td>{{ ch.description }}</td>
          <td style="text-align:right">{{ ch.qty }}</td>
          <td style="text-align:right">{{ ch.rate }}</td>
          <td style="text-align:right">{{ ch.amount }}</td>
        </tr>
        {% empty %}<tr><td colspan="4" class="muted">No charges</td></tr>{% endfor %}
      </tbody>
    </table>
  {% endfor %}
</body></html>
"""

pdf_summary = """
<!doctype html><html><head><meta charset="utf-8"><title>{{ q.number }} - Summary</title>
<style>
  body{ font-family: Arial, sans-serif; font-size:12px; }
  h2{ margin:0 0 6px 0; }
  table{ width:100%; border-collapse:collapse; margin-top:8px; }
  th,td{ border:1px solid #ccc; padding:6px; }
  thead{ background:#f5f5f5; }
  .muted{ color:#666; }
</style></head><body>
  <h2>Quotation {{ q.number }}</h2>
  <div class="muted">{{ q.date }} · Customer: {{ q.customer }} · Currency: {{ q.currency }}</div>
  <div class="muted">Mode: {{ q.transport_mode }} · Service: {{ q.service_option }} · Multi-destination: {{ q.multi_destination }}</div>
  {% if q.origin or q.destination %}
  <div class="muted">Header O/D: {{ q.origin|default:"-" }} → {{ q.destination|default:"-" }}</div>
  {% endif %}
  {% if q.notes %}<p>{{ q.notes }}</p>{% endif %}

  <h3>Price per Cargo (Summary)</h3>
  <table>
    <thead><tr><th>Cargo</th><th>Origin</th><th>Destination</th><th style="text-align:right">Total</th></tr></thead>
    <tbody>
      {% for c, tot in cargo_totals %}
      <tr>
        <td>{{ c.description }}</td>
        <td>{{ c.origin }}</td>
        <td>{{ c.destination }}</td>
        <td style="text-align:right">{{ tot }}</td>
      </tr>
      {% empty %}<tr><td colspan="4" class="muted">No cargos</td></tr>{% endfor %}
      <tr>
        <td colspan="3" style="text-align:right"><strong>Grand Total</strong></td>
        <td style="text-align:right"><strong>{{ grand_total }}</strong></td>
      </tr>
    </tbody>
  </table>
</body></html>
"""

# ---------- tulis file ----------
TPL.mkdir(parents=True, exist_ok=True)

files = {
    TPL / "base.html": base_html,
    TPL / "quotation_list.html": list_html,
    TPL / "quotation_wizard_v3_start.html": start_html,
    TPL / "quotation_wizard.html": wizard_html,
    TPL / "quotation_detail.html": detail_html,
    TPL / "quotation_pdf_detail.html": pdf_detail,
    TPL / "quotation_pdf_summary.html": pdf_summary,
}

for p, s in files.items():
    backup(p)
    write(p, s)

print("\nDone. Refresh UI pages to see the new clean style.")
