from pathlib import Path

ROOT = Path(__file__).resolve().parent
TPL = ROOT / "sales" / "templates" / "sales"
dst = TPL / "quotation_detail.html"

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print("• backup ->", b)

html = r"""
{% extends "sales/base.html" %}
{% load sales_extras %}
{% block title %}Quotation {{ q.number }}{% endblock %}
{% block content %}
<div class="container-fluid cc-container my-4">

  <div class="cc-toolbar">
    <h4 class="cc-title">Quotation {{ q.number|default:"(draft)" }}</h4>
    <div class="d-flex gap-2">
      <a class="btn btn-outline-primary cc-btn" target="_blank" href="{% url 'sales:quotation_pdf' pk=q.pk kind='summary' %}">PDF Summary</a>
      <a class="btn btn-outline-primary cc-btn" target="_blank" href="{% url 'sales:quotation_pdf' pk=q.pk kind='detail' %}">PDF Detail</a>
      <a class="btn btn-outline-secondary cc-btn" href="{% url 'sales:quotation_list' %}">Back</a>
    </div>
  </div>

  <div class="cc-card mb-3">
    <div class="p-3">
      <div class="row">
        <div class="col-md-8">
          <div class="cc-muted mb-1">{{ q.date }} · {{ q.customer }} · {{ q.currency }}</div>
          <div><strong>Mode:</strong> {{ q.transport_mode }} &middot; <strong>Service:</strong> {{ q.service_option }}</div>
          <div><strong>Multi-destination:</strong> {{ q.multi_destination }}</div>
          {# TIDAK pakai tanda kurung di if #}
          {% if not q.multi_destination %}
            {% if q.origin or q.destination %}
              <div><strong>Header O/D:</strong> {{ q.origin|default:"-" }} → {{ q.destination|default:"-" }}</div>
            {% endif %}
          {% endif %}
        </div>
        {% if q.notes %}
        <div class="col-md-4">
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
    {% for c in q.cargos.all %}
      <div class="mb-4">
        <!-- Judul Cargo -->
        <div class="mb-1">
          <div class="fw-semibold">{{ c.description }}</div>
          {% if q.multi_destination %}
            <div class="cc-muted small">{{ c.origin|default:"-" }} → {{ c.destination|default:"-" }}</div>
          {% endif %}
        </div>

        <!-- Cargo Detail (tanpa charge) -->
        <div class="cc-card mb-2">
          <div class="p-3">
            <div class="table-responsive">
              <table class="table table-sm cc-table mb-0">
                <thead class="table-light">
                  <tr>
                    <th style="width:160px;">Field</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {% if c.qty %}<tr><td>Qty</td><td>{{ c.qty }}</td></tr>{% endif %}
                  {% if c.weight_kg %}<tr><td>Weight (kg)</td><td>{{ c.weight_kg }}</td></tr>{% endif %}
                  {% if c.volume_cbm %}<tr><td>Volume (cbm)</td><td>{{ c.volume_cbm }}</td></tr>{% endif %}
                  {% if not c.qty and not c.weight_kg and not c.volume_cbm %}
                    <tr><td colspan="2" class="cc-muted">No cargo metrics</td></tr>
                  {% endif %}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Line Charges (dipisah) -->
        <div class="cc-card">
          <div class="p-3">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <h6 class="mb-0">Charges</h6>
              <div class="small cc-muted">Subtotal:
                {% if cargo_totals %}{{ cargo_totals|get_item:c.id|default:'0' }}{% else %}0{% endif %}
              </div>
            </div>
            <div class="table-responsive">
              <table class="table table-sm cc-table mb-0">
                <thead class="table-light">
                  <tr>
                    <th>Description</th>
                    <th class="text-end" style="width:120px;">Qty</th>
                    <th class="text-end" style="width:140px;">Rate</th>
                    <th class="text-end" style="width:160px;">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {% for ch in c.charges.all %}
                    <tr>
                      <td>{{ ch.description }}</td>
                      <td class="text-end">{{ ch.qty }}</td>
                      <td class="text-end">{{ ch.rate }}</td>
                      <td class="text-end">{{ ch.amount }}</td>
                    </tr>
                  {% empty %}
                    <tr><td colspan="4" class="text-center cc-muted">No charges</td></tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    {% empty %}
      <div class="cc-card">
        <div class="p-3 text-center cc-muted">No cargos</div>
      </div>
    {% endfor %}

    {% if grand_total %}
      <div class="d-flex justify-content-end mt-2">
        <div class="fw-semibold">Grand Total: {{ grand_total }}</div>
      </div>
    {% endif %}
  {% endif %}
</div>
{% endblock %}
"""

if not TPL.exists():
    raise SystemExit(f"Templates folder not found: {TPL}")

# backup dan tulis
backup(dst)
dst.write_text(html.strip() + "\n", encoding="utf-8")
print("✓ Fixed:", dst)
