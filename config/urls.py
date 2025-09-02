from django.views.generic.base import RedirectView
from django.contrib import admin
from django.urls import path, include
from account.views import dashboard_view  # root → dashboard


urlpatterns = [
  #  path('', RedirectView.as_view(pattern_name='sales:quotation_list', permanent=False)),
 #   path('', include(('account.urls', 'account'), namespace='account')),
 #   path('admin/', admin.site.urls),
    path('api/', include('sales.api.urls')),
    #path('sales/', include(('sales.urls','sales'), namespace='sales')),
    path("sales/",   include(("sales.urls", "sales"),   namespace="sales")),

    path("account/", include("account.urls", namespace="account")),
      path("", dashboard_view, name="home"),   
]
