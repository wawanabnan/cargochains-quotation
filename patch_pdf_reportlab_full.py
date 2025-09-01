from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

REPORTLAB_IMPORTS = textwrap.dedent(r"""
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
""").strip()

HELPERS = textwrap.dedent(r"""
# ==== PDF helper: wrap & key-value ====
def _wrap_text(c, text, max_width_pt, font_name="Helvetica", font_size=10):
    if text is None:
        text = ""
    words = str(text).split()
    lines, cur = [], ""
    for w in words or [""]:
        trial = (cur + " " + w).strip()
        if c.stringWidth(trial, font_name, font_size) <= max_width_pt:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]

def _kv(c, x, y, key, val, w_key=30*mm, w_val=120*mm, lh=5.0*mm, fs=10):
    c.setFont("Helvetica", fs)
    c.drawString(x, y, f"{key}")
    # value wrap
    lines = _wrap_text(c, val, w_val, "Helvetica", fs)
    c.setFont("Helvetica-Bold", fs)
    c.drawString(x + w_key, y, lines[0])
    y -= lh
    c.setFont("Helvetica", fs)
    for ln in lines[1:]:
        c.drawString(x + w_key, y, ln)
        y -= lh
    return y

def _ensure_page_space(c, y, needed, margin_bottom=18*mm, newpage_cb=None):
    if y - needed < margin_bottom:
        c.showPage()
        if callable(newpage_cb):
            newpage_cb()
        return True, (A4[1] - 18*mm)
    return False, y

def _draw_table_header(c, x, y, cols, fs=9):
    c.setFillColor(colors.whitesmoke)
    c.rect(x, y-5, sum(w for _,w,_ in cols), 16, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", fs)
    cx = x
    for title, width, align in cols:
        if align == "R":
            c.drawRightString(cx + width - 2, y+6, title)
        elif align == "C":
            c.drawCentredString(cx + width/2, y+6, title)
        else:
            c.drawString(cx + 2, y+6, title)
        cx += width
    c.line(x, y-5, x + sum(w for _,w,_ in cols), y-5)

def _draw_table_row(c, x, y, cols, values, fs=9, lh=12):
    c.setFont("Helvetica", fs)
    cx = x
    for i, (title, width, align) in enumerate(cols):
        val = values[i]
        if align == "R":
            c.drawRightString(cx + width - 2, y, val)
        elif align == "C":
            c.drawCentredString(cx + width/2, y, val)
        else:
            c.drawString(cx + 2, y, val)
        cx += width
    return y - lh
""").strip()

PDF_FUNC = textwrap.dedent(r"""
def freight_pdf(request, pk: int):
    # Ambil data + relasi secukupnya
    q = get_object_or_404(
        FreightQuotation.objects.select_related("customer").prefetch_related(
            Prefetch("cargos", queryset=FreightCargo.objects.prefetch_related("charges"))
        ),
        pk=pk
    )
    # pakai helper total yang sudah ada di views
    cargo_rows, subtotal, vat, grand_total = _compute_totals(q)

    # === PDF canvas ===
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin_x = 15*mm
    y = H - 18*mm

    def header_new_page():
        nonlocal c, margin_x, y
        y = H - 18*mm
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin_x, y, f"Quotation / {q.number or q.id}")
        c.setFont("Helvetica", 9)
        c.drawRightString(W - margin_x, y, f"Date: {q.date}")
        y -= 8*mm
        c.line(margin_x, y, W - margin_x, y)
        y -= 3*mm

    # Header halaman pertama
    header_new_page()

    # Meta informasi
    y = _kv(c, margin_x, y, "Customer", f"{q.customer}")
    y = _kv(c, margin_x, y, "Currency", f"{q.currency}")
    y = _kv(c, margin_x, y, "Payment", f"{q.payment_term or '-'}")
    y = _kv(c, margin_x, y, "Freight", f"{q.get_transport_mode_display()} / {q.get_service_option_display()}")
    if q.notes:
        y = _kv(c, margin_x, y, "Notes", q.notes)

    y -= 3*mm
    c.line(margin_x, y, W - margin_x, y)
    y -= 6*mm

    # Tabel Cargo
    cols = [
        ("#",    10*mm, "C"),
        ("Description", 80*mm, "L"),
        ("Qty",  18*mm, "R"),
        ("Weight", 22*mm, "R"),
        ("Volume", 22*mm, "R"),
        ("Price",  25*mm, "R"),
        ("Amount", 28*mm, "R"),
    ]

    def draw_table_header():
        nonlocal y
        _draw_table_header(c, margin_x, y, cols, fs=9)
        y -= 12

    # Pastikan ada ruang untuk header tabel
    need = 30*mm
    new, y = _ensure_page_space(c, y, need, newpage_cb=header_new_page)
    draw_table_header()

    # Isi baris cargo + charges ringkas
    idx = 1
    for row in cargo_rows:
        desc = row["obj"].description or "(no description)"
        # baris cargo
        line_vals = [
            str(idx),
            desc[:80],
            str(row["obj"].qty or ""),
            f'{(row["obj"].weight_kg or 0):,.2f}',
            f'{(row["obj"].volume_cbm or 0):,.3f}',
            f'{(row["obj"].price or 0):,.2f}',
            f'{(row["obj"].amount or 0):,.2f}',
        ]
        # cek ruang
        need = 12
        if row.get("charges"):
            need += (len(row["charges"]) + 2) * 11
        new, y = _ensure_page_space(c, y, need, newpage_cb=lambda: (header_new_page(), draw_table_header()))
        y = _draw_table_row(c, margin_x, y, cols, line_vals, fs=9, lh=12)

        # charges (indented)
        charges = row.get("charges") or []
        if charges:
            c.setFont("Helvetica-Oblique", 9)
            c.drawString(margin_x+12*mm, y+2, "Charges:")
            y -= 10
            for ch in charges:
                # desc, qty, rate, amount
                c.setFont("Helvetica", 9)
                c.drawString(margin_x+16*mm, y, f"- {ch.description}")
                c.drawRightString(margin_x + 145*mm, y, str(ch.qty or ""))
                c.drawRightString(margin_x + 170*mm, y, f"{(ch.rate or 0):,.2f}")
                c.drawRightString(margin_x + 195*mm, y, f"{(ch.amount or 0):,.2f}")
                y -= 11
            # line total
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(margin_x + 180*mm, y, "Line Total:")
            c.drawRightString(margin_x + 195*mm, y, f'{(row["line_total"] or 0):,.2f}')
            y -= 12

        idx += 1

    # Totals
    need = 30
    new, y = _ensure_page_space(c, y, need, newpage_cb=header_new_page)
    c.line(margin_x, y, W - margin_x, y); y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(margin_x + 180*mm, y, "Subtotal:")
    c.drawRightString(margin_x + 195*mm, y, f"{subtotal:,.2f}")
    y -= 12
    c.setFont("Helvetica", 10)
    c.drawRightString(margin_x + 180*mm, y, "VAT:")
    c.drawRightString(margin_x + 195*mm, y, f"{vat:,.2f}")
    y -= 12
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(margin_x + 180*mm, y, "Grand Total:")
    c.drawRightString(margin_x + 195*mm, y, f"{grand_total:,.2f}")
    y -= 8

    # Footer sederhana
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawRightString(W - margin_x, 10*mm, f"Generated on {datetime.date.today().isoformat()}")
    c.setFillColor(colors.black)

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()

    filename = f"{q.number or f'Quotation-{q.id}'}.pdf"
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
""").strip()

def backup(fp: Path):
    if fp.exists():
        bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
        shutil.copy2(fp, bak)
        print(f"[backup] {fp} -> {bak.name}")

def ensure_imports(src: str) -> str:
    need = [
        ("from django.http import HttpResponse", r"\bHttpResponse\b"),
        ("from django.shortcuts import get_object_or_404", r"\bget_object_or_404\b"),
        ("from django.db.models import Prefetch", r"\bPrefetch\b"),
        ("import datetime", r"\bdatetime\b"),
    ]
    for line, token in need:
        if not re.search(token, src):
            if line not in src:
                src = line + "\n" + src
    # ReportLab imports
    if "reportlab.pdfgen" not in src or "from io import BytesIO" not in src:
        src = REPORTLAB_IMPORTS + "\n" + src
        if "from io import BytesIO" not in src:
            src = "from io import BytesIO\n" + src
    return src

def inject_helpers(src: str) -> str:
    if "_wrap_text(c, text" not in src:
        # sisipkan helpers setelah import
        parts = src.split("\n", 30)
        head = "\n".join(parts[:30])
        tail = "\n".join(parts[30:])
        src = head + "\n\n" + HELPERS + "\n\n" + tail
        print("[add]   PDF helpers injected")
    return src

def replace_pdf_func(src: str) -> str:
    pat = re.compile(r"\ndef\s+freight_pdf\s*\(request\s*,\s*pk\s*:\s*int\)\s*:[\s\S]*?(?=\n\ndef\s+|\Z)", re.M)
    if pat.search(src):
        src = pat.sub("\n\n" + PDF_FUNC + "\n\n", src)
        print("[edit] Replaced existing freight_pdf()")
    else:
        src += "\n\n" + PDF_FUNC + "\n"
        print("[add]  Added freight_pdf()")
    return src

def strip_html_pdf_imports(src: str) -> str:
    # bersihkan weasyprint/xhtml2pdf biar tak konflik
    src = re.sub(r"^.*from\s+weasyprint\s+import\s+.*?$", "", src, flags=re.M)
    src = re.sub(r"^.*from\s+xhtml2pdf\s+import\s+.*?$", "", src, flags=re.M)
    return src

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")
    src = strip_html_pdf_imports(src)
    src = ensure_imports(src)
    src = inject_helpers(src)
    src = replace_pdf_func(src)
    src = re.sub(r"\n{3,}", "\n\n", src)
    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] Patched sales/views.py with ReportLab PDF (professional table)")

    print("\n✅ Selesai. Coba buka /sales/quotations/freight/<id>/pdf/")
    print("Jika belum tampil, lihat console server untuk memastikan fungsi freight_pdf baru dipanggil.")
if __name__ == "__main__":
    main()
