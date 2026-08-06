import csv
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Max, Q, When
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.api.query import filter_public_assets
from apps.assets.models import Asset, AssetReviewComment, DuplicateCandidate
from apps.assets.quality import sync_duplicate_candidates
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
        asset.overview = data.get("overview", "")
        asset.unmanned_systems_relevance = data["unmanned_systems_relevance"]
        asset.website_url = data.get("website_url", "")
        asset.contact_text = data.get("contact_text", "")
        asset.contact_phone = data.get("contact_phone", "")
        asset.contact_email = data.get("contact_email", "")
        asset.contact_url = data.get("contact_url", "")
        asset.activity_status = data.get("activity_status", "")
        asset.current_activity = data.get("current_activity", "")
        asset.partnership_opportunities = data.get("partnership_opportunities", "")
        asset.activity_source_url = data.get("activity_source_url", "")
        asset.activity_last_verified_at = (
            date.fromisoformat(data["activity_last_verified_at"])
            if data.get("activity_last_verified_at")
            else None
        )
        asset.owner_operator = data.get("owner_operator", "")
        asset.available_acreage = data.get("available_acreage") or None
        asset.development_status = data.get("development_status", "")
        asset.development_notes = data.get("development_notes", "")
        asset.infrastructure_access = data.get("infrastructure_access", "")
        asset.development_source_url = data.get("development_source_url", "")
        asset.development_last_verified_at = (
            date.fromisoformat(data["development_last_verified_at"])
            if data.get("development_last_verified_at")
            else None
        )
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
    incomplete_profiles = active_assets.filter(
        Q(overview="") | Q(contact_text="") | Q(contact_url="")
    ).order_by("name")
    generalized_locations = active_assets.filter(
        location_precision__in=[
            Asset.LocationPrecision.APPROXIMATE,
            Asset.LocationPrecision.LOCALITY,
        ]
    ).order_by("region__name", "name")
    activity_claims = (
        Q(activity_status__gt="")
        | Q(current_activity__gt="")
        | Q(partnership_opportunities__gt="")
    )
    development_claims = (
        Q(owner_operator__gt="")
        | Q(development_status__gt="")
        | Q(development_notes__gt="")
        | Q(infrastructure_access__gt="")
        | Q(available_acreage__isnull=False)
    )
    dynamic_claims_stale = active_assets.filter(
        (
            activity_claims
            & (
                Q(activity_last_verified_at__lt=stale_cutoff)
                | Q(activity_last_verified_at__isnull=True)
                | Q(activity_source_url="")
            )
        )
        | (
            development_claims
            & (
                Q(development_last_verified_at__lt=stale_cutoff)
                | Q(development_last_verified_at__isnull=True)
                | Q(development_source_url="")
            )
        )
    ).order_by("name")
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
    today = timezone.localdate()
    priority_order = Case(
        When(review_priority=Asset.ReviewPriority.URGENT, then=0),
        When(review_priority=Asset.ReviewPriority.HIGH, then=1),
        When(review_priority=Asset.ReviewPriority.NORMAL, then=2),
        default=3,
        output_field=IntegerField(),
    )
    review_queue = (
        needs_review.select_related("review_assignee", "region")
        .annotate(priority_order=priority_order)
        .order_by("priority_order", "review_due_at", "name")
    )
    my_review_queue = review_queue.filter(review_assignee=request.user)
    overdue_reviews = review_queue.filter(review_due_at__lt=today)
    unassigned_reviews = review_queue.filter(review_assignee__isnull=True)
    reviewer_workload = list(
        review_queue.values(
            "review_assignee_id",
            "review_assignee__username",
            "review_assignee__first_name",
            "review_assignee__last_name",
        )
        .annotate(
            total=Count("id"),
            overdue=Count("id", filter=Q(review_due_at__lt=today)),
        )
        .order_by("-total", "review_assignee__username")
    )

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
    coverage_counts = {
        (row["region_id"], row["record_type"]): row["total"]
        for row in active_assets.values("region_id", "record_type").annotate(
            total=Count("id", distinct=True)
        )
    }
    gap_rows = []
    for region in Region.objects.filter(is_active=True):
        cells = []
        for record_type, label in Asset.RecordType.choices:
            count = coverage_counts.get((region.pk, record_type), 0)
            status = "missing" if count == 0 else "sparse" if count <= 2 else "documented"
            cells.append(
                {
                    "record_type": record_type,
                    "label": label,
                    "count": count,
                    "status": status,
                }
            )
        gap_rows.append(
            {
                "region": region,
                "cells": cells,
                "gap_count": sum(cell["status"] != "documented" for cell in cells),
            }
        )
    open_duplicates = DuplicateCandidate.objects.filter(
        status=DuplicateCandidate.Status.OPEN
    ).select_related("left_asset", "right_asset")
    public_sources = Source.objects.filter(is_public=True)
    source_check_cutoff = timezone.now() - timedelta(days=7)
    recently_checked_sources = public_sources.filter(last_checked_at__gte=source_check_cutoff)
    healthy_sources = recently_checked_sources.exclude(
        Q(check_error__gt="") | Q(http_status__gte=400)
    ).exclude(link_review_status=Source.LinkReviewStatus.NEEDS_REPLACEMENT)
    unchecked_sources = public_sources.filter(
        Q(last_checked_at__lt=source_check_cutoff) | Q(last_checked_at__isnull=True)
    )
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
            "incomplete_profiles": incomplete_profiles[:100],
            "incomplete_profiles_count": incomplete_profiles.count(),
            "generalized_locations": generalized_locations[:100],
            "generalized_locations_count": generalized_locations.count(),
            "dynamic_claims_stale": dynamic_claims_stale[:100],
            "dynamic_claims_stale_count": dynamic_claims_stale.count(),
            "needs_review": needs_review[:100],
            "needs_review_count": needs_review.count(),
            "my_review_queue": my_review_queue[:100],
            "my_review_queue_count": my_review_queue.count(),
            "overdue_reviews": overdue_reviews[:100],
            "overdue_review_count": overdue_reviews.count(),
            "unassigned_reviews": unassigned_reviews[:100],
            "unassigned_review_count": unassigned_reviews.count(),
            "reviewer_workload": reviewer_workload,
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
            "gap_rows": gap_rows,
            "record_type_choices": Asset.RecordType.choices,
            "open_duplicates": open_duplicates[:100],
            "open_duplicate_count": open_duplicates.count(),
            "public_source_count": public_sources.count(),
            "healthy_source_count": healthy_sources.count(),
            "unchecked_source_count": unchecked_sources.count(),
            "last_source_check": last_source_check,
        },
    )


@staff_member_required
@permission_required("assets.change_duplicatecandidate", raise_exception=True)
@require_POST
def scan_duplicates(request):
    result = sync_duplicate_candidates()
    messages.success(
        request,
        "Duplicate scan complete: "
        f"{result['detected']} candidates detected, "
        f"{result['created']} created, "
        f"{result['updated']} refreshed.",
    )
    return redirect("imports:data-quality")


def _history_events(
    history_manager,
    object_type,
    label_field,
    limit=75,
    related_fields=(),
):
    events = []
    records = history_manager.select_related(
        "history_user", *related_fields
    ).order_by("-history_date")[:limit]
    for record in records:
        changed_fields = []
        if record.history_type == "~":
            previous = record.prev_record
            if previous:
                changed_fields = [
                    change.field.replace("_", " ").title()
                    for change in record.diff_against(previous).changes
                ]
        events.append(
            {
                "date": record.history_date,
                "action": {"+": "Created", "~": "Updated", "-": "Deleted"}[
                    record.history_type
                ],
                "object_type": object_type,
                "object_label": (
                    label_field(record)
                    if callable(label_field)
                    else getattr(record, label_field, str(record))
                ),
                "editor": record.history_user,
                "reason": record.history_change_reason,
                "changed_fields": changed_fields,
            }
        )
    return events


@staff_member_required
@permission_required("assets.view_asset", raise_exception=True)
def audit_log(request):
    duplicate_decisions = DuplicateCandidate.history.exclude(
        history_user__isnull=True,
        status=DuplicateCandidate.Status.OPEN,
    )

    def duplicate_label(record):
        left = getattr(record.left_asset, "name", None) or str(record.left_asset_id)
        right = getattr(record.right_asset, "name", None) or str(record.right_asset_id)
        return f"{left} / {right}"

    events = [
        *_history_events(Asset.history, "Asset", "name"),
        *_history_events(Source.history, "Source", "title"),
        *_history_events(AssetReviewComment.history, "Review comment", "body", limit=40),
        *_history_events(
            duplicate_decisions,
            "Duplicate review",
            duplicate_label,
            limit=40,
            related_fields=("left_asset", "right_asset"),
        ),
    ]
    events.sort(key=lambda event: event["date"], reverse=True)
    return render(request, "imports/audit_log.html", {"events": events[:200]})
