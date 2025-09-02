from django.urls import path
from django.contrib.auth import views as auth_views
from .views import dashboard_view
from . import views 

app_name = 'account'

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
   # path('dashboard/', dashboard_view, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='account/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='account:login'), name='logout'),  # ← Tambahkan ini
    path("dashboard/", views.dashboard_view, name="dashboard"),
    
]
