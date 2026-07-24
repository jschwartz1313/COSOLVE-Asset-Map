from allauth.account.views import LoginView, LogoutView
from django.contrib import admin
from django.urls import include, path

handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"

urlpatterns = [
    path("admin/login/", include("apps.core.admin_login_urls")),
    path("accounts/login/", LoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    path("accounts/", include("allauth.urls")),
    path("api/", include("apps.api.urls")),
    path("admin/imports/", include("apps.imports.urls")),
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
]
