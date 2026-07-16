from django.urls import path

from . import views

app_name = "imports"
urlpatterns = [
    path("preview/", views.preview, name="preview"),
    path("commit/", views.commit, name="commit"),
    path("export/", views.export_assets, name="export"),
]
