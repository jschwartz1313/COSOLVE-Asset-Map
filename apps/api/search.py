"""Bounded word/phrase search over public asset information."""

from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce, Lower, NullIf
from django.utils.text import smart_split, unescape_string_literal

from apps.assets.models import Asset, Relationship
from apps.catalog.models import Capability, MissionArea, PlatformDomain, StrategicCategory
from apps.sources.models import Source

PUBLIC_NAME_ORDER = Lower(Coalesce(NullIf("display_name", Value("")), "name"))
SEARCH_FIELDS = (
    "name",
    "display_name",
    "search_aliases",
    "short_description",
    "overview",
    "unmanned_systems_relevance",
    "current_activity",
    "partnership_opportunities",
    "owner_operator",
    "development_notes",
    "infrastructure_access",
    "test_aircraft",
    "test_dimensions",
    "test_access",
    "location_notes",
    "contact_text",
    "contact_email",
    "city",
    "region__name",
)
SEARCH_TAXONOMIES = (StrategicCategory, PlatformDomain, Capability, MissionArea)
SYNONYM_GROUPS = (
    ("drone", "drones", "uas", "uav", "unmanned", "uncrewed"),
    ("test", "testing"),
)


def search_terms(query):
    if len(query) > 500:
        return None
    terms = []
    for value in smart_split(query):
        quoted = value[:1] in {'"', "'"} and value[-1:] == value[:1]
        term = unescape_string_literal(value) if quoted and len(value) > 1 else value
        term = term.casefold().strip()
        if term and (term, quoted) not in terms:
            terms.append((term, quoted))
    return terms if len(terms) <= 16 else None


def contains_any(fields, alternatives):
    condition = Q()
    for field in fields:
        for term in alternatives:
            condition |= Q(**{f"{field}__icontains": term})
    return condition


def public_term_query(alternatives):
    condition = contains_any(SEARCH_FIELDS, alternatives)
    # Isolate each to-many relation so tags, sources, and relationships never multiply rows.
    for model in SEARCH_TAXONOMIES:
        matching = model.objects.filter(assets__pk=OuterRef("pk")).filter(
            contains_any(("name",), alternatives)
        )
        condition |= Q(Exists(matching))
    sources = Source.objects.filter(asset_id=OuterRef("pk"), is_public=True).filter(
        contains_any(("title",), alternatives)
    )
    condition |= Q(Exists(sources))
    public_partners = Asset.public.filter(
        contains_any(("name", "display_name"), alternatives)
    ).order_by().values("pk")
    for origin, target in (("from_asset", "to_asset"), ("to_asset", "from_asset")):
        matching = Relationship.objects.filter(
            is_public=True,
            **{origin: OuterRef("pk"), f"{target}__in": public_partners},
        )
        condition |= Q(Exists(matching))
    return condition


def apply_search(queryset, query):
    terms = search_terms(query)
    if terms is None:
        return queryset.none()
    for term, quoted in terms:
        alternatives = (term,)
        if not quoted:
            alternatives = next((group for group in SYNONYM_GROUPS if term in group), alternatives)
        queryset = queryset.filter(public_term_query(alternatives))
    return queryset.annotate(
        _search_rank=Case(
            When(Q(display_name__iexact=query) | Q(name__iexact=query), then=Value(0)),
            When(
                Q(search_aliases__iexact=query)
                | Q(search_aliases__istartswith=f"{query}\n")
                | Q(search_aliases__iendswith=f"\n{query}")
                | Q(search_aliases__icontains=f"\n{query}\n"),
                then=Value(1),
            ),
            When(Q(display_name__istartswith=query) | Q(name__istartswith=query), then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by("_search_rank", PUBLIC_NAME_ORDER, "pk")
