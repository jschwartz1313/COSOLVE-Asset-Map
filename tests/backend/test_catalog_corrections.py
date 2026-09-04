import json
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Asset, AssetReviewComment
from apps.sources.models import Source


class CatalogCorrectionTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            name="Correction fixture",
            record_type="organization",
            short_description="Public test organization.",
            unmanned_systems_relevance="Supports unmanned-systems research.",
            internal_notes="Catalog provenance: curated-public-source.",
            city="Richmond",
            latitude=37.5,
            longitude=-77.4,
            location_precision="locality",
            status="source-backed",
            visibility="public",
        )
        self.item = {
            "name": self.asset.name,
            "provenance": "curated-public-source",
            "before": {"city": "Richmond", "latitude": 37.5, "longitude": -77.4},
            "after": {"city": "Richmond", "latitude": 37.538119, "longitude": -77.440536},
            "reason": "Reviewed public address correction.",
        }

    def apply(self, items=None):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "corrections.json"
            path.write_text(
                json.dumps(
                    {
                        "reviewed_at": "2026-09-04",
                        "corrections": items or [self.item],
                    }
                )
            )
            call_command("apply_catalog_corrections", corrections=path, stdout=StringIO())
        self.asset.refresh_from_db()

    def test_matching_coordinates_update_once_without_publishing(self):
        self.apply()
        self.assertEqual(self.asset.latitude, Decimal("37.538119"))
        self.assertEqual(self.asset.status, "source-backed")
        self.assertIsNone(self.asset.reviewed_at)
        # A later staff rollback must not be overwritten by another deployment.
        self.asset.latitude = 37.5
        self.asset.longitude = -77.4
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.latitude, Decimal("37.500000"))
        self.assertEqual(self.asset.review_comments.count(), 1)

    def test_staff_coordinate_change_preserves_entire_group(self):
        self.asset.longitude = -78
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.latitude, Decimal("37.500000"))
        self.assertEqual(self.asset.longitude, Decimal("-78.000000"))
        self.assertTrue(
            self.asset.review_comments.filter(
                body__startswith="Catalog correction conflict:"
            ).exists()
        )

    def test_accepted_baseline_resolves_only_its_existing_conflict_and_stays_idempotent(self):
        self.asset.longitude = -78
        self.asset.save()
        self.apply()
        conflict = self.asset.review_comments.get()
        original_body = conflict.body
        unrelated = AssetReviewComment.objects.create(
            asset=self.asset,
            body="Catalog correction conflict: unrelated\nKeep this decision.",
        )
        self.item["accepted_baselines"] = [{**self.item["before"], "longitude": -78}]
        self.apply()
        self.assertEqual(self.asset.longitude, Decimal("-77.440536"))
        conflict.refresh_from_db()
        unrelated.refresh_from_db()
        self.assertTrue(conflict.body.startswith("Catalog correction conflict resolved:"))
        self.assertTrue(conflict.history.filter(body=original_body).exists())
        self.assertTrue(unrelated.body.startswith("Catalog correction conflict:"))
        # Extending the reviewed alternatives must not rerun an already applied correction.
        self.asset.longitude = -78
        self.asset.save()
        self.item["accepted_baselines"].append({**self.item["before"], "longitude": -79})
        self.apply()
        self.assertEqual(self.asset.longitude, Decimal("-78.000000"))
        self.assertEqual(
            self.asset.review_comments.filter(body__startswith="Catalog correction:").count(), 1
        )

    def test_incomplete_or_malformed_accepted_baselines_fail_without_changes(self):
        for baselines in (None, {}, "invalid", [{"longitude": -78}], [None]):
            with self.subTest(baselines=baselines):
                self.item["accepted_baselines"] = baselines
                with self.assertRaisesMessage(CommandError, "Invalid accepted baselines"):
                    self.apply()
                self.asset.refresh_from_db()
                self.assertEqual(self.asset.longitude, Decimal("-77.400000"))
                self.assertFalse(self.asset.review_comments.exists())

    def enrich(self, **overrides):
        record = {
            "name": self.asset.name,
            "provenance": "curated-public-source",
            "short_description": "Catalog profile",
            "overview": "Catalog overview",
            "address_line": "100 Public Street",
            "city": "Richmond",
            "postal_code": "23219",
            "region": "Greater Richmond",
            "latitude": 37.538119,
            "longitude": -77.440536,
            "location_precision": "site",
            "platform_domains": [],
            "strategic_categories": [],
            "sources": [],
        }
        record.update(overrides)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"records": [record]}))
            call_command("enrich_asset_profiles", catalog=path, stdout=StringIO())
        self.asset.refresh_from_db()

    def test_enrichment_does_not_undo_a_conflicted_location_correction(self):
        self.asset.longitude = -78
        self.asset.save()
        self.apply()
        self.enrich()
        self.assertEqual(self.asset.longitude, Decimal("-78.000000"))
        self.assertEqual(self.asset.latitude, Decimal("37.500000"))
        self.assertEqual(self.asset.address_line, "")

    def test_private_archived_and_staff_edited_records_are_preserved(self):
        user = get_user_model().objects.create_user("editor")
        for kind in ("private", "archived", "staff"):
            with self.subTest(kind=kind):
                self.asset.visibility = "internal" if kind == "private" else "public"
                self.asset.status = "archived" if kind == "archived" else "source-backed"
                if kind == "staff":
                    self.asset._history_user = user
                self.asset.save()
                self.apply()
                self.enrich()
                self.assertEqual(self.asset.latitude, Decimal("37.500000"))
                self.assertEqual(self.asset.address_line, "")
                self.assertFalse(self.asset.review_comments.exists())

    def test_fresh_seeded_final_values_can_apply_review_flag_without_reverting_text(self):
        self.item["before"] = {"overview": "Old claim"}
        self.item["after"] = {"overview": "Qualified claim"}
        self.item["review_required"] = True
        self.asset.overview = "Qualified claim"
        self.asset.status = "published"
        self.asset.reviewed_at = timezone.now()
        self.asset.last_verified_at = date(2026, 8, 21)
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.overview, "Qualified claim")
        self.assertEqual(self.asset.status, "source-backed")
        self.assertEqual(self.asset.visibility, "public")
        self.assertIsNone(self.asset.reviewed_at)
        self.assertIsNone(self.asset.last_verified_at)

    def test_chained_corrections_recognize_fresh_final_catalog_values(self):
        first = {
            **self.item,
            "before": {"overview": "Original"},
            "after": {"overview": "Intermediate"},
        }
        second = {
            **self.item,
            "before": {"overview": "Intermediate"},
            "after": {"overview": "Final"},
        }
        self.asset.overview = "Final"
        self.asset.save()
        self.apply(items=[first, second])
        self.assertEqual(self.asset.overview, "Final")
        self.assertEqual(self.asset.review_comments.count(), 2)
        self.assertFalse(
            self.asset.review_comments.filter(
                body__startswith="Catalog correction conflict:"
            ).exists()
        )

    def test_historical_review_cannot_verify_a_manifest_flagged_follow_up(self):
        Source.objects.create(asset=self.asset, title="Source", url="https://example.org/source")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.json"
            path.write_text(
                json.dumps(
                    {
                        "reviewed_at": "2026-08-21",
                        "reviewed_assets": {self.asset.name: ["https://example.org/source"]},
                    }
                )
            )
            with patch(
                "apps.assets.management.commands.apply_catalog_reviews.review_required_names",
                return_value={self.asset.name},
            ):
                call_command("apply_catalog_reviews", reviews=path, stdout=StringIO())
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.reviewed_at)
        self.assertEqual(self.asset.sources.get().verification_status, "unreviewed")

    def test_duplicate_source_urls_are_preserved_without_failing_deployment(self):
        self.source_replacement()
        for title in ("Duplicate A", "Duplicate B"):
            Source.objects.create(asset=self.asset, title=title, url="https://example.org/current")
        self.apply()
        self.assertEqual(self.asset.sources.count(), 3)
        self.assertTrue(self.asset.sources.get(url="https://example.org/obsolete").is_public)

    def test_missing_source_baseline_does_not_reintroduce_removed_evidence(self):
        old = self.source_replacement()
        old.delete()
        self.apply()
        self.assertFalse(self.asset.sources.exists())

    def test_staff_deleted_source_is_not_recreated_by_corrections_or_enrichment(self):
        user = get_user_model().objects.create_user("source-editor")
        old = self.source_replacement()
        removed = Source.objects.create(
            asset=self.asset,
            title="Removed source",
            url="https://example.org/current",
        )
        removed._history_user = user
        removed.delete()
        self.apply()
        self.enrich(sources=[{"title": "Replacement", "url": "https://example.org/current"}])
        self.assertEqual(self.asset.sources.count(), 1)
        old.refresh_from_db()
        self.assertTrue(old.is_public)

    def test_enrichment_keeps_staff_annotations_and_retired_source_history(self):
        self.asset.name = "HII Unmanned Systems Center of Excellence"
        self.asset.save()
        sources = []
        for index, url in enumerate(
            (
                "https://www.hampton.gov/CivicAlerts.aspx?AID=4656&ARC=9365",
                "https://www.hampton.gov/CivicAlerts.aspx?AID=4759&ARC=9695",
            )
        ):
            sources.append(
                Source.objects.create(
                    asset=self.asset,
                    title=f"Legacy source {index}",
                    url=url,
                    notes="Catalog provenance: curated-public-source"
                    + (" Staff annotation." if index else ""),
                    is_public=bool(index),
                )
            )
        self.enrich()
        self.assertEqual(self.asset.sources.count(), 2)

    def test_repeat_enrichment_preserves_current_sources_and_avoids_empty_history_updates(self):
        self.asset.name = "DZYNE Technologies"
        self.asset.save()
        values = {
            "contact_text": "Organization public information and inquiries",
            "contact_url": "https://example.org/contact",
            "sources": [
                {
                    "title": "Current SBIR evidence",
                    "url": "https://www.sbir.gov/portfolio/406214",
                }
            ],
        }
        self.enrich(**values)
        source = self.asset.sources.get()
        history_count = self.asset.history.count()
        source_history_count = source.history.count()
        updated_at = self.asset.updated_at
        self.enrich(**values)
        self.assertEqual(self.asset.history.count(), history_count)
        self.assertEqual(self.asset.updated_at, updated_at)
        self.assertEqual(self.asset.sources.get().pk, source.pk)
        self.assertEqual(source.history.count(), source_history_count)

    def source_replacement(self):
        self.item["before"] = {}
        self.item["after"] = {}
        self.item["replace_sources"] = [
            {
                "old_url": "https://example.org/obsolete",
                "source": {"title": "Current source", "url": "https://example.org/current"},
            }
        ]
        return Source.objects.create(
            asset=self.asset,
            title="Old source",
            url="https://example.org/obsolete",
            notes="Catalog provenance: curated-public-source",
            is_public=True,
        )

    def test_replaced_source_is_retained_and_new_source_stays_unreviewed(self):
        old = self.source_replacement()
        self.apply()
        old.refresh_from_db()
        self.assertFalse(old.is_public)
        self.assertEqual(old.verification_status, "stale")
        replacement = self.asset.sources.get(url="https://example.org/current")
        self.assertEqual(replacement.verification_status, "unreviewed")
        self.apply()
        self.assertEqual(self.asset.sources.count(), 2)

    def test_staff_source_annotation_is_not_removed(self):
        old = self.source_replacement()
        old.notes += " Staff annotation."
        old.save()
        self.apply()
        old.refresh_from_db()
        self.assertTrue(old.is_public)
        self.assertEqual(self.asset.sources.count(), 1)

    def test_hidden_replacement_source_is_not_republished(self):
        old = self.source_replacement()
        Source.objects.create(
            asset=self.asset,
            title="Hidden",
            url="https://example.org/current",
            is_public=False,
        )
        self.apply()
        old.refresh_from_db()
        self.assertTrue(old.is_public)
        self.assertFalse(self.asset.sources.get(url="https://example.org/current").is_public)
