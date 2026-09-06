from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.map_view, name="home"),
    path("map/", views.map_view, name="map"),
    path("directory/", views.directory_view, name="directory"),
    path("connect/", views.connect, name="connect"),
    path("saved-views/", views.saved_views, name="saved-views"),
    path("saved-views/<uuid:token>/", views.open_saved_view, name="open-saved-view"),
    path(
        "saved-views/<uuid:pk>/delete/",
        views.delete_saved_view,
        name="delete-saved-view",
    ),
    path("regions/compare/", views.region_compare, name="region-compare"),
    path("about-data/", views.about_data, name="about-data"),
    path("suggest-update/", views.suggest_update, name="suggest-update"),
    path("suggest-update/thanks/", views.update_thanks, name="update-thanks"),
    path(
        "assets/<slug:slug>/suggest-update/",
        views.suggest_update,
        name="asset-suggest-update",
    ),
    path("assets/<slug:slug>/", views.asset_detail, name="asset-detail"),
    path("health/", views.health, name="health"),
]
