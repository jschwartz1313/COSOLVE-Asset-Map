"""Bounded word/phrase search over public asset information."""

from django.db.models import Case, Exists, IntegerField, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce, Lower, NullIf
from django.utils.text import smart_split, unescape_string_literal

from apps.assets.models import Asset

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
    "strategic_categories__name",
    "platform_domains__name",
    "capabilities__name",
    "missions__name",
)
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


def public_term_query(term):
    condition = Q()
    for field in SEARCH_FIELDS:
        condition |= Q(**{f"{field}__icontains": term})
    condition |= Q(sources__title__icontains=term, sources__is_public=True)
    for direction, target in (("outgoing", "to"), ("incoming", "from")):
        prefix = f"{direction}_relationships__"
        asset_path = f"{prefix}{target}_asset__"
        related_name = Q(**{f"{asset_path}name__icontains": term}) | Q(
            **{f"{asset_path}display_name__icontains": term}
        )
        condition |= related_name & Q(
            **{
                f"{prefix}is_public": True,
                f"{asset_path}pk__in": Asset.public.values("pk"),
            }
        )
    return condition


def apply_search(queryset, query):
    terms = search_terms(query)
    if terms is None:
        return queryset.none()
    for term, quoted in terms:
        alternatives = (term,)
        if not quoted:
            alternatives = next((group for group in SYNONYM_GROUPS if term in group), alternatives)
        condition = Q()
        for alternative in alternatives:
            condition |= public_term_query(alternative)
        # Independent EXISTS clauses allow words in different sources/tags without join fan-out.
        matching = Asset.objects.filter(pk=OuterRef("pk")).filter(condition)
        queryset = queryset.filter(Exists(matching))
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
