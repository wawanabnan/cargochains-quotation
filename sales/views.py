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
