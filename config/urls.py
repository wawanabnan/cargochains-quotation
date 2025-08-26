from django.views.generic.base import RedirectView
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='sales:quotation_list', permanent=False)),

    path('admin/', admin.site.urls),
    path('api/', include('sales.api.urls')),
    path('sales/', include(('sales.urls','sales'), namespace='sales'))
]
