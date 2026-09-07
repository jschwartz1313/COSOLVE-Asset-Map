import json
from io import StringIO
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.assets.models import Asset
from scripts.build_real_asset_catalog import apply_reviewed_corrections

MANIFEST = settings.BASE_DIR / "data" / "airport_website_corrections_2026_09_06.json"
DIRECTORY = "https://doav.virginia.gov/airport-directory/"
SPONSORS = "https://doav.virginia.gov/airport_sponsors/"


class AirportWebsiteCatalogTests(SimpleTestCase):
    def test_every_catalog_airport_has_a_reviewed_decision(self):
        manifest = json.loads(MANIFEST.read_text())
        records = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())[
            "records"
        ]
        airports = {r["name"]: r for r in records if r["provenance"] == "faa-public-airport"}
        decisions = manifest["corrections"] + manifest["unresolved"]
        self.assertEqual(len(decisions), len(airports))
        self.assertEqual({r["name"] for r in decisions}, set(airports))
        self.assertEqual(len({r["identifier"] for r in decisions}), len(airports))
        self.assertEqual(len(manifest["corrections"]), 54)
        for correction in manifest["corrections"]:
            with self.subTest(airport=correction["name"]):
                record = airports[correction["name"]]
                url = correction["after"]["website_url"]
                self.assertEqual(correction["provenance"], "faa-public-airport")
                self.assertEqual(set(correction["after"]), {"website_url", "contact_url"})
                self.assertNotEqual(url, DIRECTORY)
                self.assertEqual(record["website_url"], url)
                self.assertEqual(record["contact_url"], correction["after"]["contact_url"])
                self.assertIn(url, {s["url"] for s in record["sources"]})
                self.assertTrue(
                    any(s["title"].startswith("FAA airport record") for s in record["sources"])
                )
                # Campbell Field has an operator-maintained HTTP site, not a working TLS site.
                if urlparse(url).scheme != "https":
                    self.assertEqual(correction["identifier"], "9VG")
                    self.assertIn("HTTP only", correction["reason"])
        for unresolved in manifest["unresolved"]:
            self.assertTrue(unresolved["reason"])
            self.assertEqual(airports[unresolved["name"]]["website_url"], DIRECTORY)

    def test_catalog_regeneration_retains_airport_links_without_duplicate_sources(self):
        records = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())[
            "records"
        ]
        manifest = json.loads(MANIFEST.read_text())
        by_name = {r["name"]: r for r in records}
        for correction in manifest["corrections"]:
            record = by_name[correction["name"]]
            record.update(correction["before"])
            record["sources"] = [
                s for s in record["sources"] if s["url"] != correction["after"]["website_url"]
            ]
        apply_reviewed_corrections(records)
        apply_reviewed_corrections(records)
        for correction in manifest["corrections"]:
            record = by_name[correction["name"]]
            url = correction["after"]["website_url"]
            self.assertEqual(record["website_url"], url)
            self.assertEqual(sum(s["url"] == url for s in record["sources"]), 1)


@override_settings(REQUIRE_SITE_LOGIN=False)
class AirportWebsiteDeploymentTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            name="Accomack County",
            record_type="infrastructure",
            short_description="Public-use airport in Melfa.",
            unmanned_systems_relevance="Supporting aviation infrastructure.",
            status="source-backed",
            visibility="public",
            website_url=DIRECTORY,
            contact_url=SPONSORS,
            internal_notes="Catalog provenance: faa-public-airport.",
        )
        self.url = "https://www.accomack.gov/279/Airport"

    def apply(self):
        call_command("apply_catalog_corrections", corrections=MANIFEST, stdout=StringIO())
        self.asset.refresh_from_db()

    def test_update_is_visible_and_does_not_verify_the_asset_or_source(self):
        self.apply()
        self.apply()
        self.assertEqual(self.asset.website_url, self.url)
        self.assertEqual(self.asset.contact_url, self.url)
        self.assertEqual(self.asset.status, "source-backed")
        self.assertIsNone(self.asset.reviewed_at)
        self.assertEqual(self.asset.sources.count(), 1)
        self.assertEqual(self.asset.sources.get().verification_status, "unreviewed")
        self.assertEqual(self.asset.review_comments.count(), 1)
        response = self.client.get(f"/assets/{self.asset.slug}/")
        self.assertContains(response, f'href="{self.url}"')
        self.assertNotContains(response, f'href="{DIRECTORY}"')

    def test_custom_contact_link_preserves_both_staff_values(self):
        self.asset.contact_url = "https://example.org/staff-reviewed-contact"
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.website_url, DIRECTORY)
        self.assertEqual(self.asset.contact_url, "https://example.org/staff-reviewed-contact")
        self.assertFalse(self.asset.sources.exists())

    def test_staff_managed_record_is_not_overwritten(self):
        self.asset._history_user = get_user_model().objects.create_user("airport-editor")
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.website_url, DIRECTORY)
        self.assertFalse(self.asset.sources.exists())

    def test_rejected_destination_source_prevents_reintroduction(self):
        self.asset.sources.create(
            title="Rejected airport link", url=self.url, verification_status="rejected"
        )
        self.apply()
        self.assertEqual(self.asset.website_url, DIRECTORY)
        self.assertEqual(self.asset.sources.get().verification_status, "rejected")
