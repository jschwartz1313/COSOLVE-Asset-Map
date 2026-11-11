from django.urls import path

from . import decision_tools, manufacturing_views, operator_views, views

app_name = "core"
urlpatterns = [
    path("", views.map_view, name="home"),
    path("map/", views.map_view, name="map"),
    path("directory/", views.directory_view, name="directory"),
    path("test-sites/", views.test_sites, name="test-sites"),
    path("manufacturing/", manufacturing_views.manufacturing_search, name="manufacturing-search"),
    path("operator-review/<str:token>/", operator_views.operator_review, name="operator-review"),
    path("compare/", decision_tools.compare_assets, name="asset-compare"),
    path("assets/<slug:slug>/inquiry/", decision_tools.prepare_inquiry, name="asset-inquiry"),
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
    path("references/maap/", views.maap_reference, name="maap-reference"),
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
