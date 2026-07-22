import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from apps.sources.models import Source

from .models import Asset, Relationship, UpdateSubmission


class SourceInline(admin.TabularInline):
    model = Source
    extra = 0
    fields = (
        "title",
        "url",
        "source_date",
        "verification_status",
        "last_verified_at",
        "is_public",
        "notes",
    )


class OutgoingRelationshipInline(admin.TabularInline):
    model = Relationship
    fk_name = "from_asset"
    extra = 0


@admin.action(permissions=["change"], description="Send selected records to source review")
def send_for_review(modeladmin, request, queryset):
    updated = queryset.exclude(status=Asset.Status.ARCHIVED).update(
        status=Asset.Status.NEEDS_REVIEW,
        last_verified_at=None,
        reviewed_at=None,
        reviewed_by=None,
        published_at=None,
    )
    messages.success(request, f"Sent {updated} record(s) to source review.")


@admin.action(permissions=["verify"], description="Mark eligible records verified")
def mark_verified(modeladmin, request, queryset):
    eligible = queryset.filter(
        sources__is_public=True,
        sources__verification_status="verified",
    ).distinct()
    updated = eligible.update(
        status=Asset.Status.VERIFIED,
        last_verified_at=timezone.localdate(),
        reviewed_at=timezone.now(),
        reviewed_by=request.user,
        published_at=None,
    )
    skipped = queryset.count() - updated
    messages.success(request, f"Verified {updated} record(s).")
    if skipped:
        messages.warning(request, f"Skipped {skipped} record(s) without a verified public source.")


@admin.action(permissions=["publish"], description="Publish eligible verified records")
def publish_eligible(modeladmin, request, queryset):
    eligible = queryset.filter(
        status=Asset.Status.VERIFIED,
        sources__is_public=True,
        sources__verification_status="verified",
    ).distinct()
    updated = eligible.update(
        status=Asset.Status.PUBLISHED,
        visibility=Asset.Visibility.PUBLIC,
        published_at=timezone.now(),
    )
    skipped = queryset.count() - updated
    if skipped:
        messages.warning(
            request,
            f"Skipped {skipped} record(s) that were not verified or lacked "
            "a verified public source.",
        )


@admin.action(permissions=["publish"], description="Archive selected records")
def archive_records(modeladmin, request, queryset):
    updated = queryset.update(status=Asset.Status.ARCHIVED, published_at=None)
    messages.success(request, f"Archived {updated} record(s).")


@admin.action(permissions=["export"], description="Export selected records as CSV")
def export_selected(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="cosolve-selected-assets.csv"'
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
            "visibility",
            "last_verified_at",
        ]
    )
    for asset in queryset.select_related("region").order_by("name"):
        writer.writerow(
            [
                asset.name,
                asset.record_type,
                asset.short_description,
                asset.city,
                asset.state,
                asset.region.slug if asset.region else "",
                asset.status,
                asset.visibility,
                asset.last_verified_at or "",
            ]
        )
    return response


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "record_type",
        "region",
        "status",
        "visibility",
        "last_verified_at",
        "updated_at",
    )
    list_filter = ("record_type", "region", "status", "visibility", "last_verified_at")
    search_fields = ("name", "short_description", "unmanned_systems_relevance", "city")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("strategic_categories", "platform_domains", "capabilities", "missions")
    readonly_fields = (
        "status",
        "visibility",
        "last_verified_at",
        "reviewed_at",
        "reviewed_by",
        "published_at",
        "created_at",
        "updated_at",
    )
    inlines = (SourceInline, OutgoingRelationshipInline)
    actions = (
        send_for_review,
        mark_verified,
        publish_eligible,
        archive_records,
        export_selected,
    )
    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "record_type", "short_description")}),
        ("Unmanned systems relevance", {"fields": ("unmanned_systems_relevance",)}),
        (
            "Taxonomy",
            {"fields": ("strategic_categories", "platform_domains", "capabilities", "missions")},
        ),
        (
            "Location",
            {
                "fields": (
                    "address_line",
                    "city",
                    "state",
                    "postal_code",
                    "latitude",
                    "longitude",
                    "location_precision",
                    "region",
                )
            },
        ),
        (
            "Publication",
            {
                "fields": (
                    "status",
                    "visibility",
                    "last_verified_at",
                    "reviewed_at",
                    "reviewed_by",
                    "review_notes",
                    "published_at",
                )
            },
        ),
        ("Public contact", {"fields": ("website_url", "contact_text")}),
        ("Internal", {"fields": ("internal_notes",), "classes": ("collapse",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def has_verify_permission(self, request):
        return request.user.has_perm("assets.can_verify_asset")

    def has_publish_permission(self, request):
        return request.user.has_perm("assets.can_publish_asset")

    def has_export_permission(self, request):
        return request.user.has_perm("assets.can_export_asset")


@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ("from_asset", "relationship_type", "to_asset", "is_public")
    list_filter = ("relationship_type", "is_public")
    search_fields = ("from_asset__name", "to_asset__name", "description")
    autocomplete_fields = ("from_asset", "to_asset")


@admin.register(UpdateSubmission)
class UpdateSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "subject",
        "asset",
        "kind",
        "status",
        "submitter_organization",
    )
    list_filter = ("status", "kind", "created_at")
    search_fields = (
        "subject",
        "details",
        "submitter_name",
        "submitter_organization",
        "submitter_email",
    )
    autocomplete_fields = ("asset",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("asset",)
    date_hierarchy = "created_at"
    actions = ("mark_in_review", "mark_resolved")
    fieldsets = (
        ("Request", {"fields": ("status", "kind", "asset", "subject", "details", "source_url")}),
        (
            "Submitter",
            {
                "fields": (
                    "submitter_name",
                    "submitter_organization",
                    "submitter_email",
                )
            },
        ),
        ("Internal review", {"fields": ("internal_notes",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.action(description="Mark selected submissions in review")
    def mark_in_review(self, request, queryset):
        updated = queryset.update(status=UpdateSubmission.Status.IN_REVIEW)
        messages.success(request, f"Marked {updated} submission(s) in review.")

    @admin.action(description="Mark selected submissions resolved")
    def mark_resolved(self, request, queryset):
        updated = queryset.update(status=UpdateSubmission.Status.RESOLVED)
        messages.success(request, f"Marked {updated} submission(s) resolved.")


admin.site.site_header = "COSOLVE Asset Map Administration"
admin.site.site_title = "COSOLVE Admin"
admin.site.index_title = "Ecosystem data maintenance"
