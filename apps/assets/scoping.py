from django.conf import settings
from django.db.models import Q

from .geography import current_state


def public_region_slug():
    state = current_state.get()
    if state and state.code != "VA":
        return ""
    return settings.PUBLIC_REGION_SLUG


def apply_public_scope(queryset, prefix=""):
    state = current_state.get()
    if state:
        queryset = queryset.filter(**{f"{prefix}state": state.code})
    slug = public_region_slug()
    if not slug:
        return queryset
    return queryset.filter(**{f"{prefix}region__slug": slug})


def public_scope_q(prefix=""):
    state = current_state.get()
    scope = Q(**{f"{prefix}state": state.code}) if state else Q()
    slug = public_region_slug()
    if not slug:
        return scope
    return scope & Q(**{f"{prefix}region__slug": slug})


def asset_is_in_public_scope(asset):
    state = current_state.get()
    if state and asset.state != state.code:
        return False
    slug = public_region_slug()
    return not slug or bool(asset.region and asset.region.slug == slug)
