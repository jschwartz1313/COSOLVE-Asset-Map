from django.contrib import admin, messages
from django.utils import timezone

from apps.sources.models import Source

from .models import Asset, Relationship


class SourceInline(admin.TabularInline):
    model = Source
    extra = 0
    fields = ("title", "url", "source_date", "last_verified_at", "is_public")


class OutgoingRelationshipInline(admin.TabularInline):
    model = Relationship
    fk_name = "from_asset"
    extra = 0


@admin.action(description="Mark selected records verified")
def mark_verified(modeladmin, request, queryset):
    queryset.update(status=Asset.Status.VERIFIED, last_verified_at=timezone.localdate())


@admin.action(description="Publish eligible selected records")
def publish_eligible(modeladmin, request, queryset):
    eligible_ids = [asset.pk for asset in queryset if asset.sources.filter(is_public=True).exists()]
    updated = queryset.filter(pk__in=eligible_ids).update(
        status=Asset.Status.PUBLISHED,
        visibility=Asset.Visibility.PUBLIC,
        published_at=timezone.now(),
    )
    skipped = queryset.count() - updated
    if skipped:
        messages.warning(request, f"Skipped {skipped} record(s) without a public source.")


@admin.action(description="Archive selected records")
def archive_records(modeladmin, request, queryset):
    queryset.update(status=Asset.Status.ARCHIVED, published_at=None)


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
    readonly_fields = ("created_at", "updated_at", "published_at")
    inlines = (SourceInline, OutgoingRelationshipInline)
    actions = (mark_verified, publish_eligible, archive_records)
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
        ("Publication", {"fields": ("status", "visibility", "last_verified_at", "published_at")}),
        ("Public contact", {"fields": ("website_url", "contact_text")}),
        ("Internal", {"fields": ("internal_notes",), "classes": ("collapse",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ("from_asset", "relationship_type", "to_asset", "is_public")
    list_filter = ("relationship_type", "is_public")
    search_fields = ("from_asset__name", "to_asset__name", "description")
    autocomplete_fields = ("from_asset", "to_asset")


admin.site.site_header = "COSOLVE Asset Map Administration"
admin.site.site_title = "COSOLVE Admin"
admin.site.index_title = "Ecosystem data maintenance"
