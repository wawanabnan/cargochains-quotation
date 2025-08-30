from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    print(f"[write]  {p}")

def ensure_import(txt: str, needle: str, import_line: str) -> str:
    return txt if needle in txt else import_line + "\n" + txt

# -------- models.py: pastikan FreightCargo.price ada --------
def patch_models():
    p = ROOT / "sales" / "models.py"
    if not p.exists():
        print("[skip] sales/models.py not found")
        return
    backup(p)
    txt = p.read_text(encoding="utf-8")

    # Cari blok class FreightCargo
    m = re.search(r"(class\s+FreightCargo\(models\.Model\):)(.*?)(?=\nclass\s+|\Z)", txt, flags=re.S)
    if not m:
        print("[warn] class FreightCargo not found — skip")
        return
    head, body = m.group(1), m.group(2)

    if " price =" not in body:
        # sisipkan price sebelum amount kalau ada, jika tidak ada, sisipkan sebelum __str__
        if re.search(r"\n\s*amount\s*=\s*models\.DecimalField", body):
            body = re.sub(
                r"(\n\s*amount\s*=\s*models\.DecimalField[^\n]*\n)",
                "\n    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)\n\\1",
                body, flags=re.S
            )
        else:
            body = re.sub(
                r"(\n\s*def\s+__str__\s*\()",
                "\n    price = models.DecimalField(max_digits=14, decimal_places=2, default=0)\n\\1",
                body, count=1
            )
        txt = txt[:m.start()] + head + body + txt[m.end():]
        p.write_text(txt, encoding="utf-8")
        print("[patched] sales/models.py -> add FreightCargo.price")
    else:
        print("[ok] FreightCargo.price already exists")

# -------- forms.py: tulis ulang Freight forms dgn borderless & price --------
def patch_forms():
    p = ROOT / "sales" / "forms.py"
    if not p.exists():
        print("[skip] sales/forms.py not found")
        return
    backup(p)
    txt = p.read_text(encoding="utf-8")

    # pastikan import
    txt = ensure_import(txt, "from django import forms", "from django import forms")
    txt = ensure_import(txt, "from django.forms import formset_factory", "from django.forms import formset_factory")
    txt = ensure_import(txt, "from geo.models import Location", "from geo.models import Location")
    txt = ensure_import(txt, "from .models import", "from .models import FreightCargo, FreightCharge")

    # hapus definisi lama FreightCargoForm & FreightChargeForm (jika ada)
    txt = re.sub(r"\nclass\s+FreightCargoForm\([^\)]*\):[\s\S]*?(?=\nclass\s+|\Z)", "\n", txt, flags=re.S)
    txt = re.sub(r"\nclass\s+FreightChargeForm\([^\)]*\):[\s\S]*?(?=\nclass\s+|\Z)", "\n", txt, flags=re.S)
    # hapus formset lama terkait
    txt = re.sub(r"\nCargoFormSet\s*=\s*formset_factory\([^\n]*\)\s*", "\n", txt)
    txt = re.sub(r"\nChargeFormSet\s*=\s*formset_factory\([^\n]*\)\s*", "\n", txt)

    FREIGHT_FORMS = """
    # --- Freight forms (clean) ---
    class FreightCargoForm(forms.ModelForm):
        # queryset akan di-set di views sesuai transport_mode
        origin = forms.ModelChoiceField(
            queryset=Location.objects.none(), required=False,
            widget=forms.Select(attrs={"class": "form-select form-select-sm border-0 bg-transparent p-0"})
        )
        destination = forms.ModelChoiceField(
            queryset=Location.objects.none(), required=False,
            widget=forms.Select(attrs={"class": "form-select form-select-sm border-0 bg-transparent p-0"})
        )

        class Meta:
            model = FreightCargo
            fields = ["description","qty","weight_kg","volume_cbm","price","amount","origin","destination"]
            widgets = {
                "description": forms.TextInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0"}),
                "qty": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end","value":"1"}),
                "weight_kg": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end"}),
                "volume_cbm": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end"}),
                "price": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end"}),
                "amount": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end"}),
            }

    class FreightChargeForm(forms.ModelForm):
        class Meta:
            model = FreightCharge
            fields = ["description","qty","rate","amount"]
            widgets = {
                "description": forms.TextInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0"}),
                "qty": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end","value":"1"}),
                "rate": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end"}),
                "amount": forms.NumberInput(attrs={"class": "form-control form-control-sm border-0 bg-transparent p-0 text-end"}),
            }

    CargoFormSet  = formset_factory(FreightCargoForm,  extra=2, min_num=1, validate_min=True)
    ChargeFormSet = formset_factory(FreightChargeForm, extra=2, min_num=0, validate_min=False)
    """
    txt = txt.rstrip() + "\n\n" + textwrap.dedent(FREIGHT_FORMS).lstrip()
    p.write_text(txt, encoding="utf-8")
    print("[patched] sales/forms.py -> FreightCargoForm/FreightChargeForm clean")

# -------- views.py: tulis ulang wizard + ajax options --------
def patch_views():
    p = ROOT / "sales" / "views.py"
    if not p.exists():
        print("[skip] sales/views.py not found")
        return
    backup(p)
    txt = p.read_text(encoding="utf-8")

    # impor wajib
    txt = ensure_import(txt, "from django.shortcuts import render", "from django.shortcuts import render, redirect, get_object_or_404")
    txt = ensure_import(txt, "from django.contrib import messages", "from django.contrib import messages")
    txt = ensure_import(txt, "from django.views.decorators.http", "from django.views.decorators.http import require_http_methods, require_GET")
    txt = ensure_import(txt, "from django.http import JsonResponse", "from django.http import JsonResponse")
    txt = ensure_import(txt, "import datetime", "import datetime")
    txt = ensure_import(txt, "from .models import FreightQuotation", "from .models import FreightQuotation, FreightCargo, FreightCharge")
    txt = ensure_import(txt, "from .forms import", "from .forms import FreightHeaderForm, FreightCargoForm, FreightChargeForm, CargoFormSet, ChargeFormSet")
    txt = ensure_import(txt, "from geo.models import Location", "from geo.models import Location")

    # hapus definisi lama ajax/service-options & wizard untuk ditulis ulang
    txt = re.sub(r"\n@require_GET\s+def\s+freight_service_options\(.*?\)\n", "\n", txt, flags=re.S)
    txt = re.sub(r"\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\s+def\s+freight_create_wizard\(.*?\n(?=\Z|def\s|\@)", "\n", txt, flags=re.S)

    NEW_VIEWS = """
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

    WKEY = "freight_wizard"

    def _wiz_get(request):
        return request.session.get(WKEY, {"step": "header", "header": {}})

    def _wiz_set(request, data):
        request.session[WKEY] = data
        request.session.modified = True

    def _wiz_clear(request):
        if WKEY in request.session:
            del request.session[WKEY]

    @require_http_methods(["GET", "POST"])
    def freight_create_wizard(request):
        wiz = _wiz_get(request)
        step = (request.GET.get("step") or wiz.get("step") or "header").lower()

        # Reset state saat GET pertama tanpa parameter step
        if request.method == "GET" and "step" not in request.GET:
            _wiz_clear(request)
            wiz = {"step": "header", "header": {}}
            _wiz_set(request, wiz)
            form = FreightHeaderForm()
            return render(request, "sales/freight/wizard.html", {"step": "header", "form_header": form})

        # STEP: HEADER
        if step == "header":
            if request.method == "POST":
                form = FreightHeaderForm(request.POST)
                if form.is_valid():
                    cd = form.cleaned_data
                    wiz["header"] = {
                        "date": cd["date"].isoformat(),
                        "customer_id": cd["customer"].pk,
                        "currency": cd["currency"],
                        "payment_term": cd.get("payment_term") or "",
                        "notes": cd.get("notes") or "",
                        "transport_mode": cd["transport_mode"],
                        "service_option": cd["service_option"],
                    }
                    wiz["step"] = "lines"
                    _wiz_set(request, wiz)
                    return redirect(f"{request.path}?step=lines")
                messages.error(request, "Periksa Header Information.")
            else:
                form = FreightHeaderForm()
            return render(request, "sales/freight/wizard.html", {"step": "header", "form_header": form})

        # Guard: tidak boleh ke lines tanpa header
        if step == "lines" and not wiz.get("header"):
            wiz["step"] = "header"
            _wiz_set(request, wiz)
            form = FreightHeaderForm()
            return render(request, "sales/freight/wizard.html", {"step": "header", "form_header": form})

        # STEP: LINES
        if step == "lines":
            hdr = wiz["header"]
            CargoFS = CargoFormSet
            ChargeFS = ChargeFormSet

            if request.method == "POST":
                cargo_fs = CargoFS(request.POST, prefix="cargo")
                charge_fs = ChargeFS(request.POST, prefix="charge")

                # Filter Location sesuai mode
                mode = hdr.get("transport_mode", "SEA").upper()
                if mode == "SEA":
                    loc_types = [Location.SEAPORT, Location.JETTY]
                elif mode == "AIR":
                    loc_types = [Location.AIRPORT]
                else:
                    loc_types = [Location.CITY, Location.JETTY]
                loc_qs = Location.objects.filter(type__in=loc_types).order_by("name")
                for f in cargo_fs.forms:
                    if "origin" in f.fields:
                        f.fields["origin"].queryset = loc_qs
                    if "destination" in f.fields:
                        f.fields["destination"].queryset = loc_qs

                if cargo_fs.is_valid() and charge_fs.is_valid():
                    q = FreightQuotation.objects.create(
                        date=datetime.date.fromisoformat(hdr["date"]),
                        customer_id=hdr["customer_id"],
                        currency=hdr["currency"] or "IDR",
                        payment_term=hdr.get("payment_term", ""),
                        transport_mode=hdr["transport_mode"],
                        service_option=hdr["service_option"],
                        notes=hdr.get("notes", ""),
                        multi_destination=False,
                    )

                    cargos_created = 0
                    for f in cargo_fs:
                        cd = f.cleaned_data or {}
                        if not cd:
                            continue
                        qty = cd.get("qty") or 1
                        price = cd.get("price") or 0
                        amount = cd.get("amount")
                        if amount in (None, "", 0):
                            amount = qty * price
                        FreightCargo.objects.create(
                            quotation=q,
                            description=cd.get("description"),
                            qty=qty,
                            weight_kg=cd.get("weight_kg") or 0,
                            volume_cbm=cd.get("volume_cbm") or 0,
                            price=price,
                            amount=amount,
                            origin=cd.get("origin"),
                            destination=cd.get("destination"),
                        )
                        cargos_created += 1

                    if cargos_created < 1:
                        q.delete()
                        messages.error(request, "Minimal satu Cargo wajib diisi.")
                        return render(request, "sales/freight/wizard.html", {
                            "step": "lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs
                        })

                    # Charges opsional: attach ke cargo pertama
                    first_cargo = q.cargos.first()
                    if first_cargo:
                        for f in charge_fs:
                            cd = f.cleaned_data or {}
                            if not cd:
                                continue
                            if not (cd.get("description") or cd.get("qty") or cd.get("rate") or cd.get("amount")):
                                continue
                            qty = cd.get("qty") or 1
                            rate = cd.get("rate") or 0
                            amount = cd.get("amount")
                            if amount in (None, "", 0):
                                amount = qty * rate
                            FreightCharge.objects.create(
                                cargo=first_cargo,
                                description=cd.get("description", ""),
                                qty=qty,
                                rate=rate,
                                amount=amount,
                            )

                    # done
                    if 'freight_list' in globals():
                        pass
                    _wiz_clear(request)
                    messages.success(request, "Freight Quotation berhasil dibuat.")
                    try:
                        return redirect("sales:freight_list")
                    except Exception:
                        # kalau belum ada named url, kembali ke list generic
                        return redirect("/sales/quotations/freight/")

                messages.error(request, "Periksa isian Cargo / Charge.")
                return render(request, "sales/freight/wizard.html", {
                    "step": "lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs
                })

            # GET
            cargo_fs = CargoFS(prefix="cargo")
            charge_fs = ChargeFS(prefix="charge")
            mode = hdr.get("transport_mode", "SEA").upper()
            if mode == "SEA":
                loc_types = [Location.SEAPORT, Location.JETTY]
            elif mode == "AIR":
                loc_types = [Location.AIRPORT]
            else:
                loc_types = [Location.CITY, Location.JETTY]
            loc_qs = Location.objects.filter(type__in=loc_types).order_by("name")
            for f in cargo_fs.forms:
                if "origin" in f.fields:
                    f.fields["origin"].queryset = loc_qs
                if "destination" in f.fields:
                    f.fields["destination"].queryset = loc_qs

            return render(request, "sales/freight/wizard.html", {
                "step": "lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs
            })

        # fallback aman
        wiz["step"] = "header"
        _wiz_set(request, wiz)
        form = FreightHeaderForm()
        return render(request, "sales/freight/wizard.html", {"step": "header", "form_header": form})
    """
    txt = txt.rstrip() + "\n\n" + textwrap.dedent(NEW_VIEWS).lstrip()
    p.write_text(txt, encoding="utf-8")
    print("[patched] sales/views.py -> wizard & ajax rewritten")

# -------- urls.py: pastikan route AJAX ada --------
def patch_urls():
    p = ROOT / "sales" / "urls.py"
    if not p.exists():
        print("[skip] sales/urls.py not found")
        return
    backup(p)
    txt = p.read_text(encoding="utf-8")
    if "from . import views" not in txt:
        txt = "from . import views\n" + txt
    if "freight_service_options" not in txt:
        # selipkan sebelum penutup urlpatterns
        txt = re.sub(
            r"(urlpatterns\s*=\s*\[\s*)",
            r"\\1\n    path('quotations/freight/service-options/', views.freight_service_options, name='freight_service_options'),\n",
            txt
        )
        # ensure import path
        if "from django.urls import path" not in txt:
            txt = "from django.urls import path\n" + txt
        p.write_text(txt, encoding="utf-8")
        print("[patched] sales/urls.py -> add freight_service_options")
    else:
        print("[ok] sales/urls.py already has freight_service_options")

# -------- template wizard.html --------
def patch_template():
    p = ROOT / "templates" / "sales" / "freight" / "wizard.html"
    backup(p)
    TPL = """
    {% extends "base.html" %}
    {% block title %}Freight Quotation Wizard{% endblock %}

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
          <form method="post" novalidate>
            {% csrf_token %}
            <div class="row g-3">
              <div class="col-12 col-md-4">
                <label class="form-label">Date</label>
                {{ form_header.date }} {{ form_header.date.errors }}
              </div>
              <div class="col-12 col-md-4">
                <label class="form-label">Customer</label>
                {{ form_header.customer }} {{ form_header.customer.errors }}
              </div>
              <div class="col-12 col-md-4">
                <label class="form-label">Currency</label>
                {{ form_header.currency }} {{ form_header.currency.errors }}
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label">Payment Term</label>
                {{ form_header.payment_term }} {{ form_header.payment_term.errors }}
              </div>
              <div class="col-12">
                <label class="form-label">Notes</label>
                {{ form_header.notes }} {{ form_header.notes.errors }}
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label">Moda Transportasi</label>
                {{ form_header.transport_mode }} {{ form_header.transport_mode.errors }}
              </div>
              <div class="col-12 col-md-6">
                <label class="form-label">Service Option</label>
                {{ form_header.service_option }} {{ form_header.service_option.errors }}
              </div>
            </div>
            <div class="d-flex justify-content-between mt-3">
              <a href="{% url 'sales:freight_list' %}" class="btn btn-outline-secondary rounded-0">Cancel</a>
              <button class="btn btn-primary rounded-0" type="submit">Next</button>
            </div>
          </form>

        {% elif step == 'lines' %}
          <form method="post" novalidate>
            {% csrf_token %}

            {{ cargo_fs.management_form }}
            <h6 class="mb-2">Cargo Detail</h6>
            <div class="table-responsive mb-3">
              <table class="table table-sm align-middle">
                <thead class="table-light">
                  <tr>
                    <th>Description</th>
                    <th class="text-end" style="width:100px;">Qty</th>
                    <th class="text-end" style="width:120px;">Weight (kg)</th>
                    <th class="text-end" style="width:120px;">Volume (cbm)</th>
                    <th class="text-end" style="width:120px;">Price</th>
                    <th class="text-end" style="width:140px;">Amount</th>
                    <th style="width:220px;">Origin</th>
                    <th style="width:220px;">Destination</th>
                  </tr>
                </thead>
                <tbody>
                  {% for f in cargo_fs %}
                  <tr>
                    <td>{{ f.description }} {{ f.description.errors }}</td>
                    <td class="text-end">{{ f.qty }} {{ f.qty.errors }}</td>
                    <td class="text-end">{{ f.weight_kg }} {{ f.weight_kg.errors }}</td>
                    <td class="text-end">{{ f.volume_cbm }} {{ f.volume_cbm.errors }}</td>
                    <td class="text-end">{{ f.price }} {{ f.price.errors }}</td>
                    <td class="text-end">{{ f.amount }} {{ f.amount.errors }}</td>
                    <td>{{ f.origin }} {{ f.origin.errors }}</td>
                    <td>{{ f.destination }} {{ f.destination.errors }}</td>
                  </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>

            {{ charge_fs.management_form }}
            <h6 class="mb-2">Cargo Charge Lines <small class="text-muted">(optional)</small></h6>
            <div class="table-responsive">
              <table class="table table-sm align-middle">
                <thead class="table-light">
                  <tr>
                    <th>Charge</th>
                    <th class="text-end" style="width:100px;">Qty</th>
                    <th class="text-end" style="width:140px;">Rate</th>
                    <th class="text-end" style="width:140px;">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {% for f in charge_fs %}
                  <tr>
                    <td>{{ f.description }} {{ f.description.errors }}</td>
                    <td class="text-end">{{ f.qty }} {{ f.qty.errors }}</td>
                    <td class="text-end">{{ f.rate }} {{ f.rate.errors }}</td>
                    <td class="text-end">{{ f.amount }} {{ f.amount.errors }}</td>
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
      if(modeSel && svcSel){
        const endpoint="{% url 'sales:freight_service_options' %}";
        const FALLBACK = {
          SEA:[{value:"DOOR_TO_DOOR",label:"Door to Door"},{value:"DOOR_TO_PORT",label:"Door to Port"},{value:"PORT_TO_PORT",label:"Port to Port"}],
          AIR:[{value:"DOOR_TO_AIRPORT",label:"Door to Airport"},{value:"AIRPORT_TO_AIRPORT",label:"Airport to Airport"}],
          LAND:[{value:"TRUCKING",label:"Trucking"}],
        };
        function refill(opts){
          const prev=svcSel.value; svcSel.innerHTML="";
          (opts||[]).forEach(o=>{
            const el=document.createElement("option");
            el.value=o.value; el.textContent=o.label; svcSel.appendChild(el);
          });
          if (![...svcSel.options].some(o=>o.value===prev) && svcSel.options.length){
            svcSel.value=svcSel.options[0].value;
          }
        }
        async function fetchOps(mode){
          try{
            const ctl = new AbortController();
            const t=setTimeout(()=>ctl.abort(),4000);
            const r=await fetch(endpoint+"?mode="+encodeURIComponent(mode),{headers:{"X-Requested-With":"XMLHttpRequest"},signal:ctl.signal});
            clearTimeout(t);
            if(!r.ok){ refill(FALLBACK[mode]||[]); return; }
            const d=await r.json();
            refill(d.options && d.options.length ? d.options : (FALLBACK[mode]||[]));
          }catch(e){ refill(FALLBACK[mode]||[]); }
        }
        fetchOps(modeSel.value);
        modeSel.addEventListener("change",()=>fetchOps(modeSel.value));
      }

      // Auto-calc: Cargo amount = qty * price ; Charge amount = qty * rate
      function calcRowQtyPrice(row, qtyName, priceName, amountName){
        const q=row.querySelector(`[name$='-${qtyName}']`);
        const p=row.querySelector(`[name$='-${priceName}']`);
        const a=row.querySelector(`[name$='-${amountName}']`);
        if(!q||!p||!a) return;
        const qv=parseFloat(q.value||'1'); const pv=parseFloat(p.value||'0');
        a.value=((isNaN(qv)?1:qv)*(isNaN(pv)?0:pv)).toFixed(2);
      }
      function bind(tableSel, qtyName, priceName, amountName){
        document.querySelectorAll(tableSel+' tbody tr').forEach(tr=>{
          const handler=()=>calcRowQtyPrice(tr, qtyName, priceName, amountName);
          tr.addEventListener('input', handler);
          handler();
        });
      }
      // Cargo: table pertama
      bind('.card-body table:nth-of-type(1)', 'qty','price','amount');
      // Charge: table kedua (rate sebagai "price")
      bind('.card-body table:nth-of-type(2)', 'qty','rate','amount');
    })();
    </script>
    {% endblock %}
    """
    write(p, TPL)
    print("[patched] wizard.html written")

def main():
    patch_models()
    patch_forms()
    patch_views()
    patch_urls()
    patch_template()
    print("\n✅ Done. Next:")
    print("   python manage.py makemigrations sales")
    print("   python manage.py migrate")
    print("   python manage.py runserver")
    print("\nBuka: /sales/quotations/freight/new/ (harus mulai di Header, lalu Lines)")
    print("Jika masih ada error, kirim baris error & file terkait, aku rapikan lagi spot-nya.")

if __name__ == "__main__":
    main()
