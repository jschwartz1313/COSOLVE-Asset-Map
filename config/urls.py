from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"

urlpatterns = [
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/", include("apps.api.urls")),
    path("admin/imports/", include("apps.imports.urls")),
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
]
