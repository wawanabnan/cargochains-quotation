# patch_views_lines.py
from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

def backup(p: Path):
    if p.exists():
        bak = p.with_suffix(p.suffix + f".{STAMP}.bak")
        shutil.copy2(p, bak)
        print(f"[backup] {p} -> {bak.name}")

def ensure_import(src: str, needle: str, line: str) -> str:
    return src if needle in src else (line + "\n" + src)

def replace_lines_block(src: str) -> str:
    """
    Ganti isi blok:
        if step == "lines":
            ...
    dengan versi yang rapi dan konsisten prefix.
    """
    NEW_BLOCK = textwrap.dedent(r"""
        if step == "lines":
            hdr = wiz["header"]
            CargoFS = CargoFormSet
            ChargeFS = ChargeFormSet

            if request.method == "POST":
                cargo_fs = CargoFS(request.POST, prefix="cargo")
                charge_fs = ChargeFS(request.POST, prefix="charge")

                # Filter dropdown lokasi sesuai mode
                mode = (hdr.get("transport_mode") or "SEA").upper()
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
                    # buat quotation header
                    q = FreightQuotation.objects.create(
                        date=datetime.date.fromisoformat(hdr["date"]),
                        customer_id=hdr["customer_id"],
                        currency=hdr.get("currency") or "IDR",
                        payment_term=hdr.get("payment_term") or "",
                        transport_mode=hdr["transport_mode"],
                        service_option=hdr["service_option"],
                        notes=hdr.get("notes") or "",
                        multi_destination=False,
                    )

                    cargos_created = 0
                    for f in cargo_fs:
                        cd = f.cleaned_data or {}
                        # lewati baris kosong
                        if not any(cd.get(k) for k in ("description","qty","weight_kg","volume_cbm","price","amount","origin","destination")):
                            continue
                        qty = cd.get("qty") or 1
                        price = cd.get("price") or 0
                        amount = cd.get("amount") or (qty * price)
                        FreightCargo.objects.create(
                            quotation=q,
                            description=cd.get("description") or "",
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

                    # Charges opsional → attach ke cargo pertama
                    first_cargo = q.cargos.first()
                    if first_cargo:
                        for f in charge_fs:
                            cd = f.cleaned_data or {}
                            if not any(cd.get(k) for k in ("description","qty","rate","amount")):
                                continue
                            qty = cd.get("qty") or 1
                            rate = cd.get("rate") or 0
                            amount = cd.get("amount") or (qty * rate)
                            FreightCharge.objects.create(
                                cargo=first_cargo,
                                description=cd.get("description") or "",
                                qty=qty,
                                rate=rate,
                                amount=amount,
                            )

                    _wiz_clear(request)
                    messages.success(request, f"Freight Quotation {q.number} berhasil dibuat.")
                    return redirect("sales:freight_list")

                # invalid formset
                messages.error(request, "Periksa isian Cargo / Charge.")
                return render(request, "sales/freight/wizard.html", {
                    "step": "lines", "cargo_fs": cargo_fs, "charge_fs": charge_fs
                })

            # GET: tampilkan formset kosong dengan prefix konsisten
            cargo_fs = CargoFS(prefix="cargo")
            charge_fs = ChargeFS(prefix="charge")

            # set queryset lokasi untuk dropdown origin/destination
            mode = (hdr.get("transport_mode") or "SEA").upper()
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
    """).strip("\n")

    # Cari blok if step == "lines": ... berikutnya (sampai return/render berikutnya atau elif/else/end)
    # Pola yang cukup toleran indentasi:
    pat = re.compile(
        r"\n(\s*)if\s+step\s*==\s*[\"']lines[\"']\s*:\s*\n"      # pembuka
        r"[\s\S]*?"                                              # isi lama
        r"(?=\n\1#|"
        r"\n\1elif\s+step\s*==|"
        r"\n\1else\s*:|"
        r"\n\1return\s+render\(|"
        r"\n\1\Z)",                                              # hingga blok sez-level berikutnya
        re.M
    )
    m = pat.search(src)
    if not m:
        # jika tidak ketemu, tambahkan blok baru tepat sebelum fallback render terakhir wizard
        # cari fallback ke header
        anchor = re.search(r"\n\s*#\s*fallback.*\n", src)
        if not anchor:
            # jika anchor tidak ketemu, append di akhir fungsi
            return src + "\n\n" + NEW_BLOCK + "\n"
        insert_at = anchor.start()
        return src[:insert_at] + "\n" + NEW_BLOCK + "\n" + src[insert_at:]
    # re-indent block baru sesuai indent lama
    indent = m.group(1)
    new_indented = "\n".join((indent + line if line.strip() else line) for line in NEW_BLOCK.splitlines())
    return src[:m.start()] + "\n" + new_indented + src[m.end():]

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return

    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")

    # Pastikan import wajib ada
    src = ensure_import(src, "from django.shortcuts import render", "from django.shortcuts import render, redirect, get_object_or_404")
    src = ensure_import(src, "from django.contrib import messages", "from django.contrib import messages")
    src = ensure_import(src, "from django.views.decorators.http", "from django.views.decorators.http import require_http_methods, require_GET")
    src = ensure_import(src, "from django.http import JsonResponse", "from django.http import JsonResponse")
    src = ensure_import(src, "import datetime", "import datetime")
    src = ensure_import(src, "from geo.models import Location", "from geo.models import Location")
    src = ensure_import(src, "from .models import FreightQuotation", "from .models import FreightQuotation, FreightCargo, FreightCharge")
    src = ensure_import(src, "from .forms import FreightHeaderForm", "from .forms import FreightHeaderForm, FreightCargoForm, FreightChargeForm, CargoFormSet, ChargeFormSet")

    # Normalisasi tab → spasi
    src = src.replace("\t", "    ")

    # Ganti blok "lines"
    src2 = replace_lines_block(src)

    VIEWS.write_text(src2, encoding="utf-8")
    print("[ok] Patched sales/views.py (step 'lines' fixed with consistent prefixes).")
    print("✅ Selesai. Jalankan ulang server dan coba submit step 'lines'.")

if __name__ == "__main__":
    main()
