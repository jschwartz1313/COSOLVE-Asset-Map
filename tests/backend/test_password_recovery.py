import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    REQUIRE_SITE_LOGIN=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PasswordRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = get_user_model().objects.create_user(
            "recovery-user", "recovery@example.com", "original-test-password"
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="")
    def test_unconfigured_email_has_clear_message_and_no_submission_form(self):
        response = self.client.get(reverse("account_reset_password"))
        self.assertContains(response, "Password-reset email is not available yet")
        self.assertNotContains(response, "Send reset link")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="")
    def test_unconfigured_email_rejects_posts_equally_for_known_and_unknown_accounts(self):
        for email in [self.user.email, "unknown@example.com"]:
            with self.subTest(email=email):
                response = self.client.post(reverse("account_reset_password"), {"email": email})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Password-reset email is not available yet")
        self.assertEqual(len(mail.outbox), 0)

    def test_email_link_resets_password_and_cannot_be_reused(self):
        response = self.client.post(reverse("account_reset_password"), {"email": self.user.email})
        self.assertRedirects(response, reverse("account_reset_password_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        reset_url = re.search(r"https?://[^\s]+/password/reset/key/[^\s]+", mail.outbox[0].body)[0]
        response = self.client.get(reset_url, follow=True)
        self.assertContains(response, "New Password", html=False)
        response = self.client.post(response.request["PATH_INFO"], {
            "password1": "a-new-strong-test-password-2983",
            "password2": "a-new-strong-test-password-2983",
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-new-strong-test-password-2983"))
        self.client.logout()
        response = self.client.get(reset_url, follow=True)
        self.assertContains(response, "Request another link")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST="")
    def test_admin_invitation_reports_missing_email_configuration(self):
        administrator = get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "test-admin-password"
        )
        self.client.force_login(administrator)
        response = self.client.post(reverse("admin:auth_user_changelist"), {
            "action": "send_account_setup_email", "_selected_action": [self.user.pk],
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email delivery is not configured")
        self.assertEqual(len(mail.outbox), 0)
