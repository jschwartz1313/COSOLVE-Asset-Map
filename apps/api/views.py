from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from apps.assets.models import Asset, Relationship
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory

from .query import active_filters, filter_public_assets
from .serializers import asset_feature, public_asset_dict, relationship_feature


def taxonomy_values(model):
    queryset = model.objects.filter(is_active=True)
    if model is Region and settings.PUBLIC_REGION_SLUG:
        queryset = queryset.filter(slug=settings.PUBLIC_REGION_SLUG)
    return list(queryset.values("name", "slug"))


def requested_limit(request, default, maximum):
    try:
        return min(max(int(request.GET.get("limit", str(default))), 1), maximum)
    except ValueError:
        return default


@require_GET
def asset_list(request):
    queryset = filter_public_assets(request.GET)
    limit = requested_limit(request, 100, 500)
    records = [public_asset_dict(asset, include_detail=False) for asset in queryset[:limit]]
    result_count = queryset.count()
    return JsonResponse(
        {
            "result_count": result_count,
            "returned_count": len(records),
            "truncated": result_count > len(records),
            "active_filters": active_filters(request.GET),
            "results": records,
        }
    )


@require_GET
def asset_geojson(request):
    queryset = filter_public_assets(request.GET)
    limit = requested_limit(request, 2000, 5000)
    features = [asset_feature(asset) for asset in queryset[:limit]]
    result_count = queryset.count()
    return JsonResponse(
        {
            "type": "FeatureCollection",
            "result_count": result_count,
            "returned_count": len(features),
            "truncated": result_count > len(features),
            "active_filters": active_filters(request.GET),
            "features": features,
        }
    )


@require_GET
def relationship_geojson(request):
    public_assets = Asset.public.filter(
        latitude__isnull=False,
        longitude__isnull=False,
    ).exclude(location_precision=Asset.LocationPrecision.HIDDEN)
    relationships = Relationship.objects.filter(
        is_public=True,
        from_asset__in=public_assets,
        to_asset__in=public_assets,
    ).select_related("from_asset", "to_asset")
    return JsonResponse(
        {
            "type": "FeatureCollection",
            "result_count": relationships.count(),
            "features": [relationship_feature(item) for item in relationships],
        }
    )


@require_GET
def asset_detail(request, slug):
    asset = get_object_or_404(
        Asset.public.select_related("region").prefetch_related(
            "strategic_categories", "platform_domains", "capabilities", "missions", "sources"
        ),
        slug=slug,
    )
    return JsonResponse(public_asset_dict(asset))


@require_GET
def filter_values(request):
    return JsonResponse(
        {
            "record_types": [
                {"slug": value, "name": label} for value, label in Asset.RecordType.choices
            ],
            "strategic_categories": taxonomy_values(StrategicCategory),
            "platform_domains": taxonomy_values(PlatformDomain),
            "capabilities": taxonomy_values(Capability),
            "missions": taxonomy_values(MissionArea),
            "regions": taxonomy_values(Region),
        }
    )


@require_GET
def region_summary(request, slug):
    if settings.PUBLIC_REGION_SLUG and slug != settings.PUBLIC_REGION_SLUG:
        raise Http404
    region = get_object_or_404(Region, slug=slug, is_active=True)
    params = request.GET.copy()
    params.pop("region", None)
    queryset = filter_public_assets(params).filter(region=region)
    by_type = {
        value: queryset.filter(record_type=value).count()
        for value, _label in Asset.RecordType.choices
    }
    by_category = {
        category.slug: queryset.filter(strategic_categories=category).count()
        for category in StrategicCategory.objects.filter(is_active=True)
    }
    return JsonResponse(
        {
            "region": {"name": region.name, "slug": region.slug},
            "total": queryset.count(),
            "by_type": by_type,
            "by_category": by_category,
            "active_filters": active_filters(params),
        }
    )
