from django.contrib import admin
from .models import Partner, CustomerProxy, VendorProxy, AgentProxy

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "is_customer", "is_vendor", "is_agent", "is_active")
    list_filter = ("is_customer","is_vendor","is_agent","is_active")
    search_fields = ("name","email","phone")

@admin.register(CustomerProxy)
class CustomerProxyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_active")
    search_fields = ("name","email","phone")
    def save_model(self, request, obj, form, change):
        obj.is_customer = True
        obj.save()

@admin.register(VendorProxy)
class VendorProxyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_active")
    search_fields = ("name","email","phone")
    def save_model(self, request, obj, form, change):
        obj.is_vendor = True
        obj.save()

@admin.register(AgentProxy)
class AgentProxyAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "is_active")
    search_fields = ("name","email","phone")
    def save_model(self, request, obj, form, change):
        obj.is_agent = True
        obj.save()
