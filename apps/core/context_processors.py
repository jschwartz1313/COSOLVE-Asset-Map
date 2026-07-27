from django.conf import settings
from django.db.models import Max
from django.db.utils import OperationalError, ProgrammingError

from apps.assets.models import Asset


def map_settings(request):
    public_scope_is_regional = bool(settings.PUBLIC_REGION_SLUG)
    context = {
        "basemap_tile_url": settings.BASEMAP_TILE_URL,
        "basemap_attribution": settings.BASEMAP_ATTRIBUTION,
        "default_map_lat": settings.DEFAULT_MAP_LAT,
        "default_map_lon": settings.DEFAULT_MAP_LON,
        "default_map_zoom": settings.DEFAULT_MAP_ZOOM,
        "public_scope_is_regional": public_scope_is_regional,
        "public_scope_name": settings.PUBLIC_SCOPE_NAME,
        "public_scope_region_slug": settings.PUBLIC_REGION_SLUG,
        "public_scope_eyebrow": (
            f"{settings.PUBLIC_SCOPE_NAME} ecosystem"
            if public_scope_is_regional
            else "Virginia ecosystem"
        ),
        "public_scope_geographic_focus": (
            settings.PUBLIC_SCOPE_NAME
            if public_scope_is_regional
            else "Commonwealth of Virginia"
        ),
    }
    try:
        context["catalog_last_updated"] = Asset.public.aggregate(latest=Max("updated_at"))["latest"]
    except (OperationalError, ProgrammingError):
        context["catalog_last_updated"] = None
    return context


def account_settings(request):
    return {"oidc_enabled": settings.OIDC_ENABLED}
