from django.contrib import admin, messages
from django.utils import timezone
from simple_history.admin import SimpleHistoryAdmin

from .models import Source


@admin.action(description="Mark selected sources verified")
def mark_sources_verified(modeladmin, request, queryset):
    eligible = queryset.exclude(url="")
    updated = 0
    for source in eligible:
        source.verification_status = "verified"
        source.last_verified_at = timezone.localdate()
        source._history_user = request.user
        source._change_reason = "Source verified from the admin action."
        source.save()
        updated += 1
    messages.success(request, f"Verified {updated} source(s).")
    skipped = queryset.count() - updated
    if skipped:
        messages.warning(request, f"Skipped {skipped} source(s) without a URL.")


@admin.action(description="Mark selected sources stale")
def mark_sources_stale(modeladmin, request, queryset):
    updated = 0
    for source in queryset:
        source.verification_status = "stale"
        source._history_user = request.user
        source._change_reason = "Source marked stale from the admin action."
        source.save()
        updated += 1
    messages.success(request, f"Marked {updated} source(s) stale.")


@admin.register(Source)
class SourceAdmin(SimpleHistoryAdmin):
    list_display = (
        "title",
        "asset",
        "verification_status",
        "last_verified_at",
        "http_status",
        "last_checked_at",
        "link_review_status",
        "is_public",
    )
    list_filter = (
        "verification_status",
        "link_review_status",
        "is_public",
        "last_verified_at",
        "http_status",
    )
    search_fields = ("title", "asset__name", "url")
    autocomplete_fields = ("asset",)
    actions = (mark_sources_verified, mark_sources_stale)
    readonly_fields = ("last_checked_at", "http_status", "check_error", "created_at")
