from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect


class OptionalSiteLoginMiddleware:
    public_prefixes = ("/accounts/", "/admin/login/", "/static/", "/health/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.REQUIRE_SITE_LOGIN
            and not request.user.is_authenticated
            and not request.path.startswith(self.public_prefixes)
        ):
            return redirect(f"{settings.LOGIN_URL}?{urlencode({'next': request.get_full_path()})}")
        return self.get_response(request)
