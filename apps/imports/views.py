import csv
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.api.query import filter_public_assets
from apps.assets.models import Asset
from apps.catalog.models import Region
from apps.sources.models import Source

from .services import (
    CSV_COLUMNS,
    TAXONOMY_COLUMNS,
    asset_csv_row,
    parse_csv,
    split_values,
)


@staff_member_required
@permission_required("assets.add_asset", raise_exception=True)
@require_http_methods(["GET", "POST"])
def preview(request):
    context = {}
    if request.method == "POST":
        upload = request.FILES.get("file")
        if not upload:
            context["file_errors"] = ["Choose a CSV file."]
        elif upload.size > 2 * 1024 * 1024:
            context["file_errors"] = ["CSV files are limited to 2 MB."]
        else:
            try:
                rows, file_errors = parse_csv(upload)
            except UnicodeDecodeError:
                rows, file_errors = [], ["The file must use UTF-8 encoding."]
            context.update({"rows": rows, "file_errors": file_errors})
            if not file_errors:
                request.session["asset_import_rows"] = rows
                context["can_commit"] = rows and not any(row["errors"] for row in rows)
    return render(request, "imports/preview.html", context)


@staff_member_required
@permission_required("assets.add_asset", raise_exception=True)
@require_POST
@transaction.atomic
def commit(request):
    rows = request.session.pop("asset_import_rows", [])
    if not rows or any(row["errors"] for row in rows):
        messages.error(request, "No valid import preview is available.")
        return redirect("imports:preview")
    created = 0
    updated = 0
    skipped = 0
    update_existing = request.POST.get("update_existing") == "1"
    for row in rows:
        data = row["data"]
        region = Region.objects.filter(slug=data.get("region", "")).first()
        asset = Asset.objects.filter(pk=row["asset_id"]).first() if row["asset_id"] else None
        was_created = asset is None
        if asset and not update_existing:
            skipped += 1
            continue
        if asset is None:
            asset = Asset(name=data["name"], city=data.get("city", ""))
        asset.record_type = data["record_type"]
        asset.short_description = data["short_description"]
        asset.unmanned_systems_relevance = data["unmanned_systems_relevance"]
        asset.website_url = data.get("website_url", "")
        asset.contact_text = data.get("contact_text", "")
        asset.address_line = data.get("address_line", "")
        asset.city = data.get("city", "")
        asset.state = data.get("state", "VA") or "VA"
        asset.postal_code = data.get("postal_code", "")
        asset.latitude = data.get("latitude") or None
        asset.longitude = data.get("longitude") or None
        asset.location_precision = (
            data.get("location_precision") or Asset.LocationPrecision.APPROXIMATE
        )
        asset.region = region
        if "internal_notes" in data:
            asset.internal_notes = data["internal_notes"]
        asset.status = Asset.Status.DRAFT if was_created else Asset.Status.NEEDS_REVIEW
        asset.visibility = Asset.Visibility.INTERNAL
        asset.last_verified_at = None
        asset.reviewed_at = None
        asset.reviewed_by = None
        asset.published_at = None
        asset.save()
        for column, model in TAXONOMY_COLUMNS.items():
            getattr(asset, column).set(
                model.objects.filter(slug__in=split_values(data.get(column, "")))
            )
        for source_data in row["sources"]:
            Source.objects.update_or_create(
                asset=asset,
                title=source_data["title"],
                defaults={
                    "url": source_data["url"],
                    "source_date": (
                        date.fromisoformat(source_data["source_date"])
                        if source_data["source_date"]
                        else None
                    ),
                    "verification_status": "unreviewed",
                    "last_verified_at": None,
                    "is_public": True,
                    "link_review_status": Source.LinkReviewStatus.AUTOMATIC,
                    "link_review_notes": "",
                },
            )
        created += int(was_created)
        updated += int(not was_created)
    messages.success(
        request,
        f"Import complete: {created} created, {updated} updated, {skipped} skipped.",
    )
    return redirect("admin:assets_asset_changelist")


@staff_member_required
@permission_required("assets.can_export_asset", raise_exception=True)
def export_assets(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="cosolve-assets.csv"'
    writer = csv.DictWriter(response, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    include_internal = request.GET.get("scope") == "all"
    if include_internal:
        queryset = (
            Asset.objects.select_related("region")
            .prefetch_related(
                "strategic_categories",
                "platform_domains",
                "capabilities",
                "missions",
                "sources",
            )
            .order_by("name")
        )
    else:
        queryset = filter_public_assets(request.GET)
    for asset in queryset:
        writer.writerow(asset_csv_row(asset, include_internal=include_internal))
    return response


@staff_member_required
@permission_required("assets.view_asset", raise_exception=True)
def data_quality(request):
    active_assets = Asset.objects.exclude(status=Asset.Status.ARCHIVED)
    stale_cutoff = timezone.localdate() - timedelta(days=settings.STALE_VERIFICATION_DAYS)
    stale = active_assets.filter(
        Q(last_verified_at__lt=stale_cutoff) | Q(last_verified_at__isnull=True)
    ).order_by("last_verified_at", "name")
    missing_sources = (
        active_assets.annotate(
            public_source_count=Count("sources", filter=Q(sources__is_public=True), distinct=True)
        )
        .filter(public_source_count=0)
        .order_by("name")
    )
    missing_coordinates = (
        active_assets.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
        .exclude(location_precision=Asset.LocationPrecision.REGIONAL)
        .order_by("name")
    )
    generalized_locations = active_assets.filter(
        location_precision__in=[
            Asset.LocationPrecision.APPROXIMATE,
            Asset.LocationPrecision.LOCALITY,
        ]
    ).order_by("region__name", "name")
    needs_review = active_assets.filter(
        Q(reviewed_at__isnull=True) | Q(status__in=[Asset.Status.DRAFT, Asset.Status.NEEDS_REVIEW])
    ).order_by("status", "name")
    source_issues = (
        Source.objects.filter(
            Q(verification_status__in=["unreviewed", "stale", "rejected"])
            | Q(last_verified_at__lt=stale_cutoff)
            | Q(last_verified_at__isnull=True)
        )
        .select_related("asset")
        .order_by("verification_status", "asset__name")
    )
    broken_sources = (
        Source.objects.filter(is_public=True)
        .exclude(link_review_status=Source.LinkReviewStatus.ACCEPTED)
        .filter(
            Q(link_review_status=Source.LinkReviewStatus.NEEDS_REPLACEMENT)
            | Q(check_error__gt="")
            | Q(http_status__gte=400)
        )
        .select_related("asset")
        .order_by("asset__name", "title")
    )
    undated_sources = (
        Source.objects.filter(is_public=True, source_date__isnull=True)
        .select_related("asset")
        .order_by("asset__name", "title")
    )
    missing_taxonomy = active_assets.annotate(
        category_count=Count("strategic_categories", distinct=True),
        domain_count=Count("platform_domains", distinct=True),
        capability_count=Count("capabilities", distinct=True),
    ).filter(Q(category_count=0) | Q(domain_count=0) | Q(capability_count=0))
    disconnected = active_assets.annotate(
        outgoing_count=Count("outgoing_relationships", distinct=True),
        incoming_count=Count("incoming_relationships", distinct=True),
    ).filter(outgoing_count=0, incoming_count=0)
    outside_virginia = active_assets.filter(
        Q(latitude__lt=36.45)
        | Q(latitude__gt=39.65)
        | Q(longitude__lt=-83.75)
        | Q(longitude__gt=-75.05)
    )
    repeated_values = list(
        active_assets.exclude(unmanned_systems_relevance="")
        .values("unmanned_systems_relevance")
        .annotate(copy_count=Count("id"))
        .filter(copy_count__gt=1)
        .values_list("unmanned_systems_relevance", flat=True)
    )
    repeated_copy = active_assets.filter(unmanned_systems_relevance__in=repeated_values)

    def coverage_rows(group_field):
        rows = list(
            active_assets.values(group_field)
            .annotate(
                total=Count("id", distinct=True),
                reviewed=Count(
                    "id",
                    filter=Q(reviewed_at__isnull=False, last_verified_at__isnull=False),
                    distinct=True,
                ),
                verified_source=Count(
                    "id",
                    filter=Q(
                        sources__is_public=True,
                        sources__verification_status="verified",
                        sources__last_verified_at__isnull=False,
                    ),
                    distinct=True,
                ),
                located=Count(
                    "id",
                    filter=Q(
                        location_precision__in=[
                            Asset.LocationPrecision.EXACT,
                            Asset.LocationPrecision.SITE,
                        ]
                    ),
                    distinct=True,
                ),
            )
            .order_by(group_field)
        )
        for row in rows:
            total = row["total"] or 1
            row["review_rate"] = round(row["reviewed"] * 100 / total)
            row["source_rate"] = round(row["verified_source"] * 100 / total)
            row["location_rate"] = round(row["located"] * 100 / total)
        return rows

    region_coverage = coverage_rows("region__name")
    type_coverage = coverage_rows("record_type")
    record_type_labels = dict(Asset.RecordType.choices)
    for row in type_coverage:
        row["label"] = record_type_labels.get(row["record_type"], row["record_type"])
    last_source_check = Source.objects.filter(is_public=True).aggregate(
        latest=Max("last_checked_at")
    )["latest"]
    return render(
        request,
        "imports/data_quality.html",
        {
            "stale_cutoff": stale_cutoff,
            "stale": stale[:100],
            "stale_count": stale.count(),
            "missing_sources": missing_sources[:100],
            "missing_sources_count": missing_sources.count(),
            "missing_coordinates": missing_coordinates[:100],
            "missing_coordinates_count": missing_coordinates.count(),
            "generalized_locations": generalized_locations[:100],
            "generalized_locations_count": generalized_locations.count(),
            "needs_review": needs_review[:100],
            "needs_review_count": needs_review.count(),
            "source_issues": source_issues[:100],
            "source_issues_count": source_issues.count(),
            "broken_sources": broken_sources[:100],
            "broken_sources_count": broken_sources.count(),
            "undated_sources": undated_sources[:100],
            "undated_sources_count": undated_sources.count(),
            "missing_taxonomy": missing_taxonomy[:100],
            "missing_taxonomy_count": missing_taxonomy.count(),
            "disconnected": disconnected[:100],
            "disconnected_count": disconnected.count(),
            "outside_virginia": outside_virginia[:100],
            "outside_virginia_count": outside_virginia.count(),
            "repeated_copy": repeated_copy[:100],
            "repeated_copy_count": repeated_copy.count(),
            "region_coverage": region_coverage,
            "type_coverage": type_coverage,
            "last_source_check": last_source_check,
        },
    )
