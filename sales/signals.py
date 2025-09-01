# sales/signals.py
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.db import transaction
from django.apps import apps

FreightQuotation = apps.get_model("sales", "FreightQuotation")
# Model detail yang memengaruhi PDF:
FreightCargo = apps.get_model("sales", "FreightCargo")                # <-- ganti dari FreightQuotationLine
FreightCharge = apps.get_model("sales", "FreightCharge")              # sesuaikan jika nama Anda berbeda
# Jika ada model lain yang ikut tampil di PDF, get_model juga di sini.

def _invalidate_after_commit(q_id: int):
    def _do():
        try:
            q = FreightQuotation.objects.get(pk=q_id)
            q.mark_pdf_stale()
        except FreightQuotation.DoesNotExist:
            pass
    transaction.on_commit(_do)

def _invalidate_for_instance(instance):
    # instance bisa header atau child (cargo/charge)
    if isinstance(instance, FreightQuotation):
        _invalidate_after_commit(instance.pk)
    else:
        # Asumsi setiap child punya FK "quotation" (quotation_id)
        if hasattr(instance, "quotation_id") and instance.quotation_id:
            _invalidate_after_commit(instance.quotation_id)

@receiver(post_save, sender=FreightQuotation)
def quotation_saved(sender, instance, **kwargs):
    _invalidate_for_instance(instance)

@receiver(post_delete, sender=FreightQuotation)
def quotation_deleted(sender, instance, **kwargs):
    _invalidate_for_instance(instance)

@receiver(post_save, sender=FreightCargo)        # <-- pakai FreightCargo
def quotation_cargo_saved(sender, instance, **kwargs):
    _invalidate_for_instance(instance)

@receiver(post_delete, sender=FreightCargo)      # <-- pakai FreightCargo
def quotation_cargo_deleted(sender, instance, **kwargs):
    _invalidate_for_instance(instance)

@receiver(post_save, sender=FreightCharge)
def quotation_charge_saved(sender, instance, **kwargs):
    _invalidate_for_instance(instance)

@receiver(post_delete, sender=FreightCharge)
def quotation_charge_deleted(sender, instance, **kwargs):
    _invalidate_for_instance(instance)

# Contoh kalau ada M2M yang pengaruh ke PDF:
# @receiver(m2m_changed, sender=FreightQuotation.tags.through)
# def quotation_m2m_changed(sender, instance, **kwargs):
#     _invalidate_for_instance(instance)
