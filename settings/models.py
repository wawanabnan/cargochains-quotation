from django.db import models

class Setting(models.Model):
    """
    General settings / konfigurasi aplikasi.
    Contoh key: QUO_PREFIX, QUO_PADDING, QUO_DEFAULT_NOTE, dsb.
    """

    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "settings"   # singular, bukan settings_setting
        verbose_name = "Setting"
        verbose_name_plural = "Settings"

    def __str__(self):
        return f"{self.key} = {self.value}"
