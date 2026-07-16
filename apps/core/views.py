from django.core.paginator import Paginator
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.api.query import filter_public_assets
from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory


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
    return render(request, "assets/detail.html", {"asset": asset, "relationships": relationships})


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok"})
