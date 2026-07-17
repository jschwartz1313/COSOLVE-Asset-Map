from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Region


class CoreViewTests(TestCase):
    def test_map_shell_renders(self):
        response = self.client.get(reverse("core:map"))
        self.assertContains(response, "Asset intelligence")
        self.assertContains(response, 'id="map"')

    def test_health_endpoint(self):
        self.assertEqual(self.client.get(reverse("core:health")).json(), {"status": "ok"})

    def test_directory_renders_without_javascript(self):
        response = self.client.get(reverse("core:directory"), {"q": "test"})
        self.assertContains(response, "Asset directory")

    def test_regional_comparison_renders(self):
        Region.objects.create(name="Hampton Roads")
        Region.objects.create(name="Northern Virginia")
        response = self.client.get(reverse("core:region-compare"))
        self.assertContains(response, "Regional comparison")

    def test_about_data_renders(self):
        response = self.client.get(reverse("core:about-data"))
        self.assertContains(response, "About the data")
