from django.db.models import Q

from apps.assets.discovery import RESOURCE_QUERIES
from apps.assets.models import Asset
from apps.assets.scoping import public_region_slug

from .search import PUBLIC_NAME_ORDER, apply_search

FACETS = {
    "record_type": "record_type",
    "category": "strategic_categories__slug",
    "domain": "platform_domains__slug",
    "capability": "capabilities__slug",
    "mission": "missions__slug",
    "region": "region__slug",
    "activity": "activity_status",
}


def requested_values(params, key):
    values = []
    for value in params.getlist(key):
        values.extend(part.strip() for part in value.split(",") if part.strip())
    return values


def filter_public_assets(params, include_related=True):
    queryset = Asset.public.select_related("region")
    if include_related:
        queryset = queryset.prefetch_related(
            "strategic_categories", "platform_domains", "capabilities", "missions", "sources"
        )
    for parameter, field in FACETS.items():
        if parameter == "region" and public_region_slug():
            continue
        values = requested_values(params, parameter)
        if parameter == "activity":
            values = ["" if value == "undocumented" else value for value in values]
        if values:
            queryset = queryset.filter(**{f"{field}__in": values})
    purpose = params.get("purpose", "")
    if purpose in RESOURCE_QUERIES:
        queryset = queryset.filter(RESOURCE_QUERIES[purpose])
    if params.get("test_specs") == "1":
        queryset = queryset.exclude(test_source_url="").filter(
            Q(test_aircraft__gt="") | Q(test_dimensions__gt="")
            | Q(test_runway_length_ft__isnull=False) | Q(test_access__gt=""),
            test_last_verified_at__isnull=False,
        )
    runway = params.get("min_runway", "").strip()
    if runway:
        if (runway.isascii() and runway.isdigit() and len(runway) <= 6
                and 1 <= int(runway) <= 100000):
            queryset = queryset.filter(test_runway_length_ft__gte=int(runway))
        else:
            return queryset.none()
    query = params.get("q", "").strip()
    if query:
        queryset = apply_search(queryset, query)
    else:
        queryset = queryset.order_by(PUBLIC_NAME_ORDER, "pk")
    return queryset.distinct()


def active_filters(params):
    filters = {
        key: requested_values(params, key)
        for key in FACETS
        if key != "region" or not public_region_slug()
    }
    if params.get("q"):
        filters["q"] = params["q"]
    for key in ("purpose", "test_specs", "min_runway"):
        if params.get(key):
            filters[key] = params[key]
    return {key: value for key, value in filters.items() if value}
