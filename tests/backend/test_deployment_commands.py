from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase


class EnsureAdminUserTests(TestCase):
    def test_creates_initial_administrator_from_environment(self):
        environment = {
            "DJANGO_SUPERUSER_USERNAME": "site-admin",
            "DJANGO_SUPERUSER_EMAIL": "admin@example.com",
            "DJANGO_SUPERUSER_PASSWORD": "a-strong-initial-password",
        }

        with patch.dict("os.environ", environment, clear=False):
            call_command("ensure_admin_user", verbosity=0)

        user = get_user_model().objects.get(username="site-admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.email, "admin@example.com")
        self.assertTrue(user.check_password("a-strong-initial-password"))

    def test_existing_administrator_is_never_changed(self):
        user = get_user_model().objects.create_superuser(
            username="existing-admin",
            email="existing@example.com",
            password="existing-password",
        )
        environment = {
            "DJANGO_SUPERUSER_USERNAME": "replacement-admin",
            "DJANGO_SUPERUSER_EMAIL": "replacement@example.com",
            "DJANGO_SUPERUSER_PASSWORD": "replacement-password",
        }
        output = StringIO()

        with patch.dict("os.environ", environment, clear=False):
            call_command("ensure_admin_user", stdout=output, verbosity=0)

        user.refresh_from_db()
        self.assertTrue(user.check_password("existing-password"))
        self.assertFalse(get_user_model().objects.filter(username="replacement-admin").exists())
        self.assertIn("no account changes", output.getvalue())

    def test_missing_initial_credentials_fails_instead_of_deploying_locked_site(self):
        with patch.dict(
            "os.environ",
            {
                "DJANGO_SUPERUSER_USERNAME": "",
                "DJANGO_SUPERUSER_PASSWORD": "",
            },
            clear=False,
        ):
            with self.assertRaisesMessage(CommandError, "No administrator exists"):
                call_command("ensure_admin_user", verbosity=0)
