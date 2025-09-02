# sales/services.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import FreightQuotation, FreightCargo, FreightOrder, FreightOrderLine

@transaction.atomic
def generate_freight_order_from_quotation(quotation_id: int, *, created_by=None) -> FreightOrder:
    q = (FreightQuotation.objects
         .select_related("customer")
         .prefetch_related("cargos__charges")
         .get(pk=quotation_id))

    # Idempotent: kalau sudah ada order, langsung balikan
    if hasattr(q, "order") and q.order_id:
        return q.order

    # Buat header order
    order = FreightOrder.objects.create(
        date=q.date,
        customer=q.customer,
        currency=q.currency,
        transport_mode=q.transport_mode,
        service_option=q.service_option,
        payment_term=q.payment_term or "",
        notes=q.notes or "",
        quotation=q,
        status="CONFIRMED",   # atau DRAFT jika mau approval manual
        created_by=created_by,
    )

    subtotal = Decimal("0.00")

    # Copy cargo lines (tanpa charges)
    for c in q.cargos.all():
        qty = c.qty or 1
        price = c.price or Decimal("0.00")
        amount = c.amount or (qty * price)
        FreightOrderLine.objects.create(
            order=order,
            description=c.description or "",
            qty=qty,
            price=price,
            amount=amount,
            weight_kg=c.weight_kg,
            volume_cbm=c.volume_cbm,
            origin=c.origin,
            destination=c.destination,
        )
        subtotal += (amount or Decimal("0.00"))

    # VAT: ambil dari quotation kalau mau (opsional)
    vat = q.vat or Decimal("0.00")
    total = subtotal + vat

    order.subtotal = subtotal
    order.vat = vat
    order.total = total
    order.save(update_fields=["subtotal", "vat", "total"])

    # Update status SQ (opsional): CLOSED
    if q.status != "CLOSED":
        q.status = "CLOSED"
        q.save(update_fields=["status"])

    return order
