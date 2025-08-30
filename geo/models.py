from django.db import models

class Location(models.Model):
    CITY = "CITY"
    SEAPORT = "SEAPORT"
    AIRPORT = "AIRPORT"
    JETTY = "JETTY"
    TYPE_CHOICES = [
        (CITY, "City"),
        (SEAPORT, "Sea Port"),
        (AIRPORT, "Airport"),
        (JETTY, "Jetty"),
    ]
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, blank=True)      # IATA / UN/Locode / internal code
    country = models.CharField(max_length=2, blank=True)    # ISO (ID, SG, ...)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

    class Meta:
        ordering = ["type", "name"]
        unique_together = [("code", "type")]

    def __str__(self):
        suf = f" - {self.code}" if self.code else ""
        return f"{self.name} ({self.type}){suf}"
