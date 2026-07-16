from django.conf import settings


def map_settings(request):
    return {
        "basemap_tile_url": settings.BASEMAP_TILE_URL,
        "basemap_attribution": settings.BASEMAP_ATTRIBUTION,
        "default_map_lat": settings.DEFAULT_MAP_LAT,
        "default_map_lon": settings.DEFAULT_MAP_LON,
        "default_map_zoom": settings.DEFAULT_MAP_ZOOM,
    }
