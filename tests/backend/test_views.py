from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.catalog.models import Region


class CoreViewTests(TestCase):
    def test_map_shell_renders(self):
        response = self.client.get(reverse("core:map"))
        self.assertContains(response, "Asset intelligence")
        self.assertContains(response, 'id="map"')
        self.assertContains(response, 'id="county-layer-toggle"')
        self.assertContains(response, 'id="state-boundary-toggle"')
        self.assertContains(response, "data-state-boundary-url=")

    def test_health_endpoint(self):
        self.assertEqual(self.client.get(reverse("core:health")).json(), {"status": "ok"})

    def test_directory_renders_without_javascript(self):
        response = self.client.get(reverse("core:directory"), {"q": "test"})
        self.assertContains(response, "Asset directory")
        self.assertContains(response, 'class="directory-list"')

    def test_regional_comparison_renders(self):
        Region.objects.create(name="Hampton Roads")
        Region.objects.create(name="Northern Virginia")
        response = self.client.get(reverse("core:region-compare"))
        self.assertContains(response, "Regional comparison")

    def test_about_data_renders(self):
        response = self.client.get(reverse("core:about-data"))
        self.assertContains(response, "About the data")


@override_settings(REQUIRE_SITE_LOGIN=True)
class PrivateSiteTests(TestCase):
    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("core:map"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('core:map')}",
            fetch_redirect_response=False,
        )

    def test_health_check_remains_public(self):
        self.assertEqual(self.client.get(reverse("core:health")).status_code, 200)

    def test_authenticated_user_can_open_site(self):
        user = get_user_model().objects.create_user("member", password="test-password")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("core:map")).status_code, 200)
