import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

for platform_host_variable in ("RENDER_EXTERNAL_HOSTNAME", "RAILWAY_PUBLIC_DOMAIN"):
    platform_host = os.getenv(platform_host_variable, "").strip()
    if platform_host and platform_host not in ALLOWED_HOSTS:  # noqa: F405
        ALLOWED_HOSTS.append(platform_host)  # noqa: F405

if SECRET_KEY == "local-development-only":  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
if not os.getenv("DATABASE_URL"):
    raise ImproperlyConfigured("DATABASE_URL must be set in production.")
if not ALLOWED_HOSTS or set(ALLOWED_HOSTS) <= {"localhost", "127.0.0.1"}:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must name the production host.")

DEBUG = False
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
}
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}

if os.getenv("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0.1)
