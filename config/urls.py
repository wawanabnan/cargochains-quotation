#from django.views.generic.base import RedirectView
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
 #   path('', include(('account.urls', 'account'), namespace='account')),
   path('admin/', admin.site.urls),
    path('api/', include('sales.api.urls')),
    #path('sales/', include(('sales.urls','sales'), namespace='sales')),
    path("sales/",   include(("sales.urls", "sales"),   namespace="sales")),
   
]
