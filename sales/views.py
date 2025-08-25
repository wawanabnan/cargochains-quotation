from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView
from django.db import transaction
from django.forms.utils import ErrorList
from .models import Quotation, Cargo
from .forms import QuotationForm, CargoFormSet, ChargeFormSetFactory

class QuotationListView(ListView):
    model = Quotation
    template_name = "sales/quotation_list.html"
    context_object_name = "quotations"
    ordering = ["-date","-id"]
    paginate_by = 20

class QuotationDetailView(DetailView):
    model = Quotation
    template_name = "sales/quotation_detail.html"
    context_object_name = "quotation"

# Wizard 1-halaman: Header → Cargo(s) → Charges per Cargo (save once)
def quotation_wizard(request):
    # ## PRESET_FROM_START: baca pilihan dari Step 0 (querystring)
    preset_mode = (request.GET.get('mode') or '').upper() or None
    preset_service = (request.GET.get('service') or '').upper() or None
    preset_multi = request.GET.get('multi')
    if preset_multi is not None:
        preset_multi = True if str(preset_multi) in ('1','true','True','on') else False
    if request.method == "POST":
        header_form = QuotationForm(request.POST)
        cargo_formset = CargoFormSet(request.POST, prefix="cargo")

        # kumpulkan charge formset per cargo index
        CFSF = ChargeFormSetFactory()
        total_cargo = int(request.POST.get("cargo-TOTAL_FORMS", "0") or "0")
        charge_formsets = []
        for i in range(total_cargo):
            if request.POST.get(f"cargo-{i}-DELETE") == "on":
                continue
            fs = CFSF(data=request.POST, prefix=f"chg-{i}", instance=None)
            charge_formsets.append((i, fs))

        valid = header_form.is_valid() and cargo_formset.is_valid() and all(fs.is_valid() for _, fs in charge_formsets)

        # Validasi bisnis: min 1 cargo
        from django.core.exceptions import ValidationError
        active_cargo_idx = []
        for i in range(total_cargo):
            if request.POST.get(f"cargo-{i}-DELETE") == "on":
                continue
            if any(request.POST.get(f"cargo-{i}-{k}", "").strip()
                   for k in ["description","package_type","qty","weight_kg","volume_cbm","origin","destination","extra_notes"]):
                active_cargo_idx.append(i)
        if len(active_cargo_idx) < 1:
            header_form.add_error(None, ValidationError("Minimal harus ada 1 cargo."))
            valid = False

        # tiap cargo min 1 charge
        for i, fs in charge_formsets:
            active_lines = 0
            for form in fs.forms:
                if form.cleaned_data.get("DELETE", False):
                    continue
                if any(form.cleaned_data.get(k) for k in ["charge_type","description","unit","qty","rate","currency"]):
                    active_lines += 1
            if active_lines < 1:
                fs._non_form_errors = ErrorList([f"Minimal 1 charge untuk cargo ke-{i+1}."])
                valid = False

        if not valid:
            return render(request, "sales/quotation_wizard.html", {
                "header_form": header_form,
                "cargo_formset": cargo_formset,
                "charge_formsets": charge_formsets,
            })

        with transaction.atomic():
            q = header_form.save(commit=False)
            q.save()

            saved = []
            for i in range(total_cargo):
                if request.POST.get(f"cargo-{i}-DELETE") == "on":
                    continue
                if not any(request.POST.get(f"cargo-{i}-{k}", "").strip()
                           for k in ["description","package_type","qty","weight_kg","volume_cbm","origin","destination","extra_notes"]):
                    continue
                c = Cargo(
                    quotation=q,
                    description=request.POST.get(f"cargo-{i}-description","").strip(),
                    package_type=request.POST.get(f"cargo-{i}-package_type","").strip(),
                    qty=request.POST.get(f"cargo-{i}-qty","") or 0,
                    weight_kg=request.POST.get(f"cargo-{i}-weight_kg","") or 0,
                    volume_cbm=request.POST.get(f"cargo-{i}-volume_cbm","") or 0,
                    origin=request.POST.get(f"cargo-{i}-origin","").strip(),
                    destination=request.POST.get(f"cargo-{i}-destination","").strip(),
                    extra_notes=request.POST.get(f"cargo-{i}-extra_notes","").strip(),
                )
                c.save()
                saved.append((i, c))

            # save charges
            for i, c in saved:
                CFSF2 = ChargeFormSetFactory()
                fs = CFSF2(data=request.POST, prefix=f"chg-{i}", instance=c)
                if fs.is_valid():
                    fs.save()
                else:
                    raise ValidationError(f"Data charges invalid pada cargo ke-{i+1}.")

        return redirect("sales:quotation_detail", pk=q.pk)

    # GET
    header_form = QuotationForm()
    cargo_formset = CargoFormSet(prefix="cargo")
    return render(request, "sales/quotation_wizard.html", {
        "header_form": header_form,
        "cargo_formset": cargo_formset,
    })


# -------- PDF EXPORT --------
from django.http import HttpResponse
from django.template.loader import render_to_string

def quotation_pdf(request, pk: int):
    from .models import Quotation
    quotation = Quotation.objects.prefetch_related("cargos__charges").get(pk=pk)

    mode = (request.GET.get("mode") or "detail").lower()
    show_lines = (mode != "summary")  # kalau summary → jangan tampilkan breakdown lines

    html = render_to_string("sales/quotation_pdf.html", {
        "quotation": quotation,
        "show_lines": show_lines,
        "mode": mode,
    })
    # Try xhtml2pdf
    try:
        from xhtml2pdf import pisa
        from io import BytesIO
        result = BytesIO()
        pdf = pisa.CreatePDF(src=html, dest=result, encoding="utf-8")
        if not pdf.err:
            resp = HttpResponse(result.getvalue(), content_type="application/pdf")
            filename = f"quotation-{quotation.number or quotation.pk}.pdf"
            resp['Content-Disposition'] = f'inline; filename="{filename}"'
            return resp
        # if error, fall-through to HTML
    except Exception as e:
        html = f"""<div style='padding:16px;background:#fff3cd;border:1px solid #ffeeba'>
        <strong>PDF generator not available.</strong><br>
        Install with: <code>pip install xhtml2pdf</code>.<br>
        Error: {e}
        </div>""" + html

    return HttpResponse(html)


from django.views.generic import DetailView, UpdateView
from django.urls import reverse
from .models import Cargo
from .forms import CargoForm

class CargoDetailView(DetailView):
    model = Cargo
    template_name = 'sales/cargo_detail.html'
    context_object_name = 'cargo'

class CargoUpdateView(UpdateView):
    model = Cargo
    form_class = CargoForm
    template_name = 'sales/cargo_detail.html'

    def get_success_url(self):
        return reverse('sales:cargo_detail', args=[self.object.pk])


from django.shortcuts import get_object_or_404
from django.contrib import messages
from .models import Cargo, CargoCharge
from .forms import ChargeFormSetFactory

def cargo_charges_edit(request, cargo_id: int):
    cargo = get_object_or_404(Cargo.objects.select_related('quotation'), pk=cargo_id)
    CFSF = ChargeFormSetFactory()
    if request.method == 'POST':
        formset = CFSF(request.POST, instance=cargo, prefix='chg')
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Charges updated.')
            return redirect('sales:cargo_charges_edit', cargo_id=cargo.pk)
    else:
        formset = CFSF(instance=cargo, prefix='chg')
    return render(request, 'sales/cargo_charges_edit.html', {
        'cargo': cargo,
        'quotation': cargo.quotation,
        'formset': formset,
    })

from django.views.generic import UpdateView
class ChargeUpdateView(UpdateView):
    model = CargoCharge
    fields = ['charge_type','description','unit','qty','rate','currency']
    template_name = 'sales/cargo_charges_edit.html'
    context_object_name = 'charge'
    def get_success_url(self):
        return self.request.GET.get('next') or self.object.cargo and self.object.cargo.get_absolute_url() or '/'  



from django.shortcuts import render, redirect
from django.urls import reverse

def quotation_wizard_start(request):
    """Step 0: pilih transport mode, service type, multi-destination.
    Hasilnya diteruskan via querystring ke /wizard/new/.
    """
    if request.method == "POST":
        mode = request.POST.get("mode", "MULTI").upper()
        multi = request.POST.get("multi_destination") in ("on","true","1","True")
        # Land -> service fixed 'TRUCKING'; Multi -> service kosong
        if mode == "LAND":
            service = "TRUCKING"
        else:
            service = request.POST.get("service_option","").upper()

        # Redirect ke wizard new dengan parameter
        url = reverse("sales:quotation_wizard")
        # multi sebagai 1/0
        params = f"?mode={mode}&multi={'1' if multi else '0'}&service={service}"
        return redirect(url + params)

    return render(request, "sales/quotation_wizard_start.html", {})


from django.shortcuts import render, redirect
from django.urls import reverse

def quotation_wizard_v3_start(request):
    """Step 0 (V3): Pilih mode, service, multi-destination. Hasilnya diteruskan via querystring ke /wizard/v3/"""
    if request.method == "POST":
        mode = (request.POST.get("mode") or "MULTI").upper()
        multi = request.POST.get("multi_destination") in ("on","true","1","True")
        if mode == "LAND":
            service = "TRUCKING"
        else:
            service = (request.POST.get("service_option") or "").upper()

        url = reverse("sales:quotation_wizard_v3")
        params = f"?mode={mode}&multi={'1' if multi else '0'}&service={service}"
        return redirect(url + params)
    return render(request, "sales/quotation_wizard_v3_start.html", {})

def quotation_wizard_v3(request):
    """
    Step 1 (V3): Header + Cargo.
    - SELALU pasang CargoFormSet(instance=quotation) baik GET maupun POST
    - Enforce single-destination: jika multi_destination=False, setiap cargo.destination = destination_header
    """
    # Import lokal agar tidak ganggu import order
    from .forms import QuotationForm, CargoFormSet
    from .models import Quotation

    # Baca preset dari Step 0 (querystring)
    preset_mode = (request.GET.get('mode') or '').upper() or None
    preset_service = (request.GET.get('service') or '').upper() or None
    preset_multi = request.GET.get('multi')
    if preset_multi is not None:
        preset_multi = True if str(preset_multi) in ('1','true','True','on') else False

    if request.method == "POST":
        ## LOCK_STEP1_FIELDS: override POST from Step 0 presets
        preset_mode = (request.GET.get('mode') or '').upper() or None
        preset_service = (request.GET.get('service') or '').upper() or None
        preset_multi = request.GET.get('multi')
        if preset_multi is not None:
            preset_multi = True if str(preset_multi) in ('1','true','True','on') else False
        _post = request.POST.copy()
        if preset_mode:
            _post['transport_mode'] = preset_mode
        if preset_service is not None:
            _post['service_option'] = preset_service
        if preset_multi is not None:
            _post['multi_destination'] = 'on' if preset_multi else ''
        header_form = QuotationForm(_post)
        # Buat instance quotation (unsaved) untuk dipasang ke formset
        if header_form.is_valid():
            quotation = header_form.save(commit=False)
        else:
            quotation = Quotation()  # fallback supaya formset tetap punya parent
        cargo_formset = CargoFormSet(request.POST, prefix="cg", instance=quotation)

        if header_form.is_valid() and cargo_formset.is_valid():
            # Enforce single destination
            is_multi = header_form.cleaned_data.get("multi_destination", True)
            if not is_multi:
                dest_origin = header_form.cleaned_data.get('origin_header')
                dest_header = header_form.cleaned_data.get('destination_header')
                dest_head = header_form.cleaned_data.get("destination_header")
                for f in cargo_formset.forms:
                    if getattr(f, "cleaned_data", None) and not f.cleaned_data.get("DELETE", False):
                        f.instance.destination = dest_head

            # Simpan header lalu lines
            quotation.save()
            cargo_formset.instance = quotation
            cargo_formset.save()

            from django.shortcuts import redirect
            return redirect("sales:quotation_detail", pk=quotation.pk)

        # Jika tidak valid, render kembali dengan error
        return render(request, "sales/quotation_wizard_v3.html", {
            "header_form": header_form,
            "cargo_formset": cargo_formset,
            "preset_mode": preset_mode,
            "preset_service": preset_service,
            "preset_multi": preset_multi,
        })

    else:
        # GET: siapkan form header & formset dengan parent dummy (unsaved)
        header_form = QuotationForm()
        # Apply preset ke initial
        if preset_mode:
            header_form.fields.get("transport_mode").initial = preset_mode
        if preset_service is not None and "service_option" in header_form.fields:
            header_form.fields["service_option"].initial = preset_service
        if preset_multi is not None and "multi_destination" in header_form.fields:
            header_form.fields["multi_destination"].initial = preset_multi

        quotation = Quotation()  # parent dummy untuk inline formset
        cargo_formset = CargoFormSet(prefix="cg", instance=quotation)

        return render(request, "sales/quotation_wizard_v3.html", {
            "header_form": header_form,
            "cargo_formset": cargo_formset,
            "preset_mode": preset_mode,
            "preset_service": preset_service,
            "preset_multi": preset_multi,
        })
