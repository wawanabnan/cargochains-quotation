from pathlib import Path
import re, shutil, datetime, textwrap

ROOT = Path(__file__).resolve().parent
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
VIEWS = ROOT / "sales" / "views.py"

PDF_FUNC = textwrap.dedent(r"""
def freight_pdf(request, pk: int):
    q = get_object_or_404(
        FreightQuotation.objects.select_related("customer").prefetch_related(
            Prefetch("cargos", queryset=FreightCargo.objects.prefetch_related("charges"))
        ),
        pk=pk
    )
    cargo_rows, subtotal, vat, grand_total = _compute_totals(q)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin_x = 15*mm
    y = H - 20*mm

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin_x, y, f"Quotation / {q.number or q.id}")
    c.setFont("Helvetica", 9)
    c.drawRightString(W - margin_x, y, f"Date: {q.date}")
    y -= 10*mm

    c.setFont("Helvetica", 10)
    c.drawString(margin_x, y, f"Customer : {q.customer}")
    y -= 5*mm
    c.drawString(margin_x, y, f"Currency : {q.currency}")
    y -= 5*mm
    c.drawString(margin_x, y, f"Payment  : {q.payment_term or '-'}")
    y -= 5*mm
    c.drawString(margin_x, y, f"Freight  : {q.get_transport_mode_display()} / {q.get_service_option_display()}")
    y -= 5*mm
    if q.notes:
        c.drawString(margin_x, y, f"Notes    : {q.notes}")
        y -= 8*mm
    y -= 5*mm

    # Kolom fix
    cols = [
        ("#", 12*mm, "C"),
        ("Description", 70*mm, "L"),
        ("Qty", 15*mm, "R"),
        ("Weight", 20*mm, "R"),
        ("Volume", 20*mm, "R"),
        ("Price", 25*mm, "R"),
        ("Amount", 28*mm, "R"),
    ]

    def draw_table_header(y):
        c.setFont("Helvetica-Bold", 9)
        cx = margin_x
        for title, width, align in cols:
            if align == "R":
                c.drawRightString(cx + width - 2, y, title)
            elif align == "C":
                c.drawCentredString(cx + width/2, y, title)
            else:
                c.drawString(cx + 2, y, title)
            cx += width
        y -= 4
        c.line(margin_x, y, margin_x + sum(w for _,w,_ in cols), y)
        return y - 10

    def draw_row(y, values, fs=9):
        c.setFont("Helvetica", fs)
        cx = margin_x
        for i, (title, width, align) in enumerate(cols):
            val = values[i]
            if align == "R":
                c.drawRightString(cx + width - 2, y, val)
            elif align == "C":
                c.drawCentredString(cx + width/2, y, val)
            else:
                c.drawString(cx + 2, y, val)
            cx += width
        return y - 12

    # Header tabel
    y = draw_table_header(y)

    # Cargo & Charges
    idx = 1
    for row in cargo_rows:
        desc = row["obj"].description or "(no description)"
        line_vals = [
            str(idx),
            desc[:60],
            str(row["obj"].qty or ""),
            f'{(row["obj"].weight_kg or 0):,.2f}',
            f'{(row["obj"].volume_cbm or 0):,.3f}',
            f'{(row["obj"].price or 0):,.2f}',
            f'{(row["obj"].amount or 0):,.2f}',
        ]
        y = draw_row(y, line_vals)

        # charges
        for ch in row.get("charges", []):
            charge_vals = [
                "",
                f"   - {ch.description}",
                str(ch.qty or ""),
                "",
                "",
                f"{(ch.rate or 0):,.2f}",
                f"{(ch.amount or 0):,.2f}",
            ]
            y = draw_row(y, charge_vals, fs=8)

        # line total
        line_total_vals = [""]*5 + ["Line Total", f"{row['line_total']:,.2f}"]
        # pad ke 7 kolom
        if len(line_total_vals) < len(cols):
            line_total_vals.insert(0, "")
        y = draw_row(y, line_total_vals, fs=9)
        idx += 1

    # Subtotal, VAT, Grand Total
    y -= 5
    c.line(margin_x, y, margin_x + sum(w for _,w,_ in cols), y)
    y -= 14
    totals = [
        [""]*5 + ["Subtotal", f"{subtotal:,.2f}"],
        [""]*5 + ["VAT", f"{vat:,.2f}"],
        [""]*5 + ["Grand Total", f"{grand_total:,.2f}"],
    ]
    for vals in totals:
        if len(vals) < len(cols):
            vals.insert(0, "")
        y = draw_row(y, vals, fs=10)

    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawRightString(W - margin_x, 10*mm, f"Generated {datetime.date.today().isoformat()}")
    c.setFillColor(colors.black)

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    buf.close()

    filename = f"{q.number or f'Quotation-{q.id}'}.pdf"
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp
""").strip()

def backup(fp: Path):
    if fp.exists():
        bak = fp.with_suffix(fp.suffix + f".{STAMP}.bak")
        shutil.copy2(fp, bak)
        print(f"[backup] {fp} -> {bak.name}")

def main():
    if not VIEWS.exists():
        print("[ERR] sales/views.py not found")
        return
    backup(VIEWS)
    src = VIEWS.read_text(encoding="utf-8")
    # hapus definisi freight_pdf lama
    pat = re.compile(r"\ndef\s+freight_pdf\s*\(.*?\):[\s\S]*?(?=\n\ndef\s+|\Z)", re.M)
    src = pat.sub("\n\n" + PDF_FUNC + "\n\n", src)
    VIEWS.write_text(src, encoding="utf-8")
    print("[ok] Patched sales/views.py with fixed layout freight_pdf")
    print("\n✅ Selesai. Coba buka /sales/quotations/freight/<id>/pdf/ lagi")

if __name__ == "__main__":
    main()
