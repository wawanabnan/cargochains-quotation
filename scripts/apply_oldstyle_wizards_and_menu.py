# apply_oldstyle_wizards_and_menu.py
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP = ROOT / "sales"
VIEWS = APP / "views.py"
URLS = APP / "urls.py"
TPLDIR = APP / "templates" / "sales"
TPL_LIST = TPLDIR / "quotation_list.html"
TEMPLATE_OLD = TPLDIR / "quotation_wizard.html"  # diasumsikan sudah ada di projectmu

def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak")
        if not b.exists():
            b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"• backup -> {b}")

# ---------- Patch views.py: add/override wizards that use old template ----------
def patch_views():
    assert VIEWS.exists(), f"{VIEWS} tidak ditemukan"
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")

    # Pastikan imports yang dibutuhkan ada
    needed = [
        "from django.shortcuts import render, redirect, get_object_or_404",
        "from django.urls import reverse",
        "from django.core.paginator import Paginator",
        "from django.db import transaction",
        "from django.http import HttpResponseServerError",
        "from .models import Quotation, Cargo",
        "from .forms import (QuotationFreightForm, CargoFormSet, CargoChargeFormSet, QuotationCharterForm, LegFormSet, CharterChargeFormSet)",
    ]
    for imp in needed:
        if imp not in src:
            src = imp + "\n" + src

    # Tambahkan/override wizard cargo (2 step, pakai template lama)
    freight_block = r"""
# ===== Old-style Freight Wizard (Step 1 header -> Step 2 cargo) =====
WIZ_FREIGHT_KEY = "wiz_freight_header"

def freight_wizard_new(request):
    try:
        step = int(request.GET.get("step", "1"))
        template = "sales/quotation_wizard.html"

        # STEP 1: HEADER (ke session)
        if step == 1:
            if request.method == "POST":
                qform = QuotationFreightForm(request.POST)
                if qform.is_valid():
                    request.session[WIZ_FREIGHT_KEY] = qform.cleaned_data
                    request.session.modified = True
                    return redirect(reverse("sales:freight_wizard_new") + "?step=2")
                return render(request, template, {"step": 1, "mode": "FREIGHT", "qform": qform, "fs": None})
            else:
                initial = request.session.get(WIZ_FREIGHT_KEY, {"business_type": "FREIGHT"})
                qform = QuotationFreightForm(initial=initial)
                return render(request, template, {"step": 1, "mode": "FREIGHT", "qform": qform, "fs": None})

        # STEP 2: CARGO LINES (commit DB)
        elif step == 2:
            header_data = request.session.get(WIZ_FREIGHT_KEY)
            if not header_data:
                return redirect(reverse("sales:freight_wizard_new") + "?step=1")

            if request.method == "POST":
                if request.POST.get("_action") == "back":
                    return redirect(reverse("sales:freight_wizard_new") + "?step=1")
                fs = CargoFormSet(request.POST, prefix="cargo")

                def has_valid_line(formset):
                    total = 0
                    for f in formset:
                        if f.cleaned_data.get("DELETE"):
                            continue
                        if f.cleaned_data.get("description"):
                            total += 1
                    return total > 0

                if fs.is_valid() and has_valid_line(fs):
                    with transaction.atomic():
                        qform = QuotationFreightForm(header_data)
                        if not qform.is_valid():
                            return redirect(reverse("sales:freight_wizard_new") + "?step=1")
                        q = qform.save(commit=False)
                        q.business_type = "FREIGHT"
                        q.save()

                        fs.instance = q
                        fs.save()

                        if WIZ_FREIGHT_KEY in request.session:
                            del request.session[WIZ_FREIGHT_KEY]
                    return redirect("sales:quotation_detail", pk=q.pk)

                # invalid -> render ulang
                return render(request, template, {"step": 2, "mode": "FREIGHT",
                                                  "qform": QuotationFreightForm(initial=header_data),
                                                  "fs": fs})

            # GET step 2
            fs = CargoFormSet(prefix="cargo")
            return render(request, template, {"step": 2, "mode": "FREIGHT",
                                              "qform": QuotationFreightForm(initial=header_data),
                                              "fs": fs})

        # fallback
        return redirect(reverse("sales:freight_wizard_new") + "?step=1")
    except Exception as e:
        return HttpResponseServerError(f"freight_wizard_new error: {e}")
"""
    # Tambahkan/override wizard charter (2 step, pakai template lama)
    charter_block = r"""
# ===== Old-style Charter Wizard (Step 1 header -> Step 2 legs/charges) =====
WIZ_CHARTER_KEY = "wiz_charter_header"

def charter_wizard_new(request):
    try:
        # ctype: VOYAGE / TIME
        ctype = (request.GET.get("ctype") or request.POST.get("ctype") or "VOYAGE").upper()
        step = int(request.GET.get("step", "1"))
        template = "sales/quotation_wizard.html"

        # STEP 1: HEADER (ke session)
        if step == 1:
            if request.method == "POST":
                # inject charter_type ke POST agar form bisa valid
                mutable = request.POST._mutable if hasattr(request.POST, "_mutable") else None
                try:
                    request.POST._mutable = True
                except Exception:
                    pass
                request.POST["charter_type"] = ctype
                if mutable is not None:
                    try:
                        request.POST._mutable = mutable
                    except Exception:
                        pass

                qform = QuotationCharterForm(request.POST, charter_type=ctype)
                if qform.is_valid():
                    data = qform.cleaned_data
                    data["charter_type"] = ctype
                    request.session[WIZ_CHARTER_KEY] = data
                    request.session.modified = True
                    return redirect(reverse("sales:charter_wizard_new") + f"?step=2&ctype={ctype}")
                return render(request, template, {"step": 1, "mode": "CHARTER", "ctype": ctype, "qform": qform, "fs": None})
            else:
                initial = request.session.get(WIZ_CHARTER_KEY, {"business_type": "SHIP_CHARTER", "charter_type": ctype})
                qform = QuotationCharterForm(initial=initial, charter_type=ctype)
                return render(request, template, {"step": 1, "mode": "CHARTER", "ctype": ctype, "qform": qform, "fs": None})

        # STEP 2: LINES (VOYAGE -> legs [+ charges]; TIME -> langsung commit)
        elif step == 2:
            header_data = request.session.get(WIZ_CHARTER_KEY)
            if not header_data:
                return redirect(reverse("sales:charter_wizard_new") + f"?step=1&ctype={ctype}")

            if request.method == "POST":
                if request.POST.get("_action") == "back":
                    return redirect(reverse("sales:charter_wizard_new") + f"?step=1&ctype={ctype}")

                with transaction.atomic():
                    # build header again from session
                    qform = QuotationCharterForm(header_data, charter_type=ctype)
                    if not qform.is_valid():
                        return redirect(reverse("sales:charter_wizard_new") + f"?step=1&ctype={ctype}")
                    q = qform.save(commit=False)
                    q.business_type = "SHIP_CHARTER"
                    q.charter_type = ctype
                    q.save()

                    if ctype == "VOYAGE":
                        legfs = LegFormSet(request.POST, instance=q, prefix="legs")
                        chgfs = CharterChargeFormSet(request.POST, instance=q, prefix="chg")

                        def has_leg(fs):
                            tot = 0
                            for f in fs:
                                if f.cleaned_data.get("DELETE"):
                                    continue
                                if f.cleaned_data.get("port"):
                                    tot += 1
                            return tot > 0

                        if legfs.is_valid() and has_leg(legfs) and chgfs.is_valid():
                            legfs.save()
                            chgfs.save()
                        else:
                            # rollback header agar tidak orphan
                            q.delete()
                            # render ulang
                            return render(request, template, {
                                "step": 2, "mode": "CHARTER", "ctype": ctype,
                                "qform": QuotationCharterForm(initial=header_data, charter_type=ctype),
                                "fs": legfs, "legfs": legfs, "chgfs": chgfs
                            })

                    # clear session & done
                    if WIZ_CHARTER_KEY in request.session:
                        del request.session[WIZ_CHARTER_KEY]
                return redirect("sales:quotation_detail", pk=q.pk)

            # GET step 2
            if ctype == "VOYAGE":
                legfs = LegFormSet(prefix="legs")
                chgfs = CharterChargeFormSet(prefix="chg")
                return render(request, template, {
                    "step": 2, "mode": "CHARTER", "ctype": ctype,
                    "qform": QuotationCharterForm(initial=header_data, charter_type=ctype),
                    "fs": legfs, "legfs": legfs, "chgfs": chgfs
                })
            else:
                # TIME: tidak ada lines; tampilkan ringkasan header dan tombol Save
                return render(request, template, {
                    "step": 2, "mode": "CHARTER", "ctype": ctype,
                    "qform": QuotationCharterForm(initial=header_data, charter_type=ctype),
                    "fs": None, "legfs": None, "chgfs": None
                })

        # fallback
        return redirect(reverse("sales:charter_wizard_new") + f"?step=1&ctype={ctype}")
    except Exception as e:
        return HttpResponseServerError(f"charter_wizard_new error: {e}")
"""
    # append/override: cukup tambahkan di akhir (def terakhir yang dipakai)
    # hapus definisi lama (opsional) – kita cukup append agar override by position
    for block, marker in [(freight_block, "def freight_wizard_new("),
                          (charter_block, "def charter_wizard_new(")]:
        if marker in src:
            # tetap append versi baru agar yang terakhir menang
            pass
        src = src.rstrip() + "\n\n" + block + "\n"

    VIEWS.write_text(src, encoding="utf-8")
    print(f"✔ views.py updated: {VIEWS}")

# ---------- Patch urls.py: add alias & new routes ----------
def patch_urls():
    assert URLS.exists(), f"{URLS} tidak ditemukan"
    backup(URLS)
    src = URLS.read_text(encoding="utf-8")

    if "from . import views" not in src:
        src = "from . import views\n" + src

    def ensure_path(name_snippet, line):
        nonlocal src
        if name_snippet not in src:
            # sisipkan ke dalam urlpatterns list
            src = re.sub(r"(urlpatterns\s*=\s*\[\s*)", r"\1    " + line + "\n    ", src, count=1)
            print("✓ route added:", name_snippet)

    ensure_path("freight_wizard_new",
        "path('quotations/wizard/new/', views.freight_wizard_new, name='freight_wizard_new'),")
    # alias lama:
    if "quotation_wizard_new" not in src:
        ensure_path("quotation_wizard_new",
            "path('quotations/wizard/new/', views.freight_wizard_new, name='quotation_wizard_new'),")
    if "quotation_wizard_v3_start" not in src:
        ensure_path("quotation_wizard_v3_start",
            "path('quotations/wizard/v3/start/', views.freight_wizard_new, name='quotation_wizard_v3_start'),")

    # charter wizard (old-style template)
    ensure_path("charter_wizard_new",
        "path('quotations/wizard/charter/', views.charter_wizard_new, name='charter_wizard_new'),")
    # alias step0 lama ke wizard baru
    if "charter_step0" not in src:
        ensure_path("charter_step0",
            "path('charter/quotations/new/', views.charter_wizard_new, name='charter_step0'),")

    URLS.write_text(src, encoding="utf-8")
    print(f"✔ urls.py updated: {URLS}")

# ---------- Patch quotation_list.html: single New button + dropdown ----------
def patch_list_template():
    if not TPL_LIST.exists():
        print(f"• {TPL_LIST} tidak ditemukan, skip patch tombol menu")
        return

    backup(TPL_LIST)
    html = TPL_LIST.read_text(encoding="utf-8")

    if "id=\"newTypeSelect\"" in html:
        print("• dropdown New Quotation sudah ada — skip")
        return

    toolbar = """
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h3 class="m-0">Quotations</h3>
    <div class="d-flex gap-2">
      <select id="newTypeSelect" class="form-select form-select-sm">
        <option value="FREIGHT">Freight</option>
        <option value="VOYAGE">Ship Charter — Voyage</option>
        <option value="TIME">Ship Charter — Time</option>
      </select>
      <button id="btnNewQuotation" class="btn btn-sm btn-primary">+ New Quotation</button>
    </div>
  </div>
  <script>
  (function(){
    const btn = document.getElementById('btnNewQuotation');
    if(!btn) return;
    btn.addEventListener('click', function(e){
      e.preventDefault();
      const v = document.getElementById('newTypeSelect').value;
      if(v === 'FREIGHT'){
        window.location.href = "{% url 'sales:freight_wizard_new' %}?step=1";
      }else if(v === 'VOYAGE'){
        window.location.href = "{% url 'sales:charter_wizard_new' %}?step=1&ctype=VOYAGE";
      }else{
        window.location.href = "{% url 'sales:charter_wizard_new' %}?step=1&ctype=TIME";
      }
    });
  })();
  </script>
"""
    # sisipkan setelah pembuka container bila ada; kalau tidak, prepend
    new_html = re.sub(r"(<div\s+class=\"container\"[^>]*>)", r"\\1\n" + toolbar, html, count=1, flags=re.I)
    if new_html == html:
        new_html = toolbar + "\n" + html

    TPL_LIST.write_text(new_html, encoding="utf-8")
    print(f"✔ quotation_list.html updated with dropdown button: {TPL_LIST}")

def main():
    # cek template lama ada
    if not TEMPLATE_OLD.exists():
        print(f"⚠️ Peringatan: template lama tidak ditemukan: {TEMPLATE_OLD}")
        print("   Script tetap lanjut, pastikan file itu ada agar wizard tampil dengan styling lama.")
    patch_views()
    patch_urls()
    patch_list_template()
    print("\nDone. Coba akses:")
    print("  /sales/quotations/wizard/new/?step=1          (Freight wizard, old style)")
    print("  /sales/quotations/wizard/charter/?step=1&ctype=VOYAGE  (Charter wizard)")
    print("  /sales/quotations/                              (menu list, ada dropdown New)")

if __name__ == "__main__":
    main()
