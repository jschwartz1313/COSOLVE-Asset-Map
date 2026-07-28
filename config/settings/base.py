import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "simple_history",
    "apps.core",
    "apps.catalog",
    "apps.assets",
    "apps.sources",
    "apps.api",
    "apps.imports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "apps.core.middleware.OptionalSiteLoginMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.map_settings",
                "apps.core.context_processors.account_settings",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

BASEMAP_TILE_URL = os.getenv(
    "BASEMAP_TILE_URL", "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
)
BASEMAP_ATTRIBUTION = os.getenv("BASEMAP_ATTRIBUTION", "&copy; OpenStreetMap contributors")
DEFAULT_MAP_LAT = float(os.getenv("DEFAULT_MAP_LAT", "37.5"))
DEFAULT_MAP_LON = float(os.getenv("DEFAULT_MAP_LON", "-78.7"))
DEFAULT_MAP_ZOOM = int(os.getenv("DEFAULT_MAP_ZOOM", "7"))
PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "http://127.0.0.1:8000")
STALE_VERIFICATION_DAYS = int(os.getenv("STALE_VERIFICATION_DAYS", "180"))
REQUIRE_SITE_LOGIN = os.getenv("REQUIRE_SITE_LOGIN", "false").lower() == "true"
PUBLIC_REGION_SLUG = os.getenv("PUBLIC_REGION_SLUG", "").strip()
PUBLIC_SCOPE_NAME = os.getenv("PUBLIC_SCOPE_NAME", "").strip() or (
    PUBLIC_REGION_SLUG.replace("-", " ").title() if PUBLIC_REGION_SLUG else "Virginia"
)
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/map/"
LOGOUT_REDIRECT_URL = "/login/"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)
ACCOUNT_ADAPTER = "apps.core.adapters.ClosedAccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.core.adapters.InvitedUserSocialAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m",
    "login": "20/5m",
    "reset_password": "5/h",
    "reset_password_email": "5/h",
}
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_ALLOW_UNVERIFIED_EMAIL = True

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "COSOLVE Asset Map <noreply@localhost>")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"

OIDC_SERVER_URL = os.getenv("OIDC_SERVER_URL", "").strip()
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "").strip()
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "").strip()
OIDC_ENABLED = bool(OIDC_SERVER_URL and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET)
if OIDC_ENABLED:
    SOCIALACCOUNT_PROVIDERS = {
        "openid_connect": {
            "APPS": [
                {
                    "provider_id": "cosolve-sso",
                    "name": os.getenv("OIDC_PROVIDER_NAME", "Organization sign in"),
                    "client_id": OIDC_CLIENT_ID,
                    "secret": OIDC_CLIENT_SECRET,
                    "settings": {"server_url": OIDC_SERVER_URL},
                }
            ]
        }
    }

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
