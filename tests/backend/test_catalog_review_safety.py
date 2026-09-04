import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Asset
from apps.sources.models import Source


class CatalogReviewSafetyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("catalog-editor")

    def make_asset(self, name, **overrides):
        values = {
            "name": name,
            "record_type": Asset.RecordType.FACILITY,
            "short_description": "Catalog fixture",
            "unmanned_systems_relevance": "Testing",
            "internal_notes": "Catalog provenance: official source",
            "status": Asset.Status.SOURCE_BACKED,
            "visibility": Asset.Visibility.PUBLIC,
        }
        values.update(overrides)
        asset = Asset.objects.create(**values)
        Source.objects.create(
            asset=asset, title="Official source", url="https://example.org/source"
        )
        return asset

    def apply_manifest(self, reviewed_assets=None, follow_up_assets=None):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.json"
            path.write_text(
                json.dumps(
                    {
                        "reviewed_at": "2026-09-04",
                        "reviewed_assets": reviewed_assets or {},
                        "follow_up_assets": follow_up_assets or {},
                    }
                )
            )
            call_command("apply_catalog_reviews", reviews=path, stdout=StringIO())

    def test_review_cannot_publish_private_archived_or_assigned_records(self):
        protected = [
            self.make_asset("Private", visibility=Asset.Visibility.INTERNAL),
            self.make_asset("Archived", status=Asset.Status.ARCHIVED),
            self.make_asset("Needs review", status=Asset.Status.NEEDS_REVIEW),
            self.make_asset("Assigned", review_assignee=self.user),
            self.make_asset("Scheduled", review_due_at=timezone.localdate()),
            self.make_asset("Staff note", review_notes="Resolve location before publishing"),
            self.make_asset("Priority", review_priority=Asset.ReviewPriority.URGENT),
            self.make_asset("Edited"),
        ]
        edited = protected[-1]
        edited.short_description = "Staff corrected description"
        edited._history_user = self.user
        edited.save()
        self.apply_manifest({asset.name: ["https://example.org/source"] for asset in protected})
        for asset in protected:
            with self.subTest(name=asset.name):
                original_status, original_visibility = asset.status, asset.visibility
                asset.refresh_from_db()
                self.assertEqual(asset.status, original_status)
                self.assertEqual(asset.visibility, original_visibility)
                self.assertIsNone(asset.reviewed_at)
                self.assertEqual(asset.sources.get().verification_status, "unreviewed")
                self.assertFalse(asset.review_comments.exists())

    def test_staff_source_edits_are_not_automatically_accepted(self):
        asset = self.make_asset("Staff source")
        source = asset.sources.get()
        source.notes = "This page supports only part of the description"
        source._history_user = self.user
        source.save()
        self.apply_manifest({asset.name: [source.url]})
        asset.refresh_from_db()
        source.refresh_from_db()
        self.assertIsNone(asset.reviewed_at)
        self.assertEqual(source.verification_status, "unreviewed")

    def test_follow_up_preserves_urgent_priority_and_private_records(self):
        urgent = self.make_asset("Urgent", review_priority=Asset.ReviewPriority.URGENT)
        private = self.make_asset("Private follow-up", visibility=Asset.Visibility.INTERNAL)
        self.apply_manifest(follow_up_assets={urgent.name: "Check location", private.name: "Check"})
        urgent.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(urgent.review_priority, Asset.ReviewPriority.URGENT)
        self.assertEqual(private.review_priority, Asset.ReviewPriority.NORMAL)
        self.assertFalse(private.review_comments.exists())

    def test_empty_evidence_does_not_publish_a_record(self):
        asset = self.make_asset("No evidence")
        self.apply_manifest({asset.name: []})
        asset.refresh_from_db()
        self.assertIsNone(asset.reviewed_at)
