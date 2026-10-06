import json
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Asset
from apps.sources.models import Source
from scripts.build_real_asset_catalog import apply_reviewed_corrections

MANIFEST = settings.BASE_DIR / "data/escc_grant_correction_2026_10_06.json"


class EsccGrantCorrectionTests(TestCase):
    def setUp(self):
        self.change = json.loads(MANIFEST.read_text())["corrections"][0]
        catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        self.catalog_records = catalog["records"]
        self.current_record = next(
            record for record in catalog["records"] if record["name"] == self.change["name"]
        )
        old_record = deepcopy(self.current_record)
        old_record.update(self.change["before"])
        grant_url = self.change["add_sources"][0]["url"]
        old_record["sources"] = [s for s in old_record["sources"] if s["url"] != grant_url]
        self.seed(old_record)
        self.asset = Asset.objects.get(name=self.change["name"])
        self.asset.status = Asset.Status.PUBLISHED
        self.asset.reviewed_at = timezone.now()
        self.asset.last_verified_at = timezone.localdate()
        self.asset.save()

    def seed(self, record):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"records": [record], "relationships": []}))
            call_command("seed_real_data", catalog=path, stdout=StringIO())

    def apply(self):
        output = StringIO()
        call_command("apply_catalog_corrections", corrections=MANIFEST, stdout=output)
        self.asset.refresh_from_db()
        return output.getvalue()

    def test_funded_plan_remains_pending_and_existing_course_evidence_is_retained(self):
        before_urls = set(self.asset.sources.values_list("url", flat=True))
        before_location = (self.asset.latitude, self.asset.longitude, self.asset.location_precision)
        self.assertIn("Applied 1", self.apply())
        self.assertEqual(self.asset.status, Asset.Status.SOURCE_BACKED)
        self.assertIsNone(self.asset.reviewed_at)
        self.assertIn("$788,700", self.asset.current_activity)
        self.assertIn("not confirmed", self.asset.current_activity)
        self.assertEqual(self.asset.activity_status, "")
        self.assertEqual(before_location, (
            self.asset.latitude, self.asset.longitude, self.asset.location_precision,
        ))
        self.assertTrue(before_urls <= set(self.asset.sources.values_list("url", flat=True)))
        self.assertEqual(self.asset.sources.count(), len(before_urls) + 1)
        self.asset.full_clean()
        history_count = self.asset.history.count()
        self.assertIn("Applied 0", self.apply())
        self.assertEqual(self.asset.history.count(), history_count)
        self.assertEqual(self.asset.sources.count(), len(before_urls) + 1)

    def test_later_text_preserves_the_whole_group_and_does_not_add_the_grant(self):
        self.asset.current_activity = "Later staff research is in progress."
        self.asset.activity_source_url = "https://example.org/staff-research"
        self.asset.activity_last_verified_at = timezone.localdate()
        self.asset.save()
        self.assertIn("preserved 1", self.apply())
        self.assertEqual(self.asset.current_activity, "Later staff research is in progress.")
        self.assertEqual(self.asset.activity_source_url, "https://example.org/staff-research")
        self.assertEqual(self.asset.search_aliases, "")
        self.assertFalse(self.asset.sources.filter(url=self.change["add_sources"][0]["url"]).exists())
        self.assertEqual(self.asset.status, Asset.Status.PUBLISHED)

    def test_staff_history_protects_an_otherwise_matching_baseline(self):
        self.asset._history_user = get_user_model().objects.create_user("escc-reviewer")
        self.asset.save()
        self.assertIn("preserved 1", self.apply())
        self.assertEqual(self.asset.current_activity, "")
        self.assertEqual(self.asset.status, Asset.Status.PUBLISHED)
        self.assertEqual(self.asset.sources.count(), 3)

    def test_hidden_grant_source_preserves_staff_source_decision(self):
        source = self.change["add_sources"][0]
        Source.objects.create(asset=self.asset, title=source["title"], url=source["url"],
                              is_public=False)
        self.assertIn("preserved 1", self.apply())
        self.assertEqual(self.asset.current_activity, "")
        self.assertFalse(self.asset.sources.get(url=source["url"]).is_public)
        self.assertEqual(self.asset.status, Asset.Status.PUBLISHED)

    def test_fresh_seed_and_later_editorial_manifest_do_not_certify_the_expansion(self):
        self.asset.delete()
        self.seed(self.current_record)
        self.asset = Asset.objects.get(name=self.change["name"])
        self.assertIn("Applied 1", self.apply())
        with TemporaryDirectory() as directory:
            path = Path(directory) / "review.json"
            path.write_text(json.dumps({
                "reviewed_at": "2026-10-06",
                "reviewed_assets": {self.asset.name: [self.change["add_sources"][0]["url"]]},
            }))
            call_command("apply_catalog_reviews", reviews=path, stdout=StringIO())
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.Status.SOURCE_BACKED)
        self.assertIsNone(self.asset.reviewed_at)
        self.assertEqual(self.asset.sources.count(), 4)
        self.asset.full_clean()

    def test_catalog_regeneration_retains_the_grant_without_duplicate_sources(self):
        records = deepcopy(self.catalog_records)
        record = next(r for r in records if r["name"] == self.change["name"])
        record.update(self.change["before"])
        grant_url = self.change["add_sources"][0]["url"]
        record["sources"] = [s for s in record["sources"] if s["url"] != grant_url]
        apply_reviewed_corrections(records)
        self.assertEqual(record["current_activity"], self.change["after"]["current_activity"])
        self.assertEqual(record["activity_source_url"], grant_url)
        self.assertEqual(sum(s["url"] == grant_url for s in record["sources"]), 1)
        apply_reviewed_corrections(records)
        self.assertEqual(sum(s["url"] == grant_url for s in record["sources"]), 1)
