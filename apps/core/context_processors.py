from django.conf import settings
from django.db.models import Max
from django.db.utils import OperationalError, ProgrammingError

from apps.assets.geography import BY_CODE, STATES, scoped_regions
from apps.assets.models import Asset
from apps.assets.scoping import public_region_slug


def map_settings(request):
    state = getattr(request, "inventory_state", BY_CODE["VA"])
    virginia = state.code == "VA"
    public_scope_is_regional = bool(public_region_slug())
    scope_name = settings.PUBLIC_SCOPE_NAME if virginia else state.name
    can_preview = (request.user.is_active and request.user.is_staff
                   and request.user.has_perm("assets.view_asset"))
    context = {
        "state_switch_view": (
            request.resolver_match.url_name
            if request.resolver_match and request.resolver_match.url_name in {
                "map", "directory", "test-sites", "manufacturing-search",
                "asset-compare", "about-data", "region-compare",
            } else "map"
        ),
        "basemap_tile_url": settings.BASEMAP_TILE_URL,
        "basemap_attribution": settings.BASEMAP_ATTRIBUTION,
        "light_basemap_tile_url": settings.LIGHT_BASEMAP_TILE_URL,
        "light_basemap_attribution": settings.LIGHT_BASEMAP_ATTRIBUTION,
        "imagery_basemap_tile_url": settings.IMAGERY_BASEMAP_TILE_URL,
        "imagery_basemap_attribution": settings.IMAGERY_BASEMAP_ATTRIBUTION,
        "topo_basemap_tile_url": settings.TOPO_BASEMAP_TILE_URL,
        "topo_basemap_attribution": settings.TOPO_BASEMAP_ATTRIBUTION,
        "default_map_lat": settings.DEFAULT_MAP_LAT if virginia else state.lat,
        "default_map_lon": settings.DEFAULT_MAP_LON if virginia else state.lon,
        "default_map_zoom": settings.DEFAULT_MAP_ZOOM if virginia else state.zoom,
        "inventory_state": state,
        "inventory_prefix": state.prefix,
        "inventory_is_virginia": virginia,
        "inventory_has_regions": virginia or scoped_regions().exists(),
        "inventory_preview": getattr(request, "inventory_preview", False),
        "boundary_version": "2025" if virginia else "20261117",
        "inventory_states": STATES if can_preview or settings.MULTISTATE_PUBLIC else STATES[:1],
        "state_boundary_path": (
            "data/virginia-state-boundary.geojson" if virginia
            else f"data/states/{state.slug}-boundary.geojson"
        ),
        "county_boundary_path": (
            "data/virginia-counties.geojson" if virginia
            else f"data/states/{state.slug}-counties.geojson"
        ),
        "public_scope_is_regional": public_scope_is_regional,
        "public_scope_name": scope_name,
        "public_scope_region_slug": public_region_slug(),
        "public_scope_eyebrow": (
            f"{scope_name} ecosystem"
        ),
        "public_scope_geographic_focus": (
            scope_name
            if public_scope_is_regional
            else "Commonwealth of Virginia" if virginia else state.name
        ),
    }
    try:
        context["catalog_last_updated"] = Asset.public.aggregate(latest=Max("updated_at"))["latest"]
    except (OperationalError, ProgrammingError):
        context["catalog_last_updated"] = None
    return context


def account_settings(request):
    return {"oidc_enabled": settings.OIDC_ENABLED}
