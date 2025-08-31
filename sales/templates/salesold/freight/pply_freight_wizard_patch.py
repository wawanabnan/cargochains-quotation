# apply_freight_wizard_patch.py
from pathlib import Path
import shutil, textwrap, datetime

ROOT = Path(__file__).resolve().parent
APP  = ROOT / "sales"
TPL  = ROOT / "templates" / "sales" / "freight"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    print(f"[write]  {p}")

def patch_views():
    p = APP / "views.py"
    backup(p)
    content = """
    from django.shortcuts import render, redirect, get_object_or_404
    from django.contrib import messages
    from django.views.decorators.http import require_http_methods, require_GET
    from django.db import transaction
    from django.http import JsonResponse
    import datetime

    from .models import FreightQuotation, FreightCargo, FreightCharge
    from .forms import (
        FreightHeaderForm, FreightCargoForm, FreightChargeForm,
        CargoFormSet, ChargeFormSet
    )
    from geo.models import Location

    # --- AJAX: service options by transport mode ---
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

    # --- LIST ---
    def freight_list(request):
        qs = FreightQuotation.objects.all()
        return render(request, "sales/freight/list.html", {"quotations": qs})

    # --- Wizard state (2 langkah: header -> lines) ---
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

        # guard jika langsung ke lines tanpa header
        if step == "lines" and not wiz.get("header"):
            wiz["step"] = "header"
            _wiz_set(request, wiz)
            form = FreightHeaderForm()
            return render(request, "sales/freight/wizard.html", {"step": "header", "form_header": form})

        # STEP: LINES (cargo + optional charges)
        if step == "lines":
            hdr = wiz["header"]
            CargoFS = CargoFormSet
            ChargeFS = ChargeFormSet

            if request.method == "POST":
                cargo_fs = CargoFS(request.POST, prefix="cargo")
                charge_fs = ChargeFS(request.POST, prefix="charge")

                # filter Location menurut transport mode
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
                        origin=None,
                        destination=None,
                    )

                    cargos_created = 0
                    for f in cargo_fs:
                        cd = f.cleaned_data or {}
                        if not cd:
                            continue
                        FreightCargo.objects.create(
                            quotation=q,
                            description=cd.get("description"),
                            qty=cd.get("qty") or 0,
                            weight_kg=cd.get("weight_kg") or 0,
                            volume_cbm=cd.get("volume_cbm") or 0,
                            amount=cd.get("amount") or 0,
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

                    # charges opsional — attach ke cargo pertama
                    first_cargo = q.cargos.first()
                    if first_cargo:
                        for f in charge_fs:
                            cd = f.cleaned_data or {}
                            if not cd:
                                continue
                            if not (cd.get("description") or cd.get("qty") or cd.get("rate") or cd.get("amount")):
                                continue
                            FreightCharge.objects.create(
                                cargo=first_cargo,
                                description=cd.get("description", ""),
                                qty=cd.get("qty") or 0,
                                rate=cd.get("rate") or 0,
                                amount=cd.get("amount") or 0,
                            )

                    _wiz_clear(request)
                    messages.success(request, "Freight Quotation berhasil dibuat.")
                    return redirect("sales:freight_list")

                messages.error(request, "Periksa isian Cargo / Charge.")
                return render(request, "sales/freight/wizard.html", {
                    "step": "lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs
                })

            # GET
            cargo_fs = CargoFS(prefix="cargo")
            charge_fs = ChargeFS(prefix="charge")

            # set queryset untuk dropdown lokasi
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

        # fallback aman: render header (hindari redirect loop)
        wiz["step"] = "header"
        _wiz_set(request, wiz)
        form = FreightHeaderForm()
        return render(request, "sales/freight/wizard.html", {"step": "header", "form_header": form})

    # --- VIEW / EDIT ---
    def freight_view(request, pk):
        q = get_object_or_404(FreightQuotation, pk=pk)
        return render(request, "sales/freight/view.html", {"q": q})

    @require_http_methods(["GET", "POST"])
    @transaction.atomic
    def freight_edit(request, pk):
        q = get_object_or_404(FreightQuotation, pk=pk)
        if request.method == "POST":
            form = FreightHeaderForm(request.POST, instance=q)
            if form.is_valid():
                obj = form.save(commit=False)
                cd = form.cleaned_data
                q.transport_mode = cd["transport_mode"]
                q.service_option = cd["service_option"]
                q.payment_term  = cd.get("payment_term") or ""
                q.currency      = cd.get("currency") or q.currency
                obj.save()
                messages.success(request, "Quotation updated.")
                return redirect("sales:freight_view", pk=q.pk)
        else:
            initial = {
                "transport_mode": q.transport_mode,
                "service_option": q.service_option,
                "payment_term": q.payment_term,
                "currency": q.currency,
            }
            form = FreightHeaderForm(instance=q, initial=initial)
        return render(request, "sales/freight/edit.html", {"form": form, "q": q})
    """
    write(p, content)

def patch_urls():
    u = APP / "urls.py"
    backup(u)
    if not u.exists():
        print("[warn] sales/urls.py tidak ditemukan — lewati.")
        return
    txt = u.read_text(encoding="utf-8")
    # pastikan ada import views (umumnya sudah ada)
    if "from . import views" not in txt:
        txt = "from . import views\n" + txt

    # tambahkan route service-options jika belum ada
    if "freight_service_options" not in txt:
        insert = "    path('quotations/freight/service-options/', views.freight_service_options, name='freight_service_options'),\n"
        # selipkan sebelum penutup urlpatterns
        txt = txt.replace("]", f"{insert}]\n") if txt.strip().endswith("]") else txt + "\nurlpatterns += [\n" + insert + "]\n"

    u.write_text(txt, encoding="utf-8")
    print("[patched] sales/urls.py (service-options route)")

def write_template():
    write(TPL / "wizard.html", """
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
            {% if form_header.non_field_errors %}
              <div class="alert alert-danger py-2 mb-3">{{ form_header.non_field_errors }}</div>
            {% endif %}

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
      if(!modeSel||!svcSel) return;
      const endpoint="{% url 'sales:freight_service_options' %}";

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
        const FALLBACK = {
          SEA:[{value:"DOOR_TO_DOOR",label:"Door to Door"},{value:"DOOR_TO_PORT",label:"Door to Port"},{value:"PORT_TO_PORT",label:"Port to Port"}],
          AIR:[{value:"DOOR_TO_AIRPORT",label:"Door to Airport"},{value:"AIRPORT_TO_AIRPORT",label:"Airport to Airport"}],
          LAND:[{value:"TRUCKING",label:"Trucking"}],
        };
        try{
          const ctl = new AbortController();
          const t = setTimeout(()=>ctl.abort(), 4000);
          const r = await fetch(endpoint+"?mode="+encodeURIComponent(mode),{
            headers:{"X-Requested-With":"XMLHttpRequest"},
            signal: ctl.signal
          });
          clearTimeout(t);
          if(!r.ok){ refill(FALLBACK[mode]||[]); return; }
          const d = await r.json();
          refill(d.options && d.options.length ? d.options : (FALLBACK[mode]||[]));
        }catch(e){
          refill(FALLBACK[mode]||[]);
        }
      }

      fetchOps(modeSel.value);
      modeSel.addEventListener("change",()=>fetchOps(modeSel.value));
    })();
    </script>
    {% endblock %}
    """)
    print("[ok] wizard template written")

def main():
    patch_views()
    patch_urls()
    write_template()
    print("\\n✅ Patch selesai. Coba jalankan:")
    print("   -> python manage.py runserver")
    print("   Buka: /sales/quotations/freight/new/?step=header")
    print("\\nCatatan:")
    print(" - Pastikan SessionMiddleware aktif di settings.py")
    print(" - Origin/Destination di Cargo akan autofilter berdasarkan transport_mode")
    print(" - Endpoint AJAX: /sales/quotations/freight/service-options/")

if __name__ == "__main__":
    main()
