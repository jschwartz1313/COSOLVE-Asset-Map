import json
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.assets.models import Asset
from apps.catalog.models import Region
from apps.core.views import region_metrics
from scripts.audit_catalog_sources import classify_response

CORRECTIONS = settings.BASE_DIR / "data/asset_website_corrections_2026_10_06.json"


class SourceResponseClassificationTests(SimpleTestCase):
    def response(self, **overrides):
        result = {"url": "https://example.org/source", "http_status": 200, "title": "", "text": ""}
        result.update(overrides)
        return classify_response(result)

    def test_arcgis_rate_limit_in_success_response_is_inconclusive(self):
        self.assertEqual(self.response(
            url="https://services.arcgis.com/FeatureServer/0/query",
            text=json.dumps({"error": {"code": 429, "message": "Too many requests"}}),
        ), "access_blocked_or_rate_limited")

    def test_arcgis_error_and_valid_payload_are_distinguished(self):
        url = "https://services.arcgis.com/FeatureServer/0/query"
        self.assertEqual(self.response(url=url, text='{"error":{"code":400}}'),
                         "api_error_in_success_response")
        self.assertEqual(self.response(url=url, text='{"features":[],"code":200}'), "reachable")
        self.assertEqual(self.response(url=url, text="Not JSON"), "reachable")

    def test_human_verification_and_real_not_found_are_distinguished(self):
        self.assertEqual(self.response(http_status=405, title="Human Verification"),
                         "access_blocked_or_rate_limited")
        self.assertEqual(self.response(http_status=404), "http_not_found")
        self.assertEqual(self.response(http_status=503), "server_error")
        self.assertEqual(self.response(final_url="https://example.org/"),
                         "redirected_to_homepage_review")

    def test_login_redirect_is_not_treated_as_readable_source_evidence(self):
        self.assertEqual(self.response(
            final_url="https://example.org/login/?next=%2Fsource", title="Sign in",
        ), "access_blocked_or_rate_limited")


class MappedCoverageTests(TestCase):
    def test_site_quality_counts_require_both_coordinates(self):
        region = Region.objects.create(name="Hampton Roads")
        for name, latitude, longitude in (("Mapped site", 36.8, -76.2),
                                          ("Unmapped site", None, None)):
            Asset.objects.create(
                name=name, record_type="facility", short_description="Test site",
                unmanned_systems_relevance="Test site", region=region,
                status="source-backed", visibility="public", location_precision="site",
                latitude=latitude, longitude=longitude,
            )
        quality = region_metrics(region)["quality_metrics"][-1]
        self.assertEqual(quality["count"], 1)
        self.assertEqual(quality["rate"], 50)
        user = get_user_model().objects.create_superuser("coverage-review", password="test")
        self.client.force_login(user)
        rows = self.client.get(reverse("imports:data-quality")).context["region_coverage"]
        self.assertEqual(rows[0]["located"], 1)
        self.assertEqual(rows[0]["location_rate"], 50)


class OctoberWebsiteCorrectionTests(TestCase):
    def setUp(self):
        self.changes = json.loads(CORRECTIONS.read_text())["corrections"]
        catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        names = {c["name"] for c in self.changes}
        records = deepcopy([r for r in catalog["records"] if r["name"] in names])
        by_name = {r["name"]: r for r in records}
        for c in self.changes:
            r = by_name[c["name"]]
            for field, value in c["after"].items():
                self.assertEqual(r[field], value)
            r.update(c["before"])
            additions = c.get("add_sources", []) + [
                x["source"] for x in c.get("replace_sources", [])
            ]
            new_urls = {s["url"] for s in additions}
            r["sources"] = [s for s in r["sources"] if s["url"] not in new_urls]
            for replacement in c.get("replace_sources", []):
                r["sources"].append({"title": "Old public source", "url": replacement["old_url"]})
        with TemporaryDirectory() as directory:
            path = Path(directory) / "old-catalog.json"
            path.write_text(json.dumps({"records": records, "relationships": []}))
            call_command("seed_real_data", catalog=path, stdout=StringIO())

    def apply(self):
        out = StringIO()
        call_command("apply_catalog_corrections", corrections=CORRECTIONS, stdout=out)
        return out.getvalue()

    def test_repairs_are_idempotent_and_preserve_obsolete_source_history(self):
        self.assertIn("Applied 9", self.apply())
        for c in self.changes:
            asset = Asset.objects.get(name=c["name"])
            for field, value in c["after"].items():
                self.assertEqual(getattr(asset, field), value)
            for replacement in c.get("replace_sources", []):
                old = asset.sources.get(url=replacement["old_url"])
                self.assertFalse(old.is_public)
                self.assertEqual(old.link_review_status, "needs-replacement")
                self.assertTrue(old.history.exists())
                self.assertTrue(asset.sources.filter(
                    url=replacement["source"]["url"], is_public=True,
                ).exists())
            asset.full_clean()
        before = Asset.history.count()
        self.assertIn("Applied 0", self.apply())
        self.assertEqual(before, Asset.history.count())
        dms = Asset.objects.get(name="Defense Maritime Solutions Chesapeake Manufacturing Facility")
        self.assertIsNone(dms.reviewed_at)
        self.assertEqual(dms.status, "source-backed")
        self.assertIn("not been confirmed", dms.current_activity)

    def test_staff_values_are_preserved_and_generated_legacy_baseline_is_accepted(self):
        park = Asset.objects.get(name="Virginia Tech Drone Park")
        park.contact_url = "https://example.org/staff-contact"
        park.save()
        ctrc = Asset.objects.get(name="Virginia Tech Counter UAS Research and Testing Center")
        ctrc.website_url = "https://news.vt.edu/articles/2025/04/research-counteruascenter.html"
        ctrc.save()
        self.assertIn("Applied 8", self.apply())
        park.refresh_from_db()
        ctrc.refresh_from_db()
        self.assertEqual(park.contact_url, "https://example.org/staff-contact")
        self.assertEqual(ctrc.website_url, "https://nationalsecurity.vt.edu/research/msd.html")
