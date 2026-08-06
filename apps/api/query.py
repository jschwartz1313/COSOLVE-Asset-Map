from django.db.models import Q

from apps.assets.models import Asset
from apps.assets.scoping import public_region_slug

FACETS = {
    "record_type": "record_type",
    "category": "strategic_categories__slug",
    "domain": "platform_domains__slug",
    "capability": "capabilities__slug",
    "mission": "missions__slug",
    "region": "region__slug",
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
        if values:
            queryset = queryset.filter(**{f"{field}__in": values})
    query = params.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(short_description__icontains=query)
            | Q(overview__icontains=query)
            | Q(unmanned_systems_relevance__icontains=query)
            | Q(contact_text__icontains=query)
            | Q(contact_email__icontains=query)
            | Q(city__icontains=query)
            | Q(region__name__icontains=query)
            | Q(strategic_categories__name__icontains=query)
            | Q(platform_domains__name__icontains=query)
            | Q(capabilities__name__icontains=query)
            | Q(missions__name__icontains=query)
            | Q(sources__title__icontains=query)
            | Q(outgoing_relationships__to_asset__name__icontains=query)
            | Q(incoming_relationships__from_asset__name__icontains=query)
        )
    return queryset.distinct()


def active_filters(params):
    filters = {
        key: requested_values(params, key)
        for key in FACETS
        if key != "region" or not public_region_slug()
    }
    if params.get("q"):
        filters["q"] = params["q"]
    return {key: value for key, value in filters.items() if value}
