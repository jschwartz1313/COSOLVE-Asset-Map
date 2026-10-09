"""Exercise guarded FAA reconciliation, source retirement and release review state."""

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

MANIFEST = settings.BASE_DIR / "data/faa_baa_corrections_2026_10_09.json"


class FaaBaaProposalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changes = json.loads(MANIFEST.read_text())["corrections"]
        catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        cls.records = [r for r in catalog["records"] if r["name"] in {
            c["name"] for c in cls.changes
        }]
        # Represent the freshly observed hosted baseline, before the new release.
        changes_by_name = {c["name"]: c for c in cls.changes}
        for record in cls.records:
            change = changes_by_name[record["name"]]
            record.update(change["before"])
            additions = {s["url"] for s in change["add_sources"]}
            record["sources"] = [s for s in record["sources"] if s["url"] not in additions]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"records": cls.records, "relationships": []}))
            call_command("seed_real_data", catalog=path, stdout=StringIO())
        Asset.objects.update(status=Asset.Status.PUBLISHED, reviewed_at=timezone.now(),
                             last_verified_at=timezone.localdate())

    def apply(self):
        call_command("apply_catalog_corrections", corrections=MANIFEST, stdout=StringIO())

    def test_awards_remain_pending_with_prior_evidence_locations_and_statuses_retained(self):
        before = {}
        for asset in Asset.objects.all():
            before[asset.name] = {
                "location": (asset.latitude, asset.longitude, asset.location_precision),
                "activity_status": asset.activity_status,
                "sources": set(asset.sources.values_list("url", flat=True)),
                "capabilities": set(asset.capabilities.values_list("pk", flat=True)),
            }
        self.apply()
        for change in self.changes:
            with self.subTest(name=change["name"]):
                asset = Asset.objects.get(name=change["name"])
                self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
                self.assertIsNone(asset.reviewed_at)
                self.assertEqual(asset.current_activity, change["after"]["current_activity"])
                self.assertEqual(asset.activity_status, before[asset.name]["activity_status"])
                self.assertEqual((asset.latitude, asset.longitude, asset.location_precision),
                                 before[asset.name]["location"])
                self.assertEqual(set(asset.capabilities.values_list("pk", flat=True)),
                                 before[asset.name]["capabilities"])
                self.assertTrue(before[asset.name]["sources"] <= set(
                    asset.sources.values_list("url", flat=True)))
                asset.full_clean()
                history_count = asset.history.count()
                source_count = asset.sources.count()
                self.apply()
                self.assertEqual(asset.history.count(), history_count)
                self.assertEqual(asset.sources.count(), source_count)

    def test_later_activity_preserves_whole_group_and_does_not_add_award_source(self):
        Asset.objects.update(current_activity="Later staff research.")
        self.apply()
        for asset in Asset.objects.all():
            self.assertEqual(asset.current_activity, "Later staff research.")
            self.assertEqual(asset.status, Asset.Status.PUBLISHED)
            self.assertFalse(asset.sources.filter(url=self.changes[0]["add_sources"][0]["url"]).exists())

    def test_staff_history_preserves_matching_baseline(self):
        reviewer = get_user_model().objects.create_user("isolated-baa-reviewer")
        for asset in Asset.objects.all():
            asset._history_user = reviewer
            asset.save()
        self.apply()
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            self.assertEqual(asset.current_activity, change["before"]["current_activity"])
            self.assertEqual(asset.status, Asset.Status.PUBLISHED)

    def test_hidden_source_decision_prevents_update(self):
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            source = change["add_sources"][0]
            Source.objects.create(asset=asset, title=source["title"], url=source["url"],
                                  is_public=False)
        self.apply()
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            self.assertEqual(asset.current_activity, change["before"]["current_activity"])
            self.assertEqual(asset.status, Asset.Status.PUBLISHED)
            self.assertFalse(asset.sources.get(url=change["add_sources"][0]["url"]).is_public)

    def test_retired_award_url_preserves_the_group_and_is_not_reintroduced(self):
        reviewer = get_user_model().objects.create_user("isolated-source-reviewer")
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            evidence = change["add_sources"][0]
            source = Source.objects.create(asset=asset, **evidence)
            source.url = "https://example.org/reviewed-replacement"
            source._history_user = reviewer
            source.save()
        self.apply()
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            self.assertEqual(asset.current_activity, change["before"]["current_activity"])
            self.assertEqual(asset.status, Asset.Status.PUBLISHED)
            self.assertFalse(asset.sources.filter(url=change["add_sources"][0]["url"]).exists())
            self.assertTrue(asset.sources.filter(
                url="https://example.org/reviewed-replacement").exists())

    def test_unattributed_deleted_award_source_is_not_reintroduced(self):
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            source = Source.objects.create(asset=asset, **change["add_sources"][0])
            source.delete()
        self.apply()
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            self.assertEqual(asset.current_activity, change["before"]["current_activity"])
            self.assertEqual(asset.status, Asset.Status.PUBLISHED)
            self.assertFalse(asset.sources.filter(url=change["add_sources"][0]["url"]).exists())

    def test_provenance_and_ambiguous_identity_skips_cannot_be_bypassed_by_enrichment(self):
        anra = Asset.objects.get(name="ANRA Technologies")
        droneup = Asset.objects.get(name="DroneUp")
        anra.internal_notes = "Preserve manually managed provenance."
        anra.save(update_fields=["internal_notes"])
        Asset.objects.create(
            name=droneup.name,
            city="Isolated duplicate city",
            record_type=droneup.record_type,
            short_description=droneup.short_description,
            unmanned_systems_relevance=droneup.unmanned_systems_relevance,
            internal_notes=droneup.internal_notes,
            status=Asset.Status.SOURCE_BACKED,
        )
        self.apply()
        call_command("enrich_asset_profiles", guarded_corrections=MANIFEST, stdout=StringIO())
        for name in ("ANRA Technologies", "DroneUp"):
            change = next(c for c in self.changes if c["name"] == name)
            asset = Asset.objects.get(pk=anra.pk if name == anra.name else droneup.pk)
            self.assertEqual(asset.current_activity, change["before"]["current_activity"])
            self.assertEqual(asset.status, Asset.Status.PUBLISHED)
            self.assertFalse(Source.objects.filter(
                asset__name=name, url=change["add_sources"][0]["url"]).exists())

    def test_default_and_explicit_generation_include_each_award_once(self):
        records = deepcopy(self.records)
        apply_reviewed_corrections(records, self.changes)
        apply_reviewed_corrections(records, self.changes)
        for record, change in zip(sorted(records, key=lambda r: r["name"]),
                                  sorted(self.changes, key=lambda r: r["name"]), strict=True):
            self.assertEqual(record["current_activity"], change["after"]["current_activity"])
            self.assertEqual(sum(s["url"] == change["add_sources"][0]["url"]
                                 for s in record["sources"]), 1)
        default_records = json.loads(
            (settings.BASE_DIR / "data/virginia_real_assets.json").read_text()
        )["records"]
        apply_reviewed_corrections(default_records)
        by_name = {record["name"]: record for record in default_records}
        for change in self.changes:
            record = by_name[change["name"]]
            self.assertEqual(record["current_activity"], change["after"]["current_activity"])
            self.assertEqual(sum(s["url"] == change["add_sources"][0]["url"]
                                 for s in record["sources"]), 1)

    def test_historical_catalog_reviews_do_not_republish_the_new_claims(self):
        self.apply()
        review_paths = [
            settings.BASE_DIR / "data/asset_editorial_reviews.json",
            *sorted((settings.BASE_DIR / "data").glob("asset_editorial_reviews_*.json")),
        ]
        for reviews in review_paths:
            call_command("apply_catalog_reviews", reviews=reviews, stdout=StringIO())
        for asset in Asset.objects.all():
            self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
