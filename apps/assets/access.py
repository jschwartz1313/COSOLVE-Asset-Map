"""Account-level access to the unpublished benchmark-state inventories."""

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

STATE_FIELDS = {
    "assets.asset": ("state",),
    "assets.relationship": ("from_asset__state", "to_asset__state"),
    "assets.assetreviewcomment": ("asset__state",),
    "assets.duplicatecandidate": ("left_asset__state", "right_asset__state"),
    "assets.updatesubmission": ("state",),
    "assets.operatorreview": ("asset__state",),
    "assets.sitediagram": ("asset__state",),
    "assets.manufacturingprofile": ("asset__state",),
    "assets.savedview": ("state",),
    "sources.source": ("asset__state",),
    "catalog.region": ("state",),
}


def can_preview_peer_states(user):
    return bool(
        user.is_authenticated and user.is_active
        and user.username in settings.MULTISTATE_PREVIEW_USERS
        and user.is_staff and user.has_perm("assets.view_asset")
    )


def can_access_all_states(user):
    return settings.MULTISTATE_PUBLIC or can_preview_peer_states(user)


def inventory_model_label(model):
    opts = model._meta
    return f"{opts.app_label}.{opts.model_name.removeprefix('historical')}"


def inventory_state_fields(model):
    return STATE_FIELDS.get(inventory_model_label(model), ())


def restrict_peer_assets(queryset, user):
    if can_access_all_states(user):
        return queryset
    queryset = queryset.filter(**{field: "VA" for field in inventory_state_fields(queryset.model)})
    if inventory_model_label(queryset.model) == "assets.updatesubmission":
        queryset = queryset.filter(Q(asset__isnull=True) | Q(asset__state="VA"))
    return queryset


def inventory_object_allowed(obj, user):
    if obj is None or can_access_all_states(user):
        return True
    for path in inventory_state_fields(type(obj)):
        value = obj
        try:
            for part in path.split("__"):
                value = getattr(value, part, None)
        except ObjectDoesNotExist:
            return False
        if value != "VA":
            return False
    if inventory_model_label(type(obj)) == "assets.updatesubmission" and obj.asset_id:
        try:
            return obj.asset.state == "VA"
        except ObjectDoesNotExist:
            return False
    return True
