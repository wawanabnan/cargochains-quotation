from datetime import date, timedelta
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Quotation, Cargo, CargoCharge

# ---- Header (Quotation) ----
class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["date","customer","validity_date","payment_terms","notes", 'transport_mode', 'service_option', 'multi_destination', 'destination_header', 'origin_header']
        widgets = {
            'origin_header': forms.TextInput(attrs={'class':'form-control','id':'id_origin_header'}), 'transport_mode': forms.Select(attrs={'class':'form-select'}),
            'service_option': forms.Select(attrs={'class':'form-select'}),
            'multi_destination': forms.CheckboxInput(attrs={'class':'form-check-input'}),
            'destination_header': forms.TextInput(attrs={'class':'form-control'}),
            "date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "validity_date": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "customer": forms.Select(attrs={"class":"form-select"}),
            "payment_terms": forms.TextInput(attrs={"class":"form-control"}),
            "notes": forms.Textarea(attrs={"class":"form-control","rows":3}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["date"].initial = date.today()
            self.fields["validity_date"].initial = date.today() + timedelta(days=14)


# ---- Cargo FormSet (min 1 cargo) ----
class _CargoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = [
            f for f in self.forms
            if not f.cleaned_data.get("DELETE", False)
            and any(
                f.cleaned_data.get(k)
                for k in ["description","origin","destination","qty","weight_kg","volume_cbm","package_type"]
            )
        ]
        if len(active) < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal harus ada 1 cargo di quotation ini.")

CargoFormSet = inlineformset_factory(
    Quotation, Cargo,
    formset=_CargoFormSet,
    fields=["description", "package_type", "qty", "weight_kg", "volume_cbm", "origin", "destination", "extra_notes"],
    extra=1, can_delete=True
)

# ---- Charge FormSet (min 1 charge per cargo) ----
class _ChargeFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        active = 0
        for f in self.forms:
            if f.cleaned_data.get("DELETE", False):
                continue
            if any(f.cleaned_data.get(k) for k in ["charge_type","description","unit","qty","rate","currency"]):
                active += 1
        if active < 1:
            from django.core.exceptions import ValidationError
            raise ValidationError("Minimal 1 charge untuk setiap cargo.")

ChargeFormSet = inlineformset_factory(
    Cargo, CargoCharge,
    formset=_ChargeFormSet,
    fields=["description", "unit", "qty", "rate", 'description'],
    extra=3, can_delete=True
)

def ChargeFormSetFactory():
    return inlineformset_factory(
        Cargo, CargoCharge,
        formset=_ChargeFormSet,
        fields=["description", "unit", "qty", "rate", 'description'],
        extra=1, can_delete=True
    )


# ---- Single Cargo Form (detail/edit) ----
class CargoForm(forms.ModelForm):
    class Meta:
        model = Cargo
        fields = [
            'description','package_type','qty','weight_kg','volume_cbm',
            'origin','destination','shipper','consignee','notify_party','extra_notes'
        ]
        widgets = {
            'description': forms.TextInput(attrs={'class':'form-control'}),
            'package_type': forms.TextInput(attrs={'class':'form-control'}),
            'qty': forms.NumberInput(attrs={'class':'form-control','step':'0.001'}),
            'weight_kg': forms.NumberInput(attrs={'class':'form-control','step':'0.001'}),
            'volume_cbm': forms.NumberInput(attrs={'class':'form-control','step':'0.001'}),
            'origin': forms.TextInput(attrs={'class':'form-control'}),
            'destination': forms.TextInput(attrs={'class':'form-control'}),
            'shipper': forms.TextInput(attrs={'class':'form-control'}),
            'consignee': forms.TextInput(attrs={'class':'form-control'}),
            'notify_party': forms.TextInput(attrs={'class':'form-control'}),
            'extra_notes': forms.Textarea(attrs={'class':'form-control','rows':3}),
        }


    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('transport_mode') or 'SEA'
        multi_dest = cleaned.get('multi_destination')
        service = cleaned.get('service_option') or ''
        dest_head = cleaned.get('destination_header') or ''

        # Mapping service option per mode (server-side)
        SERVICE_BY_MODE = {
            'SEA': ['D2D', 'D2P', 'P2P'],      # Door-to-Door, Door-to-Port, Port-to-Port
            'AIR': ['A2A', 'D2A'],             # Airport-to-Airport, Door-to-Airport
            'LAND': ['D2D', 'H2H'],            # Door-to-Door, Hub-to-Hub (opsional)
            'MULTI': [],                       # bebas, tidak wajib
        }

        if mode != 'MULTI':
            # service option wajib & harus valid
            if not service:
                from django.core.exceptions import ValidationError
                raise ValidationError({'service_option': 'Service option wajib untuk mode selain MULTI.'})
            if service not in SERVICE_BY_MODE.get(mode, []):
                from django.core.exceptions import ValidationError
                raise ValidationError({'service_option': f'Service option tidak valid untuk mode {mode}.'})

        # single destination → destination header wajib
        if not multi_dest and not dest_head:
            from django.core.exceptions import ValidationError
            raise ValidationError({'destination_header': 'Destination (header) wajib jika single destination.'})

        return cleaned
