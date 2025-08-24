from django.contrib import admin
from .models import Quotation, Cargo, CargoCharge

class CargoChargeInline(admin.TabularInline):
    model = CargoCharge
    extra = 0

class CargoAdmin(admin.ModelAdmin):
    list_display = ("quotation","description","origin","destination","qty","weight_kg","volume_cbm")
    inlines = [CargoChargeInline]

class QuotationAdmin(admin.ModelAdmin):
    list_display = ("number","date","customer","validity_date")
    search_fields = ("number","customer__name")

admin.site.register(Quotation, QuotationAdmin)
admin.site.register(Cargo, CargoAdmin)
