from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.conf import settings
from django.apps import apps
from pathlib import Path

from core.pdf_service import html_to_pdf_bytes

# Ambil model tanpa import langsung agar aman terhadap urutan load
FreightQuotation = apps.get_model("sales", "FreightQuotation")

class Command(BaseCommand):
    help = "Generate ALL Freight Quotation PDFs ke MEDIA_ROOT/quotations_pdf/ (tanpa menyentuh field model)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            default="http://127.0.0.1:8000/",
            help="Base URL untuk resolve static (default: http://127.0.0.1:8000/)",
        )

    def handle(self, *args, **opts):
        base_url = opts["domain"].rstrip("/") + "/"

        # Pastikan output dir ada
        media_root = Path(getattr(settings, "MEDIA_ROOT", "."))
        out_dir = media_root / "quotations_pdf"
        out_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        for q in FreightQuotation.objects.all():
            # Siapkan context minimal – sesuaikan dengan template Anda bila perlu
            subtotal = getattr(q, "subtotal", 0) or 0
            vat = getattr(q, "vat_amount", 0) or 0
            grand_total = getattr(q, "grand_total", subtotal + vat) or (subtotal + vat)

            ctx = {
                "q": q,
                # Kalau template butuh daftar cargo/charge, tambahkan di sini
                # Misal: "cargo_rows": q.freightcargo_set.all(),
                "subtotal": subtotal,
                "vat": vat,
                "grand_total": grand_total,
            }

            html = render_to_string("sales/freight/pdf.html", ctx)
            pdf_bytes = html_to_pdf_bytes(html, base_url)

            safe_name = (q.number or f"Quotation-{q.pk}").replace("/", "-")
            fname = f"{safe_name}.pdf"
            (out_dir / fname).write_bytes(pdf_bytes)

            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Generated {count} PDFs → {out_dir.resolve()}"
        ))
