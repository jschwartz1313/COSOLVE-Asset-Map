import os
import runpy
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.test import SimpleTestCase


class BasemapSettingsTests(SimpleTestCase):
    def load_settings(self, **environment):
        with patch.dict(os.environ, environment, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(str(settings.BASE_DIR / "config/settings/base.py"))

    def test_key_is_added_to_carto_light_only(self):
        configured = self.load_settings(CARTO_BASEMAP_API_KEY="  test+key&value  ")
        url = configured["LIGHT_BASEMAP_TILE_URL"]
        self.assertEqual(urlsplit(url).hostname, "{s}.basemaps.cartocdn.com")
        self.assertEqual(parse_qs(urlsplit(url).query), {"key": ["test+key&value"]})
        self.assertIn("/{z}/{x}/{y}{r}.png", url)
        self.assertNotIn("key=", configured["BASEMAP_TILE_URL"])
        self.assertNotIn("key=", configured["IMAGERY_BASEMAP_TILE_URL"])
        self.assertIn("carto.com/attributions", configured["LIGHT_BASEMAP_ATTRIBUTION"])

    def test_custom_provider_does_not_receive_carto_key(self):
        custom = "https://tiles.example.org/light/{z}/{x}/{y}.png?token=provider-test"
        configured = self.load_settings(
            CARTO_BASEMAP_API_KEY="test-carto-key", LIGHT_BASEMAP_TILE_URL=custom
        )
        self.assertEqual(configured["LIGHT_BASEMAP_TILE_URL"], custom)

    def test_empty_override_uses_carto(self):
        configured = self.load_settings(
            CARTO_BASEMAP_API_KEY="test-carto-key", LIGHT_BASEMAP_TILE_URL=""
        )
        self.assertIn("key=test-carto-key", configured["LIGHT_BASEMAP_TILE_URL"])

    def test_no_key_is_not_replaced_with_an_invalid_placeholder(self):
        configured = self.load_settings()
        self.assertNotIn("?", configured["LIGHT_BASEMAP_TILE_URL"])
