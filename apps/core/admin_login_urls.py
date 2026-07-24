from django.shortcuts import redirect
from django.urls import path, reverse


def admin_login(request):
    if request.user.is_authenticated:
        return redirect("admin:index")
    return redirect(f"{reverse('account_login')}?next={reverse('admin:index')}")


urlpatterns = [path("", admin_login, name="admin-login")]
