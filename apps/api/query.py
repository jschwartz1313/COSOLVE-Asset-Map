from django.db.models import Q

from apps.assets.models import Asset

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


def filter_public_assets(params):
    queryset = Asset.public.select_related("region").prefetch_related(
        "strategic_categories", "platform_domains", "capabilities", "missions", "sources"
    )
    for parameter, field in FACETS.items():
        values = requested_values(params, parameter)
        if values:
            queryset = queryset.filter(**{f"{field}__in": values})
    query = params.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(short_description__icontains=query)
            | Q(unmanned_systems_relevance__icontains=query)
            | Q(city__icontains=query)
            | Q(capabilities__name__icontains=query)
        )
    return queryset.distinct()


def active_filters(params):
    filters = {key: requested_values(params, key) for key in FACETS}
    if params.get("q"):
        filters["q"] = params["q"]
    return {key: value for key, value in filters.items() if value}
