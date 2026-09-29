import json
from copy import deepcopy
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.api.query import filter_public_assets
from apps.assets.management.commands.apply_catalog_corrections import ALLOWED_FIELDS
from apps.assets.models import Asset
from scripts.build_real_asset_catalog import (
    AEROSPACE_REPORT_CORRECTIONS_PATH,
    apply_reviewed_corrections,
    validate,
)

CATALOG = settings.BASE_DIR / "data/virginia_real_assets.json"


class AerospaceReportCatalogTests(SimpleTestCase):
    def test_evidence_matches_catalog_without_changing_identity_or_taxonomy(self):
        manifest = json.loads(AEROSPACE_REPORT_CORRECTIONS_PATH.read_text())
        self.assertEqual(len(manifest["corrections"]), 1)
        change = manifest["corrections"][0]
        catalog = json.loads(CATALOG.read_text())
        record = next(r for r in catalog["records"] if r["name"] == change["name"])
        self.assertEqual(set(change["before"]), set(change["after"]))
        self.assertTrue(set(change["after"]) <= ALLOWED_FIELDS)
        self.assertTrue(change["review_required"])
        for field, value in change["after"].items():
            self.assertEqual(record[field], value)
        for baseline in change["accepted_baselines"]:
            self.assertEqual(set(baseline), set(change["before"]))
            self.assertEqual(
                {key for key in baseline if baseline[key] != change["before"][key]},
                {"website_url"},
            )
        self.assertEqual(record["address_line"], "7499 Pine Stake Road")
        self.assertEqual(record["latitude"], 38.30252)
        self.assertEqual(record["longitude"], -77.930442)
        self.assertIn("Supporting ecosystem asset", record["strategic_categories"])
        self.assertEqual(record["activity_status"], "active")
        self.assertEqual(record["development_status"], "operational")
        self.assertIn("planned", record["development_notes"])
        self.assertIn("not confirmed completed", record["current_activity"])
        self.assertIn("not public drone flight ranges", record["overview"])
        self.assertIsNone(record.get("test_runway_length_ft"))
        self.assertIsNone(record.get("available_acreage"))
        urls = {source["url"] for source in record["sources"]}
        for field in ("website_url", "activity_source_url", "development_source_url",
                      "test_source_url"):
            self.assertIn(record[field], urls)
        self.assertTrue(all("l3harris.com" in s["url"] for s in change["add_sources"]))
        self.assertFalse(any("Avio" in r["name"] for r in catalog["records"]))
        validate(catalog["records"], [
            (r["from"], r["type"], r["to"]) for r in catalog["relationships"]
        ])

    def test_regeneration_and_source_additions_are_idempotent(self):
        records = deepcopy(json.loads(CATALOG.read_text())["records"])
        expected = json.dumps(records, sort_keys=True)
        apply_reviewed_corrections(records)
        apply_reviewed_corrections(records)
        self.assertEqual(json.dumps(records, sort_keys=True), expected)
        for record in records:
            urls = [source["url"] for source in record["sources"]]
            self.assertEqual(len(urls), len(set(urls)))


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class AerospaceReportDeploymentTests(TestCase):
    def setUp(self):
        self.change = json.loads(AEROSPACE_REPORT_CORRECTIONS_PATH.read_text())["corrections"][0]
        record = next(r for r in json.loads(CATALOG.read_text())["records"]
                      if r["name"] == self.change["name"])
        self.asset = Asset(
            name=record["name"], record_type="facility", status="published",
            visibility="public", short_description=record["short_description"],
            unmanned_systems_relevance=record["unmanned_systems_relevance"],
            activity_status="active", address_line=record["address_line"],
            city=record["city"], postal_code=record["postal_code"],
            location_precision="exact", last_verified_at=date(2026, 8, 30),
            reviewed_at=timezone.now(), internal_notes="Catalog provenance: curated-public-source.",
        )
        for field, value in self.change["before"].items():
            setattr(self.asset, field, Asset._meta.get_field(field).to_python(value))
        self.asset.save()
        self.new_urls = {s["url"] for s in self.change["add_sources"]}
        for source in record["sources"]:
            if source["url"] not in self.new_urls:
                self.asset.sources.create(
                    **source, is_public=True, verification_status="verified",
                    last_verified_at=date(2026, 8, 30),
                    notes="Catalog provenance: curated-public-source",
                )

    def apply(self):
        out = StringIO()
        call_command("apply_catalog_corrections",
                     corrections=AEROSPACE_REPORT_CORRECTIONS_PATH, stdout=out)
        self.asset.refresh_from_db()
        return out.getvalue()

    def test_updates_once_and_new_details_require_review(self):
        self.assertIn("Applied 1", self.apply())
        for field, expected in self.change["after"].items():
            value = getattr(self.asset, field)
            if isinstance(value, date):
                value = value.isoformat()
            self.assertEqual(value, expected)
        self.asset.full_clean()
        self.assertEqual(self.asset.status, "source-backed")
        self.assertIsNone(self.asset.reviewed_at)
        self.assertIsNone(self.asset.last_verified_at)
        self.assertEqual(self.asset.review_priority, "high")
        self.assertFalse(self.asset.sources.filter(url__in=self.new_urls)
                         .exclude(verification_status="unreviewed").exists())
        count = self.asset.history.count()
        self.assertIn("Applied 0", self.apply())
        self.assertEqual(self.asset.history.count(), count)
        self.assertEqual(self.asset.sources.filter(url__in=self.new_urls).count(), 3)

    def test_committed_pre_website_cleanup_baseline_is_accepted(self):
        self.asset.website_url = self.change["accepted_baselines"][0]["website_url"]
        self.asset.save()
        self.assertIn("Applied 1", self.apply())
        self.assertEqual(self.asset.website_url, self.change["after"]["website_url"])

    def test_staff_changes_and_conflicting_values_are_not_overwritten(self):
        for staff_context in (False, True):
            with self.subTest(staff_context=staff_context):
                self.asset.overview = "Locally confirmed instructions from a site representative."
                if staff_context:
                    self.asset._history_user = get_user_model().objects.create_user("gls-editor")
                self.asset.save()
                self.assertIn("preserved 1 conflicts", self.apply())
                self.assertEqual(self.asset.overview,
                                 "Locally confirmed instructions from a site representative.")
                self.assertEqual(self.asset.status, "published")
                self.assertFalse(self.asset.sources.filter(url__in=self.new_urls).exists())

    def test_private_record_and_hidden_source_are_preserved(self):
        self.asset.visibility = "internal"
        self.asset.status = "source-backed"
        self.asset.save()
        self.assertIn("preserved 1 conflicts", self.apply())
        self.assertEqual(self.asset.visibility, "internal")
        self.asset.visibility = "public"
        self.asset.status = "published"
        self.asset.save()
        self.asset.sources.create(**self.change["add_sources"][0], is_public=False)
        self.assertIn("preserved 1 conflicts", self.apply())
        self.assertEqual(self.asset.status, "published")
        self.assertEqual(self.asset.test_source_url, "")

    def test_historical_reviews_cannot_republish_new_details(self):
        self.apply()
        call_command("apply_catalog_reviews", reviews=settings.BASE_DIR
                     / "data/asset_editorial_reviews_2026_08_30_manufacturing.json",
                     stdout=StringIO())
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, "source-backed")
        self.assertIsNone(self.asset.reviewed_at)
        self.assertIsNone(self.asset.last_verified_at)

    def test_search_and_detail_expose_useful_terms_and_primary_links(self):
        self.apply()
        matches = filter_public_assets(QueryDict("q=VAPF"))
        self.assertTrue(matches.filter(pk=self.asset.pk).exists())
        response = self.client.get(f"/assets/{self.asset.slug}/")
        self.assertContains(response, "OSTF")
        self.assertContains(response, "OAPL")
        self.assertContains(response, "OATS")
        self.assertContains(response, "not confirmed completed capacity")
        self.assertContains(response, f'href="{self.change["after"]["website_url"]}"')
