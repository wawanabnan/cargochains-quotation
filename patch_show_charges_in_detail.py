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

# ---- views.py (add cargo_totals & grand_total in quotation_detail) ----
views_patch = r"""
from django import forms as djforms
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.template.loader import render_to_string

from .models import Quotation
from .forms import (
    QuotationFreightForm, CargoFormSet,
    QuotationCharterForm, LegFormSet, CharterChargeFormSet
)

# ====== List & Detail ======
def quotation_list(request):
    qs = Quotation.objects.select_related("customer").order_by("-date","number")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "sales/quotation_list.html", {"page_obj": page_obj})

def quotation_detail(request, pk):
    q = get_object_or_404(Quotation.objects.select_related("customer"), pk=pk)
    if q.business_type == "FREIGHT":
        q = (
            Quotation.objects
            .filter(pk=pk)
            .select_related("customer")
            .prefetch_related("cargos__charges")
            .first()
        )
        cargo_totals = []
        grand_total = 0
        for c in q.cargos.all():
            tot = c.charges.aggregate(s=Sum("amount")).get("s") or 0
            cargo_totals.append((c.id, float(tot)))
            grand_total += float(tot)
    else:
        q = (
            Quotation.objects
            .filter(pk=pk)
            .select_related("customer")
            .prefetch_related("legs","charter_charges")
            .first()
        )
        cargo_totals = []
        grand_total = 0

    # peta {cargo_id: total}
    cargo_totals_map = {cid: tot for cid, tot in cargo_totals}

    return render(
        request,
        "sales/quotation_detail.html",
        {"q": q, "cargo_totals": cargo_totals_map, "grand_total": grand_total},
    )

# ====== Start (v3) ======
WIZ_COMMON_KEY = "sales_wiz_common"
def quotation_wizard_v3_start(request):
    if request.method == "POST":
        bt = (request.POST.get("business_type") or "FREIGHT").upper()
        tm = (request.POST.get("transport_mode") or "SEA").upper()
        so = (request.POST.get("service_option") or "PORT_TO_PORT").upper()
        md = True if request.POST.get("multi_destination") in ("on","true","1","True") else False
        request.session[WIZ_COMMON_KEY] = {"transport_mode": tm, "service_option": so, "multi_destination": md}
        # Fokus Freight dulu
        return redirect(reverse("sales:freight_wizard") + "?step=1")
    return render(request, "sales/quotation_freight_start.html", {})

# ====== Freight Wizard (Step 1 header -> Step 2 cargos) ======
WIZ_FREIGHT_HEADER = "sales_wiz_freight_header"
def freight_wizard(request):
    step = int(request.GET.get("step","1"))
    common = request.session.get(WIZ_COMMON_KEY, {"transport_mode":"SEA","service_option":"PORT_TO_PORT","multi_destination":True})
    show_od_in_header = not common.get("multi_destination", True)

    if step == 1:
        if request.method == "POST":
            post = request.POST.copy()
            post["business_type"] = "FREIGHT"
            qform = QuotationFreightForm(post)
            if qform.is_valid():
                data = qform.cleaned_data
                data["business_type"] = "FREIGHT"
                data.setdefault("transport_mode", common.get("transport_mode"))
                data.setdefault("service_option", common.get("service_option"))
                data.setdefault("multi_destination", common.get("multi_destination"))
                if data.get("multi_destination"):
                    data["origin"] = ""
                    data["destination"] = ""
                request.session[WIZ_FREIGHT_HEADER] = data
                request.session.modified = True
                return redirect(reverse("sales:freight_wizard") + "?step=2")
            return render(request, "sales/quotation_freight.html", {"step":1,"mode":"FREIGHT","qform":qform,"fs":None,"common":common,"show_od_in_header":show_od_in_header})
        else:
            initial = request.session.get(WIZ_FREIGHT_HEADER, {"business_type":"FREIGHT", **common})
            if initial.get("multi_destination"):
                initial["origin"] = ""
                initial["destination"] = ""
            return render(request, "sales/quotation_freight.html", {"step":1,"mode":"FREIGHT","qform":QuotationFreightForm(initial=initial),"fs":None,"common":common,"show_od_in_header":show_od_in_header})

    if step == 2:
        from django import forms as djforms
        header = request.session.get(WIZ_FREIGHT_HEADER)
        if not header:
            return redirect(reverse("sales:freight_wizard") + "?step=1")
        multi_dest = bool(header.get("multi_destination"))

        fs = CargoFormSet(request.POST or None, prefix="cargo")
        if not multi_dest:
            for f in fs.forms:
                if "origin" in f.fields:
                    f.fields["origin"].widget = djforms.HiddenInput()
                    if header.get("origin"): f.initial["origin"] = header.get("origin")
                if "destination" in f.fields:
                    f.fields["destination"].widget = djforms.HiddenInput()
                    if header.get("destination"): f.initial["destination"] = header.get("destination")

        if request.method == "POST":
            if request.POST.get("_action") == "back":
                return redirect(reverse("sales:freight_wizard") + "?step=1")

            def ok(fs):
                tot=0
                for f in fs:
                    if f.cleaned_data.get("DELETE"): continue
                    if f.cleaned_data.get("description"): tot+=1
                return tot>0

            if fs.is_valid() and ok(fs):
                with transaction.atomic():
                    qf = QuotationFreightForm(header); qf.is_valid()
                    q = qf.save(commit=False); q.business_type="FREIGHT"; q.save()
                    fs.instance = q; fs.save()
                    if not multi_dest and (header.get("origin") or header.get("destination")):
                        for c in q.cargos.all():
                            changed=False
                            if header.get("origin"): c.origin = header["origin"]; changed=True
                            if header.get("destination"): c.destination = header["destination"]; changed=True
                            if changed: c.save(update_fields=["origin","destination"])
                    request.session.pop(WIZ_FREIGHT_HEADER, None)
                return redirect("sales:quotation_detail", pk=q.pk)

        return render(request, "sales/quotation_freight.html", {
            "step":2,"mode":"FREIGHT",
            "qform":QuotationFreightForm(initial=header),
            "fs":fs,"common":common,"show_od_in_header":not multi_dest
        })

    return redirect(reverse("sales:freight_wizard") + "?step=1")

# ====== PDF export (tetap) ======
def quotation_pdf(request, pk, kind="detail"):
    q = get_object_or_404(Quotation.objects.select_related("customer"), pk=pk)
    if q.business_type == "FREIGHT":
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("cargos__charges").first())
    else:
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("legs","charter_charges").first())

    cargo_totals = []
    grand_total = 0
    for c in getattr(q, "cargos", []).all() if hasattr(q, "cargos") else []:
        tot = c.charges.aggregate(s=Sum("amount")).get("s") or 0
        cargo_totals.append((c, tot))
        grand_total += tot

    context = {"q": q, "cargo_totals": cargo_totals, "grand_total": grand_total}
    template = "sales/quotation_pdf_detail.html" if kind.lower() == "detail" else "sales/quotation_pdf_summary.html"
    html = render_to_string(template, context)

    try:
        from weasyprint import HTML
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{q.number}-{kind}.pdf"'
        HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf(response)
        return response
    except Exception:
        return HttpResponse(html)
"""

detail_tpl = r"""
{% extends "sales/base.html" %}
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
      <div class="p-3">
        <h6 class="mb-2">Cargos & Charges</h6>

        {% for c in q.cargos.all %}
          <div class="mb-3">
            <div class="fw-semibold">{{ c.description }} <span class="cc-muted">({{ c.origin|default:"-" }} → {{ c.destination|default:"-" }})</span></div>

            <div class="table-responsive">
              <table class="table table-sm cc-table mb-1">
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
                <tfoot>
                  <tr>
                    <th colspan="3" class="text-end">Subtotal</th>
                    <th class="text-end">
                      {{ cargo_totals.c.id }} {# placeholder to avoid errors if not exists #}
                      {% if cargo_totals and c.id in cargo_totals %}
                        {{ cargo_totals.c.id }}
                      {% endif %}
                    </th>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        {% empty %}
          <div class="text-center cc-muted">No cargos</div>
        {% endfor %}

        {% if grand_total %}
          <div class="d-flex justify-content-end mt-2">
            <div class="fw-semibold">Grand Total: {{ grand_total }}</div>
          </div>
        {% endif %}
      </div>
    </div>
  {% endif %}

</div>
{% endblock %}
"""

# NOTE: Django template tidak mendukung akses dictionary dengan key dinamis secara langsung.
# Kita akan tweak sedikit subtotal rendering supaya tidak error:
# Ganti blok <th class="text-end"> subtotal </th> jadi gunakan filter default jika key tak ada.
detail_tpl = detail_tpl.replace(
    "{{ cargo_totals.c.id }} {# placeholder to avoid errors if not exists #}\n                      {% if cargo_totals and c.id in cargo_totals %}\n                        {{ cargo_totals.c.id }}\n                      {% endif %}",
    "{% if cargo_totals %}{{ cargo_totals|get_item:c.id|default:'0' }}{% else %}0{% endif %}"
)

# Tambahkan custom template filter get_item (simple) ke templatetags jika belum ada
TT_DIR = APP / "templatetags"
TT_DIR.mkdir(parents=True, exist_ok=True)
filters_py = """
from django import template
register = template.Library()

@register.filter
def get_item(d, k):
    try:
        return d.get(k, 0)
    except Exception:
        return 0
"""
backup(TT_DIR / "sales_extras.py")
write(TT_DIR / "sales_extras.py", filters_py)

# Update base.html agar load templatetags otomatis? Tidak perlu; load di template detail saja.
detail_tpl = detail_tpl.replace("{% extends \"sales/base.html\" %}",
                                "{% extends \"sales/base.html\" %}\n{% load sales_extras %}")

# Tulis file
views_p = APP / "views.py"
detail_p = TPL / "quotation_detail.html"

backup(views_p)
write(views_p, views_patch)

backup(detail_p)
write(detail_p, detail_tpl)

print("\n✓ Patch applied. Now reload the detail page.")
