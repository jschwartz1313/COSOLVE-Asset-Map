import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(
    REQUIRE_SITE_LOGIN=True,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "shared-account-login-tests",
        }
    },
)
class SharedAccountLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user(
            "shared-viewer", password="test-only-password"
        )

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def sign_in(self, client, password="test-only-password"):
        return client.post(
            reverse("login"), {"login": self.viewer.username, "password": password}
        )

    def test_only_general_login_limit_increases(self):
        self.assertEqual(settings.ACCOUNT_RATE_LIMITS["login"], "40/5m")
        self.assertEqual(settings.ACCOUNT_RATE_LIMITS["login_failed"], "5/5m")
        self.assertEqual(settings.ACCOUNT_RATE_LIMITS["reset_password"], "5/h")
        self.assertEqual(settings.ACCOUNT_RATE_LIMITS["reset_password_email"], "5/h")

    def test_forty_independent_sessions_then_rate_limit_without_disconnecting_viewers(self):
        clients = [Client() for _ in range(40)]
        for index, client in enumerate(clients, 1):
            with self.subTest(sign_in=index):
                self.assertRedirects(
                    self.sign_in(client), reverse("core:map"), fetch_redirect_response=False
                )
                self.assertEqual(client.session["_auth_user_id"], str(self.viewer.pk))
        self.assertEqual(len({client.session.session_key for client in clients}), 40)
        self.assertEqual(self.sign_in(Client()).status_code, 429)
        for client in clients:
            self.assertEqual(client.get(reverse("core:map")).status_code, 200)

        clients[0].post(reverse("logout"))
        self.assertNotIn("_auth_user_id", clients[0].session)
        self.assertEqual(clients[1].get(reverse("core:map")).status_code, 200)
        self.assertRedirects(
            self.sign_in(Client(REMOTE_ADDR="198.51.100.2")),
            reverse("core:map"), fetch_redirect_response=False,
        )
        with patch("allauth.core.internal.ratelimit.time.time", return_value=time.time() + 301):
            self.assertRedirects(
                self.sign_in(Client()), reverse("core:map"), fetch_redirect_response=False
            )

    def test_failed_password_protection_still_blocks_after_five_failures(self):
        for _ in range(5):
            client = Client()
            self.sign_in(client, password="incorrect")
            self.assertNotIn("_auth_user_id", client.session)
        blocked = Client()
        self.sign_in(blocked)
        self.assertNotIn("_auth_user_id", blocked.session)
        with patch("allauth.core.internal.ratelimit.time.time", return_value=time.time() + 301):
            self.assertRedirects(
                self.sign_in(Client()), reverse("core:map"), fetch_redirect_response=False
            )
