"""Keep Virginia editing available without exposing unpublished peer inventories."""

from django.contrib.admin.utils import NestedObjects
from django.db import router

from .access import (
    can_access_all_states,
    inventory_object_allowed,
    inventory_state_fields,
    restrict_peer_assets,
)


class InventoryAdminAccessMixin:
    def get_queryset(self, request):
        return restrict_peer_assets(super().get_queryset(request), request.user)

    def has_view_permission(self, request, obj=None):
        return inventory_object_allowed(obj, request.user) and super().has_view_permission(
            request, obj,
        )

    def has_change_permission(self, request, obj=None):
        return inventory_object_allowed(obj, request.user) and super().has_change_permission(
            request, obj,
        )

    def has_delete_permission(self, request, obj=None):
        return inventory_object_allowed(obj, request.user) and super().has_delete_permission(
            request, obj,
        )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if (not can_access_all_states(request.user)
                and "state" in inventory_state_fields(self.model)):
            return tuple(dict.fromkeys((*fields, "state")))
        return fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        queryset = kwargs.get("queryset")
        if queryset is None:
            queryset = db_field.remote_field.model._default_manager.all()
        kwargs["queryset"] = restrict_peer_assets(queryset, request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class InventoryHistoryAdminMixin(InventoryAdminAccessMixin):
    def get_history_queryset(self, request, *args, **kwargs):
        return restrict_peer_assets(
            super().get_history_queryset(request, *args, **kwargs), request.user,
        )

    def has_view_history_or_change_history_permission(self, request, obj=None):
        return inventory_object_allowed(obj, request.user) and (
            super().has_view_history_or_change_history_permission(request, obj)
        )

    def has_view_history_permission(self, request, obj=None):
        return inventory_object_allowed(obj, request.user) and (
            super().has_view_history_permission(request, obj)
        )

    def has_change_history_permission(self, request, obj=None):
        return inventory_object_allowed(obj, request.user) and (
            super().has_change_history_permission(request, obj)
        )

    def get_deleted_objects(self, objs, request):
        if not can_access_all_states(request.user):
            objs = list(objs)
            collector = NestedObjects(using=router.db_for_write(self.model))
            collector.collect(objs)
            related = [obj for values in collector.data.values() for obj in values]
            related.extend(collector.protected)
            if any(not inventory_object_allowed(obj, request.user) for obj in related):
                return [], {}, {"records outside your inventory access"}, []
        return super().get_deleted_objects(objs, request)
