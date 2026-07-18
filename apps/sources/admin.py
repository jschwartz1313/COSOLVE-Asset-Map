from django.contrib import admin, messages
from django.utils import timezone

from .models import Source


@admin.action(description="Mark selected sources verified")
def mark_sources_verified(modeladmin, request, queryset):
    updated = queryset.update(
        verification_status="verified",
        last_verified_at=timezone.localdate(),
    )
    messages.success(request, f"Verified {updated} source(s).")


@admin.action(description="Mark selected sources stale")
def mark_sources_stale(modeladmin, request, queryset):
    updated = queryset.update(verification_status="stale")
    messages.success(request, f"Marked {updated} source(s) stale.")


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "asset",
        "verification_status",
        "last_verified_at",
        "http_status",
        "last_checked_at",
        "is_public",
    )
    list_filter = ("verification_status", "is_public", "last_verified_at", "http_status")
    search_fields = ("title", "asset__name", "url")
    autocomplete_fields = ("asset",)
    actions = (mark_sources_verified, mark_sources_stale)
    readonly_fields = ("last_checked_at", "http_status", "check_error", "created_at")
