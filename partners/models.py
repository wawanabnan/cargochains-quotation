from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

from django.db import models

class Partner(models.Model):
    name        = models.CharField(max_length=200, unique=True)
    address     = models.TextField(blank=True)
    phone       = models.CharField(max_length=50, blank=True)
    email       = models.EmailField(blank=True)

    # multi-role flags
    is_customer = models.BooleanField(default=False)
    is_vendor   = models.BooleanField(default=False)
    is_agent    = models.BooleanField(default=False)

    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# Proxy managers
class CustomerManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_customer=True, is_active=True)

class VendorManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_vendor=True, is_active=True)

class AgentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_agent=True, is_active=True)


# Proxy models (aman: nama berbeda dari model konkret lama)
class CustomerProxy(Partner):
    objects = CustomerManager()
    class Meta:
        proxy = True
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

class VendorProxy(Partner):
    objects = VendorManager()
    class Meta:
        proxy = True
        verbose_name = "Vendor"
        verbose_name_plural = "Vendors"

class AgentProxy(Partner):
    objects = AgentManager()
    class Meta:
        proxy = True
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
