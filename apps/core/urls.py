from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.map_view, name="home"),
    path("map/", views.map_view, name="map"),
    path("directory/", views.directory_view, name="directory"),
    path("assets/<slug:slug>/", views.asset_detail, name="asset-detail"),
    path("health/", views.health, name="health"),
]
