import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.api.query import filter_public_assets
from apps.assets.models import Asset
from apps.catalog.models import Region
from apps.sources.models import Source

from .services import TAXONOMY_COLUMNS, parse_csv, split_values


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
    for row in rows:
        data = row["data"]
        region = Region.objects.filter(slug=data.get("region", "")).first()
        asset, was_created = Asset.objects.get_or_create(
            name=data["name"],
            city=data.get("city", ""),
            defaults={
                "record_type": data["record_type"],
                "short_description": data["short_description"],
                "unmanned_systems_relevance": data["unmanned_systems_relevance"],
                "state": data.get("state", "VA") or "VA",
                "latitude": data.get("latitude") or None,
                "longitude": data.get("longitude") or None,
                "region": region,
                "status": Asset.Status.DRAFT,
                "visibility": Asset.Visibility.INTERNAL,
            },
        )
        if not was_created:
            continue
        for column, model in TAXONOMY_COLUMNS.items():
            getattr(asset, column).set(
                model.objects.filter(slug__in=split_values(data.get(column, "")))
            )
        if data.get("source_title"):
            Source.objects.create(
                asset=asset,
                title=data["source_title"],
                url=data.get("source_url", ""),
                is_public=True,
            )
        created += 1
    messages.success(request, f"Imported {created} new draft record(s).")
    return redirect("admin:assets_asset_changelist")


@staff_member_required
@permission_required("assets.view_asset", raise_exception=True)
def export_assets(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="cosolve-assets.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "name",
            "record_type",
            "short_description",
            "city",
            "state",
            "region",
            "status",
            "last_verified_at",
        ]
    )
    for asset in filter_public_assets(request.GET):
        writer.writerow(
            [
                asset.name,
                asset.record_type,
                asset.short_description,
                asset.city,
                asset.state,
                asset.region.slug if asset.region else "",
                asset.status,
                asset.last_verified_at or "",
            ]
        )
    return response
