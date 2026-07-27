from django.conf import settings
from django.db.models import Q


def public_region_slug():
    return settings.PUBLIC_REGION_SLUG


def apply_public_scope(queryset, prefix=""):
    slug = public_region_slug()
    if not slug:
        return queryset
    return queryset.filter(**{f"{prefix}region__slug": slug})


def public_scope_q(prefix=""):
    slug = public_region_slug()
    if not slug:
        return Q()
    return Q(**{f"{prefix}region__slug": slug})


def asset_is_in_public_scope(asset):
    slug = public_region_slug()
    return not slug or bool(asset.region and asset.region.slug == slug)
