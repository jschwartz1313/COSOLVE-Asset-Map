from django.urls import path

from . import views

app_name = "api"
urlpatterns = [
    path("assets/", views.asset_list, name="asset-list"),
    path("assets.geojson", views.asset_geojson, name="asset-geojson"),
    path("assets/<slug:slug>/", views.asset_detail, name="asset-detail"),
    path("filters/", views.filter_values, name="filter-values"),
    path("regions/<slug:slug>/summary/", views.region_summary, name="region-summary"),
]
