from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, Cargo, CargoCharge, CharterLeg, CharterCharge

class QuotationFreightForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["date","validity_date","customer","currency",
                  "transport_mode","service_option","multi_destination",
                  "origin","destination","notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type":"date"}),
            "validity_date": forms.DateInput(attrs={"type":"date"}),
            "notes": forms.Textarea(attrs={"rows":2}),
        }

class QuotationCharterForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["date","validity_date","customer","currency",
                  "charter_type","vessel_name","vessel_type","dwt_mt",
                  "laycan_start","laycan_end","laytime_allowed_hours","reversible_laytime",
                  "demurrage_usd_per_day","despatch_usd_per_day","bunker_terms","notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type":"date"}),
            "validity_date": forms.DateInput(attrs={"type":"date"}),
            "laycan_start": forms.DateInput(attrs={"type":"date"}),
            "laycan_end": forms.DateInput(attrs={"type":"date"}),
            "notes": forms.Textarea(attrs={"rows":2}),
        }

class BaseCargoChargeFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if self.can_delete and form.cleaned_data.get("DELETE"):
                continue
            desc = (form.cleaned_data.get("description") or "").strip().lower()
            if not desc:
                continue
            if desc in seen:
                raise forms.ValidationError("Duplicate charge description on the same cargo.")
            seen.add(desc)

CargoFormSet = inlineformset_factory(
    Quotation, Cargo,
    fields=["description","origin","destination","qty","weight_kg","volume_cbm"],
    extra=1, can_delete=True
)

CargoChargeFormSet = inlineformset_factory(
    Cargo, CargoCharge,
    fields=["description","qty","rate"],
    extra=1, can_delete=True,
    formset=BaseCargoChargeFormSet
)

LegFormSet = inlineformset_factory(
    Quotation, CharterLeg,
    fields=["order","kind","port","terminal","remarks"],
    extra=1, can_delete=True
)

CharterChargeFormSet = inlineformset_factory(
    Quotation, CharterCharge,
    fields=["description","qty","rate"],
    extra=1, can_delete=True
)
