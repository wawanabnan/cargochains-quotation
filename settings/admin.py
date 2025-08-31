from django.contrib import admin
from .models import Setting

@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated_at")
    search_fields = ("key", "value")
from django.contrib import admin

# Register your models here.
