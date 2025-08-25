from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
VIEWS = ROOT / "sales" / "views.py"

assert VIEWS.exists(), "Tidak menemukan sales/views.py"

def backup(p: Path):
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"• backup -> {b.name}")

print("== Patch: fix quotation_wizard_v3 to always pass instance to CargoFormSet ==")
backup(VIEWS)
src = VIEWS.read_text(encoding="utf-8")

pattern = re.compile(
    r"def\s+quotation_wizard_v3\s*\([\s\S]*?\):[\s\S]*?(?=\n\ndef\s|\Z)",
    re.MULTILINE
)

new_func = '''
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
        header_form = QuotationForm(request.POST)
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
'''.lstrip()

if pattern.search(src):
    src = pattern.sub(new_func, src, count=1)
    VIEWS.write_text(src, encoding="utf-8")
    print("✓ quotation_wizard_v3 berhasil diperbarui")
else:
    # Jika fungsi tidak ditemukan, tambahkan di akhir file
    with VIEWS.open("a", encoding="utf-8") as f:
        f.write("\n\n" + new_func)
    print("• Tidak menemukan fungsi lama; fungsi v3 ditambahkan di akhir file.")

print("\nSelesai ✅  Coba lagi ke /sales/quotations/wizard/v3/")
