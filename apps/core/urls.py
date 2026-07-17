from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.map_view, name="home"),
    path("map/", views.map_view, name="map"),
    path("directory/", views.directory_view, name="directory"),
    path("regions/compare/", views.region_compare, name="region-compare"),
    path("about-data/", views.about_data, name="about-data"),
    path("assets/<slug:slug>/", views.asset_detail, name="asset-detail"),
    path("health/", views.health, name="health"),
]
