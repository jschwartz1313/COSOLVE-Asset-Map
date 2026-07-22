from django.conf import settings
from django.db.models import Max
from django.db.utils import OperationalError, ProgrammingError

from apps.assets.models import Asset


def map_settings(request):
    context = {
        "basemap_tile_url": settings.BASEMAP_TILE_URL,
        "basemap_attribution": settings.BASEMAP_ATTRIBUTION,
        "default_map_lat": settings.DEFAULT_MAP_LAT,
        "default_map_lon": settings.DEFAULT_MAP_LON,
        "default_map_zoom": settings.DEFAULT_MAP_ZOOM,
    }
    try:
        context["catalog_last_updated"] = Asset.public.aggregate(latest=Max("updated_at"))["latest"]
    except (OperationalError, ProgrammingError):
        context["catalog_last_updated"] = None
    return context
