from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .forms import LoginForm

from django.contrib.auth.decorators import login_required



class UserLoginView(LoginView):
    template_name = 'login.html'
    authentication_form = LoginForm

@login_required
def dashboard_view(request):
    return render(request, 'account/dashboard.html')

def logout_view(request):
    logout(request)
    return redirect('login')
from django.shortcuts import render



# Create your views here.
