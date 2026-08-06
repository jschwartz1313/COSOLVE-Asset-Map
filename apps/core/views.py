from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Max
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.api.query import filter_public_assets
from apps.assets.models import Asset, SavedView
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source

from .forms import SavedViewForm, UpdateSubmissionForm

DIRECTORY_SORTS = (
    ("name", "Name A-Z"),
    ("region", "Region"),
    ("type", "Asset type"),
)
DIRECTORY_ORDERING = {
    "name": ("name",),
    "region": ("region__name", "name"),
    "type": ("record_type", "name"),
}
PUBLIC_HISTORY_FIELDS = {
    "name",
    "record_type",
    "short_description",
    "overview",
    "unmanned_systems_relevance",
    "website_url",
    "contact_text",
    "contact_phone",
    "contact_email",
    "contact_url",
    "address_line",
    "city",
    "state",
    "postal_code",
    "latitude",
    "longitude",
    "location_precision",
    "region",
    "status",
    "last_verified_at",
    "published_at",
}


def asset_history_entries(asset, include_editor=False):
    records = list(asset.history.select_related("history_user").order_by("-history_date")[:12])
    entries = []
    for index, record in enumerate(records):
        changed_fields = []
        if record.history_type == "+":
            label = "Record added"
        else:
            label = "Record updated"
            if index + 1 < len(records):
                delta = record.diff_against(records[index + 1])
                changed_fields = [
                    change.field.replace("_", " ").title()
                    for change in delta.changes
                    if change.field in PUBLIC_HISTORY_FIELDS
                ]
        entries.append(
            {
                "date": record.history_date,
                "label": label,
                "changed_fields": changed_fields,
                "editor": record.history_user if include_editor else None,
                "reason": record.history_change_reason if include_editor else "",
            }
        )
    return entries


def filter_context():
    regions = Region.objects.filter(is_active=True)
    if settings.PUBLIC_REGION_SLUG:
        regions = regions.filter(slug=settings.PUBLIC_REGION_SLUG)
    return {
        "record_types": Asset.RecordType.choices,
        "categories": StrategicCategory.objects.filter(is_active=True),
        "domains": PlatformDomain.objects.filter(is_active=True),
        "capabilities": Capability.objects.filter(is_active=True),
        "missions": MissionArea.objects.filter(is_active=True),
        "regions": regions,
    }


def map_view(request):
    context = filter_context()
    context["total_assets"] = Asset.public.count()
    return render(request, "map/viewer.html", context)


def directory_view(request):
    queryset = filter_public_assets(request.GET)
    sort_key = request.GET.get("sort", "name")
    if sort_key not in DIRECTORY_ORDERING:
        sort_key = "name"
    queryset = queryset.order_by(*DIRECTORY_ORDERING[sort_key])
    paginator = Paginator(queryset, 12)
    context = filter_context()
    context.update(
        {
            "page_obj": paginator.get_page(request.GET.get("page")),
            "result_count": queryset.count(),
            "sort_key": sort_key,
            "sort_options": DIRECTORY_SORTS,
        }
    )
    return render(request, "assets/directory.html", context)


def asset_detail(request, slug):
    public_assets = Asset.public.all()
    asset = get_object_or_404(
        public_assets.select_related("region").prefetch_related(
            "strategic_categories", "platform_domains", "capabilities", "missions", "sources"
        ),
        slug=slug,
    )
    relationships = asset.outgoing_relationships.filter(
        is_public=True,
        to_asset__status__in=Asset.public_status_values(),
        to_asset__visibility=Asset.Visibility.PUBLIC,
        to_asset__in=public_assets,
    ).select_related("to_asset")
    incoming_relationships = asset.incoming_relationships.filter(
        is_public=True,
        from_asset__status__in=Asset.public_status_values(),
        from_asset__visibility=Asset.Visibility.PUBLIC,
        from_asset__in=public_assets,
    ).select_related("from_asset")
    related_ids = list(relationships.values_list("to_asset_id", flat=True)) + list(
        incoming_relationships.values_list("from_asset_id", flat=True)
    )
    similar_assets = (
        Asset.public.exclude(pk=asset.pk)
        .exclude(pk__in=related_ids)
        .filter(strategic_categories__in=asset.strategic_categories.all())
        .annotate(shared_categories=Count("strategic_categories", distinct=True))
        .select_related("region")
        .order_by("-shared_categories", "name")[:6]
    )
    return render(
        request,
        "assets/detail.html",
        {
            "asset": asset,
            "relationships": relationships,
            "relationship_count": relationships.count(),
            "incoming_relationships": incoming_relationships,
            "incoming_relationship_count": incoming_relationships.count(),
            "similar_assets": similar_assets,
            "history_entries": asset_history_entries(asset, request.user.is_staff),
        },
    )


@login_required
def saved_views(request):
    initial = {
        "view_type": request.GET.get("view_type", SavedView.ViewType.MAP),
        "query_string": request.GET.get("query", "")[:4000],
    }
    form = SavedViewForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        duplicate = request.user.saved_asset_views.filter(
            name=form.cleaned_data["name"], view_type=form.cleaned_data["view_type"]
        ).exists()
        if duplicate:
            form.add_error("name", "You already have a saved view with this name and type.")
        else:
            saved_view = form.save(commit=False)
            saved_view.owner = request.user
            saved_view.save()
            messages.success(request, f'Saved "{saved_view.name}".')
            return redirect("core:saved-views")
    return render(
        request,
        "saved_views/list.html",
        {"form": form, "saved_views": request.user.saved_asset_views.all()},
    )


def open_saved_view(request, token):
    saved_view = get_object_or_404(SavedView, share_token=token)
    if saved_view.owner_id != request.user.pk and not saved_view.is_shared:
        if not request.user.is_authenticated:
            return redirect(f"{reverse('account_login')}?{urlencode({'next': request.path})}")
        return render(request, "403.html", status=403)
    destination = reverse(saved_view.destination_url_name())
    if saved_view.query_string:
        destination = f"{destination}?{saved_view.query_string}"
    return redirect(destination)


@login_required
@require_POST
def delete_saved_view(request, pk):
    saved_view = get_object_or_404(SavedView, pk=pk, owner=request.user)
    name = saved_view.name
    saved_view.delete()
    messages.success(request, f'Deleted "{name}".')
    return redirect("core:saved-views")


def region_metrics(region):
    queryset = Asset.public.filter(region=region)
    total = queryset.count()
    reviewed = queryset.filter(
        reviewed_at__isnull=False, last_verified_at__isnull=False
    ).count()
    verified_source = (
        queryset.filter(
            sources__is_public=True,
            sources__verification_status="verified",
            sources__last_verified_at__isnull=False,
        )
        .distinct()
        .count()
    )
    site_level = queryset.filter(
        location_precision__in=[
            Asset.LocationPrecision.EXACT,
            Asset.LocationPrecision.SITE,
        ]
    ).count()

    def rate(value):
        return round(value * 100 / total) if total else 0

    return {
        "region": region,
        "total": total,
        "quality_metrics": [
            {"name": "Editorially reviewed", "count": reviewed, "rate": rate(reviewed)},
            {
                "name": "Verified public source",
                "count": verified_source,
                "rate": rate(verified_source),
            },
            {"name": "Exact or site-level location", "count": site_level, "rate": rate(site_level)},
        ],
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
        "capabilities": Capability.objects.filter(assets__in=queryset)
        .annotate(asset_count=Count("assets", distinct=True))
        .order_by("-asset_count", "name")[:8],
    }


def region_compare(request):
    if settings.PUBLIC_REGION_SLUG:
        raise Http404
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
    public_assets = Asset.public.all()
    reviewed_count = public_assets.filter(
        reviewed_at__isnull=False, last_verified_at__isnull=False
    ).count()
    return render(
        request,
        "core/about_data.html",
        {
            "asset_count": public_assets.count(),
            "source_count": Source.objects.filter(asset__in=public_assets, is_public=True)
            .values("url")
            .distinct()
            .count(),
            "region_count": Region.objects.filter(assets__in=public_assets).distinct().count(),
            "reviewed_count": reviewed_count,
            "pending_review_count": public_assets.count() - reviewed_count,
            "latest_source_check": Source.objects.filter(
                asset__in=public_assets, is_public=True
            ).aggregate(latest=Max("last_checked_at"))["latest"],
        },
    )


def suggest_update(request, slug=None):
    asset = get_object_or_404(Asset.public, slug=slug) if slug else None
    form = UpdateSubmissionForm(request.POST or None, asset=asset)
    if request.method == "POST" and form.is_valid():
        submission = form.save(commit=False)
        if asset:
            submission.asset = asset
            submission.kind = submission.Kind.CORRECTION
            submission.subject = asset.name
        submission.save()
        return redirect("core:update-thanks")
    return render(request, "core/suggest_update.html", {"form": form, "asset": asset})


def update_thanks(request):
    return render(request, "core/update_thanks.html")


def page_not_found(request, exception):
    return render(request, "404.html", status=404)


def server_error(request):
    return render(request, "500.html", status=500)


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok"})
