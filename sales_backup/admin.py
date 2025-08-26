from django.contrib import admin
from .models import Quotation, Cargo, CargoCharge, CharterLeg, CharterCharge
@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("number","date","customer","business_type","currency")
    search_fields = ("number","customer__name")
    list_filter = ("business_type","currency")
admin.site.register(Cargo)
admin.site.register(CargoCharge)
admin.site.register(CharterLeg)
admin.site.register(CharterCharge)
