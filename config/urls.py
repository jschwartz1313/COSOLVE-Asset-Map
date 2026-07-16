from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("apps.api.urls")),
    path("admin/imports/", include("apps.imports.urls")),
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
]
