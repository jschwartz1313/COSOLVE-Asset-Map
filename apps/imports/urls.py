from django.urls import path

from . import views

app_name = "imports"
urlpatterns = [
    path("preview/", views.preview, name="preview"),
    path("commit/", views.commit, name="commit"),
    path("export/", views.export_assets, name="export"),
    path("data-quality/", views.data_quality, name="data-quality"),
    path("data-quality/scan-duplicates/", views.scan_duplicates, name="scan-duplicates"),
    path("audit-log/", views.audit_log, name="audit-log"),
]
