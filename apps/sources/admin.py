from django.contrib import admin

from .models import Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("title", "asset", "verification_status", "last_verified_at", "is_public")
    list_filter = ("verification_status", "is_public", "last_verified_at")
    search_fields = ("title", "asset__name", "url")
    autocomplete_fields = ("asset",)
