from django.contrib import admin
from .models import Setting

@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description")
    search_fields = ("key", "value")
    #list_editable = ("key", "price", "origin","destination")
    
    
# Register your models here.
