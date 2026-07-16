from django.test import TestCase
from django.urls import reverse


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
