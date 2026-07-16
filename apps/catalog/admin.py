from django.contrib import admin

from .models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory


@admin.register(StrategicCategory, PlatformDomain, Capability, MissionArea, Region)
class TaxonomyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "display_order")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
