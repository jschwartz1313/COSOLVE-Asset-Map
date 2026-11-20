from functools import lru_cache
from types import ModuleType

from django.conf import settings
from django.http import HttpResponseNotFound
from django.urls import get_urlconf, include, path, set_urlconf

from apps.assets.access import can_preview_peer_states
from apps.assets.geography import BY_SLUG, current_state, internal_preview


@lru_cache(maxsize=16)
def state_urlconf(slug):
    from config.urls import urlpatterns

    module = ModuleType(f"state_urls_{slug}")
    prefix = f"states/{slug}/"
    # Scoped instances go first so reverse() keeps navigation and APIs in this state.
    module.urlpatterns = [
        path(prefix + "api/", include("apps.api.urls")),
        path(prefix + "admin/imports/", include("apps.imports.urls")),
        path(prefix, include("apps.core.urls")),
        *urlpatterns,
    ]
    return module


class StateScopeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def unavailable():
        response = HttpResponseNotFound("State not available.")
        response["Cache-Control"] = "private, no-store"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    def __call__(self, request):
        state = BY_SLUG["virginia"]
        is_scoped = request.path_info.startswith("/states/")
        preview = False
        if is_scoped:
            state = BY_SLUG.get(request.path_info.split("/")[2])
            if not state or state.code == "VA":
                return self.unavailable()
            preview = can_preview_peer_states(request.user)
            if not settings.MULTISTATE_PUBLIC and not preview:
                return self.unavailable()
            request.urlconf = state_urlconf(state.slug)
        # Administrative work remains cross-state; public endpoints are always scoped.
        administrative = request.path_info.startswith(("/admin/", "/auth/"))
        cross_state_admin = administrative and can_preview_peer_states(request.user)
        scope = (
            None if cross_state_admin and request.path_info != "/admin/imports/export/" else state
        )
        request.inventory_state = state
        request.inventory_preview = bool(is_scoped and preview)
        old_urlconf = get_urlconf()
        token = current_state.set(scope)
        preview_token = internal_preview.set(bool(is_scoped and preview))
        try:
            response = self.get_response(request)
            if is_scoped:
                response["Cache-Control"] = "private, no-store"
                response["X-Robots-Tag"] = "noindex, nofollow"
            return response
        finally:
            current_state.reset(token)
            internal_preview.reset(preview_token)
            set_urlconf(old_urlconf)
