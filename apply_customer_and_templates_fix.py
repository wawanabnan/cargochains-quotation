from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
APP  = ROOT / "sales"
TPL  = ROOT / "templates" / "sales" / "freight"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak}")

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    print(f"[write]  {p}")

# 1) forms.py — customer queryset = semua CustomerProxy (tanpa filter "admin")
def patch_forms():
    p = APP / "forms.py"
    txt = p.read_text(encoding="utf-8")
    backup(p)

    # pastikan import CustomerProxy
    if "from partners.models import CustomerProxy" not in txt:
        txt = re.sub(
            r"(from \.models import .*FreightCharge.*\n)",
            r"\\1from partners.models import CustomerProxy\n",
            txt
        )

    # ganti __init__ FreightHeaderForm: set queryset = CustomerProxy.objects.all()
    pattern = re.compile(r"class\s+FreightHeaderForm\(forms\.ModelForm\):(.*?)(\nclass\s|\Z)", re.S)
    m = pattern.search(txt)
    if m:
        block = m.group(0)
        if "def __init__(" not in block:
            block_new = block.rstrip() + """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # dropdown customer berisi semua customer
        try:
            self.fields["customer"].queryset = CustomerProxy.objects.all()
        except Exception:
            pass
"""
            txt = txt.replace(block, block_new)
        else:
            # sudah ada __init__: set (atau overwrite) queryset barisnya
            block_new = re.sub(
                r"self\.fields\[\s*[\"']customer[\"']\s*\]\.queryset\s*=.*",
                "self.fields[\"customer\"].queryset = CustomerProxy.objects.all()",
                block
            )
            if block_new == block:
                # belum ada baris queryset → sisipkan setelah super().__init__
                block_new = block.replace(
                    "def __init__(self, *args, **kwargs):",
                    "def __init__(self, *args, **kwargs):\n        super().__init__(*args, **kwargs)\n        self.fields[\"customer\"].queryset = CustomerProxy.objects.all()\n        #"
                )
            txt = txt.replace(block, block_new)

    # pastikan field currency & payment_term ada di Meta.fields (bukan terhapus)
    txt = re.sub(
        r"class\s+FreightHeaderForm\(forms\.ModelForm\):(.*?)class\s+Meta:\s*?\n\s*model\s*=\s*FreightQuotation\s*?\n\s*fields\s*=\s*\[([^\]]*)\]",
        lambda m: m.group(0) if ("currency" in m.group(2) and "payment_term" in m.group(2))
        else m.group(0).replace(m.group(2), '"date","customer","currency","payment_term","notes"'),
        txt, flags=re.S
    )

    p.write_text(txt, encoding="utf-8")
    print(f"[patched] {p}")

# 2) views.py — pakai template freight/new.html (bukan quotation_form.html)
def patch_views():
    p = APP / "views.py"
    txt = p.read_text(encoding="utf-8")
    backup(p)
    txt = txt.replace('render(request, "sales/freight/quotation_form.html"', 'render(request, "sales/freight/new.html"')
    p.write_text(txt, encoding="utf-8")
    print(f"[patched] {p}")

# 3) templates/sales/freight/new.html — wizard 2 langkah
def write_template_new():
    content = """
    {% extends "base.html" %}
    {% block title %}New Freight Quotation{% endblock %}

    {% block content %}
    <div class="card shadow-sm border-0">
      <div class="card-header py-2">
        <ol class="breadcrumb mb-0">
          <li class="breadcrumb-item {% if step == 'header' %}active{% endif %}">Header Information</li>
          <li class="breadcrumb-item {% if step == 'lines' %}active{% endif %}">Cargo & Charges</li>
        </ol>
      </div>

      <div class="card-body">
        {% if step == 'header' %}
          <form method="post">{% csrf_token %}
            {% if form_header.non_field_errors %}
              <div class="alert alert-danger py-2 mb-3">{{ form_header.non_field_errors }}</div>
            {% endif %}
            <div class="row g-3">
              <div class="col-12 col-md-4">
                <label class="form-label">Date</label>{{ form_header.date }}
              </div>
              <div class="col-12 col-md-4">
                <label class="form-label">Customer</label>{{ form_header.customer }}
              </div>
              <div class="col-12 col-md-4">
                <label class="form-label">Currency</label>{{ form_header.currency }}
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label">Payment Term</label>{{ form_header.payment_term }}
              </div>
              <div class="col-12">
                <label class="form-label">Notes</label>{{ form_header.notes }}
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label">Moda Transportasi</label>{{ form_header.transport_mode }}
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label">Service Option</label>{{ form_header.service_option }}
              </div>
            </div>

            <div class="d-flex justify-content-between mt-3">
              <a href="{% url 'sales:freight_list' %}" class="btn btn-outline-secondary rounded-0">Cancel</a>
              <button class="btn btn-primary rounded-0" type="submit">Next</button>
            </div>
          </form>

        {% elif step == 'lines' %}
          <form method="post">{% csrf_token %}
            {{ cargo_fs.management_form }}
            <h6>Cargo Detail</h6>
            <div class="table-responsive mb-3">
              <table class="table table-sm align-middle">
                <thead class="table-light">
                  <tr>
                    <th>Description</th><th class="text-end" style="width:100px;">Qty</th>
                    <th class="text-end" style="width:120px;">Weight</th>
                    <th class="text-end" style="width:120px;">Volume</th>
                    <th class="text-end" style="width:140px;">Amount</th>
                    <th>Origin</th><th>Destination</th>
                  </tr>
                </thead>
                <tbody>
                  {% for f in cargo_fs %}
                  <tr>
                    <td>{{ f.description }}</td>
                    <td class="text-end">{{ f.qty }}</td>
                    <td class="text-end">{{ f.weight_kg }}</td>
                    <td class="text-end">{{ f.volume_cbm }}</td>
                    <td class="text-end">{{ f.amount }}</td>
                    <td>{{ f.origin }}</td>
                    <td>{{ f.destination }}</td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>

            {{ charge_fs.management_form }}
            <h6>Cargo Charge Lines (Optional)</h6>
            <div class="table-responsive">
              <table class="table table-sm align-middle">
                <thead class="table-light">
                  <tr><th>Charge</th><th class="text-end" style="width:100px;">Qty</th><th class="text-end" style="width:140px;">Rate</th><th class="text-end" style="width:140px;">Amount</th></tr>
                </thead>
                <tbody>
                  {% for f in charge_fs %}
                  <tr>
                    <td>{{ f.description }}</td>
                    <td class="text-end">{{ f.qty }}</td>
                    <td class="text-end">{{ f.rate }}</td>
                    <td class="text-end">{{ f.amount }}</td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>

            <div class="d-flex justify-content-between mt-3">
              <a href="?step=header" class="btn btn-outline-secondary rounded-0">Back</a>
              <button class="btn btn-primary rounded-0" type="submit">Create</button>
            </div>
          </form>
        {% endif %}
      </div>
    </div>
    {% endblock %}

    {% block extra_js %}
    <script>
    (function(){
      const modeSel=document.getElementById("id_transport_mode");
      const svcSel=document.getElementById("id_service_option");
      if(!modeSel||!svcSel) return;
      const endpoint="{% url 'sales:freight_service_options' %}";
      function refill(opts){
        const prev=svcSel.value; svcSel.innerHTML="";
        (opts||[]).forEach(o=>{const el=document.createElement("option"); el.value=o.value; el.textContent=o.label; svcSel.appendChild(el);});
        const keep=[...svcSel.options].some(o=>o.value===prev);
        svcSel.value=keep?prev:(svcSel.options[0]?.value||"");
      }
      function fetchOps(mode){
        fetch(endpoint+"?mode="+encodeURIComponent(mode),{headers:{"X-Requested-With":"XMLHttpRequest"}})
          .then(r=>r.json()).then(d=>refill(d.options)).catch(()=>{});
      }
      fetchOps(modeSel.value);
      modeSel.addEventListener("change",()=>fetchOps(modeSel.value));
    })();
    </script>
    {% endblock %}
    """
    write(TPL / "new.html", content)

def main():
    patch_forms()
    patch_views()
    write_template_new()
    print("\n✅ Fix applied.")
    print("➡ Jika Anda menambah field baru di model (mis. payment_term) tapi belum migrate:")
    print("   python manage.py makemigrations sales && python manage.py migrate")
    print("➡ Coba buka: /sales/quotations/freight/new/?step=header")

if __name__ == "__main__":
    main()
