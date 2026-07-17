from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Max, Min
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.api.query import filter_public_assets
from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source


def filter_context():
    return {
        "record_types": Asset.RecordType.choices,
        "categories": StrategicCategory.objects.filter(is_active=True),
        "domains": PlatformDomain.objects.filter(is_active=True),
        "capabilities": Capability.objects.filter(is_active=True),
        "missions": MissionArea.objects.filter(is_active=True),
        "regions": Region.objects.filter(is_active=True),
    }


def map_view(request):
    context = filter_context()
    context["total_assets"] = Asset.public.count()
    return render(request, "map/viewer.html", context)


def directory_view(request):
    queryset = filter_public_assets(request.GET)
    paginator = Paginator(queryset, 12)
    context = filter_context()
    context.update(
        {"page_obj": paginator.get_page(request.GET.get("page")), "result_count": queryset.count()}
    )
    return render(request, "assets/directory.html", context)


def asset_detail(request, slug):
    asset = get_object_or_404(
        Asset.public.select_related("region").prefetch_related(
            "strategic_categories", "platform_domains", "capabilities", "missions", "sources"
        ),
        slug=slug,
    )
    relationships = asset.outgoing_relationships.filter(
        is_public=True,
        to_asset__status=Asset.Status.PUBLISHED,
        to_asset__visibility=Asset.Visibility.PUBLIC,
    ).select_related("to_asset")
    incoming_relationships = asset.incoming_relationships.filter(
        is_public=True,
        from_asset__status=Asset.Status.PUBLISHED,
        from_asset__visibility=Asset.Visibility.PUBLIC,
    ).select_related("from_asset")
    return render(
        request,
        "assets/detail.html",
        {
            "asset": asset,
            "relationships": relationships,
            "incoming_relationships": incoming_relationships,
        },
    )


def region_metrics(region):
    queryset = Asset.public.filter(region=region)
    return {
        "region": region,
        "total": queryset.count(),
        "record_types": [
            {
                "name": label,
                "count": queryset.filter(record_type=value).count(),
            }
            for value, label in Asset.RecordType.choices
        ],
        "categories": StrategicCategory.objects.filter(assets__in=queryset)
        .annotate(asset_count=Count("assets", distinct=True))
        .order_by("-asset_count", "name")[:6],
        "domains": PlatformDomain.objects.filter(assets__in=queryset)
        .annotate(asset_count=Count("assets", distinct=True))
        .order_by("-asset_count", "name")[:6],
    }


def region_compare(request):
    regions = list(Region.objects.filter(is_active=True))
    if not regions:
        return render(
            request,
            "regions/compare.html",
            {"regions": [], "first": None, "second": None, "comparisons": []},
        )
    first_slug = request.GET.get("region_a", "hampton-roads")
    second_slug = request.GET.get("region_b", "northern-virginia")
    first = next((region for region in regions if region.slug == first_slug), regions[0])
    second = next((region for region in regions if region.slug == second_slug), regions[-1])
    first_metrics = region_metrics(first)
    second_metrics = region_metrics(second)
    return render(
        request,
        "regions/compare.html",
        {
            "regions": regions,
            "first": first_metrics,
            "second": second_metrics,
            "comparisons": [first_metrics, second_metrics],
        },
    )


def about_data(request):
    verification = Asset.public.aggregate(
        earliest=Min("last_verified_at"), latest=Max("last_verified_at")
    )
    return render(
        request,
        "core/about_data.html",
        {
            "asset_count": Asset.public.count(),
            "source_count": Source.objects.filter(asset__in=Asset.public.all(), is_public=True)
            .values("url")
            .distinct()
            .count(),
            "region_count": Region.objects.filter(assets__in=Asset.public.all()).distinct().count(),
            "verification": verification,
        },
    )


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok"})
