from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.core.paginator import Paginator
from django.db import transaction
from .models import Quotation
from .forms import (
    QuotationFreightForm, CargoFormSet, CargoChargeFormSet,
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
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("cargos__charges").first())
    else:
        q = (Quotation.objects.filter(pk=pk).select_related("customer").prefetch_related("legs","charter_charges").first())
    return render(request, "sales/quotation_detail.html", {"q": q})

# ====== Start (v3) ======
WIZ_COMMON_KEY = "sales_wiz_common"
def quotation_wizard_v3_start(request):
    if request.method == "POST":
        bt = (request.POST.get("business_type") or "FREIGHT").upper()
        ctype = (request.POST.get("charter_type") or "VOYAGE").upper()
        tm = (request.POST.get("transport_mode") or "SEA").upper()
        so = (request.POST.get("service_option") or "PORT_TO_PORT").upper()
        md = True if request.POST.get("multi_destination") in ("on","true","1","True") else False
        request.session[WIZ_COMMON_KEY] = {"transport_mode": tm, "service_option": so, "multi_destination": md}
        if bt == "FREIGHT":
            return redirect(reverse("sales:freight_wizard") + "?step=1")
        else:
            return redirect(reverse("sales:charter_wizard") + f"?step=1&ctype={ctype}")
    return render(request, "sales/quotation_wizard_v3_start.html", {})

# ====== Freight Wizard (Step 1 header -> Step 2 cargos) ======
WIZ_FREIGHT_HEADER = "sales_wiz_freight_header"
def freight_wizard(request):
    step = int(request.GET.get("step","1"))
    common = request.session.get(WIZ_COMMON_KEY, {"transport_mode":"SEA","service_option":"PORT_TO_PORT","multi_destination":True})

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
                request.session[WIZ_FREIGHT_HEADER] = data
                request.session.modified = True
                return redirect(reverse("sales:freight_wizard") + "?step=2")
            return render(request, "sales/quotation_wizard.html", {"step":1,"mode":"FREIGHT","qform":qform,"fs":None,"common":common})
        else:
            initial = request.session.get(WIZ_FREIGHT_HEADER, {"business_type":"FREIGHT", **common})
            return render(request, "sales/quotation_wizard.html", {"step":1,"mode":"FREIGHT","qform":QuotationFreightForm(initial=initial),"fs":None,"common":common})

    if step == 2:
        header = request.session.get(WIZ_FREIGHT_HEADER)
        if not header:
            return redirect(reverse("sales:freight_wizard") + "?step=1")
        fs = CargoFormSet(request.POST or None, prefix="cargo")
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
                    request.session.pop(WIZ_FREIGHT_HEADER, None)
                return redirect("sales:quotation_detail", pk=q.pk)
        return render(request, "sales/quotation_wizard.html", {"step":2,"mode":"FREIGHT","qform":QuotationFreightForm(initial=header),"fs":fs,"common":common})

    return redirect(reverse("sales:freight_wizard") + "?step=1")

# ====== Charter Wizard (Step 1 header -> Step 2 legs/charges for VOYAGE) ======
WIZ_CHARTER_HEADER = "sales_wiz_charter_header"
def charter_wizard(request):
    step = int(request.GET.get("step","1"))
    ctype = (request.GET.get("ctype") or request.POST.get("ctype") or "VOYAGE").upper()
    common = request.session.get(WIZ_COMMON_KEY, {"transport_mode":"SEA","service_option":"PORT_TO_PORT","multi_destination":False})

    if step == 1:
        if request.method == "POST":
            post = request.POST.copy(); post["charter_type"] = ctype
            qform = QuotationCharterForm(post)
            if qform.is_valid():
                data = qform.cleaned_data; data["charter_type"] = ctype
                request.session[WIZ_CHARTER_HEADER] = data; request.session.modified = True
                return redirect(reverse("sales:charter_wizard") + f"?step=2&ctype={ctype}")
            return render(request, "sales/quotation_wizard.html", {"step":1,"mode":"CHARTER","ctype":ctype,"qform":qform,"fs":None,"common":common})
        else:
            initial = request.session.get(WIZ_CHARTER_HEADER, {"business_type":"SHIP_CHARTER","charter_type":ctype})
            return render(request, "sales/quotation_wizard.html", {"step":1,"mode":"CHARTER","ctype":ctype,"qform":QuotationCharterForm(initial=initial),"fs":None,"common":common})

    if step == 2:
        hdr = request.session.get(WIZ_CHARTER_HEADER)
        if not hdr:
            return redirect(reverse("sales:charter_wizard") + f"?step=1&ctype={ctype}")
        if request.method == "POST":
            if request.POST.get("_action") == "back":
                return redirect(reverse("sales:charter_wizard") + f"?step=1&ctype={ctype}")
            with transaction.atomic():
                qf = QuotationCharterForm(hdr); qf.is_valid()
                q = qf.save(commit=False); q.business_type="SHIP_CHARTER"; q.charter_type=ctype; q.save()
                if ctype == "VOYAGE":
                    legfs = LegFormSet(request.POST, instance=q, prefix="legs")
                    chgfs = CharterChargeFormSet(request.POST, instance=q, prefix="chg")
                    if legfs.is_valid() and chgfs.is_valid():
                        legfs.save(); chgfs.save()
                    else:
                        q.delete()
                        return render(request, "sales/quotation_wizard.html", {"step":2,"mode":"CHARTER","ctype":ctype,"qform":QuotationCharterForm(initial=hdr),"fs":legfs,"legfs":legfs,"chgfs":chgfs,"common":common})
                request.session.pop(WIZ_CHARTER_HEADER, None)
            return redirect("sales:quotation_detail", pk=q.pk)

        if ctype == "VOYAGE":
            legfs = LegFormSet(prefix="legs"); chgfs = CharterChargeFormSet(prefix="chg")
            return render(request, "sales/quotation_wizard.html", {"step":2,"mode":"CHARTER","ctype":ctype,"qform":QuotationCharterForm(initial=hdr),"fs":legfs,"legfs":legfs,"chgfs":chgfs,"common":common})
        else:
            return render(request, "sales/quotation_wizard.html", {"step":2,"mode":"CHARTER","ctype":ctype,"qform":QuotationCharterForm(initial=hdr),"fs":None,"common":common})

    return redirect(reverse("sales:charter_wizard") + f"?step=1&ctype={ctype}")
