from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Asset, AssetReviewComment, DuplicateCandidate
from apps.assets.quality import sync_duplicate_candidates
from apps.sources.models import Source


class ReviewQualityWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            "quality-editor", email="quality@example.test", password="test"
        )
        self.client.force_login(self.user)

    def make_asset(self, name, **overrides):
        values = {
            "name": name,
            "record_type": Asset.RecordType.FACILITY,
            "short_description": "Quality workflow fixture.",
            "unmanned_systems_relevance": "Supports autonomous systems.",
            "status": Asset.Status.NEEDS_REVIEW,
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    def test_review_assignments_comments_and_audit_history_are_persistent(self):
        asset = self.make_asset(
            "Assigned Review",
            review_assignee=self.user,
            review_due_at=timezone.localdate(),
            review_priority=Asset.ReviewPriority.HIGH,
        )
        comment = AssetReviewComment.objects.create(
            asset=asset,
            author=self.user,
            body="Confirm the campus-level coordinates before verification.",
        )

        dashboard = self.client.get(reverse("imports:data-quality"))
        self.assertContains(dashboard, "Assigned Review")
        self.assertContains(dashboard, "Assigned to me")
        self.assertContains(dashboard, "quality-editor")
        audit = self.client.get(reverse("imports:audit-log"))
        self.assertContains(audit, "Data audit log")
        self.assertContains(audit, "Assigned Review")
        self.assertTrue(comment.history.exists())

    def test_duplicate_scan_creates_high_signal_candidates_and_preserves_distinct_decisions(self):
        first = self.make_asset(
            "Virginia Autonomy Laboratory",
            city="Norfolk",
            website_url="https://example.org/autonomy-lab",
            latitude="36.850000",
            longitude="-76.290000",
        )
        second = self.make_asset(
            "Virginia Autonomous Laboratory",
            city="Norfolk",
            website_url="https://example.org/autonomy-lab",
            latitude="36.850100",
            longitude="-76.290100",
        )
        self.make_asset(
            "Unrelated Campus Program",
            city="Norfolk",
            website_url="https://example.org/autonomy-lab",
        )

        result = sync_duplicate_candidates()

        self.assertEqual(result["detected"], 1)
        candidate = DuplicateCandidate.objects.get()
        self.assertEqual({candidate.left_asset, candidate.right_asset}, {first, second})
        candidate.status = DuplicateCandidate.Status.NOT_DUPLICATE
        candidate.reviewed_by = self.user
        candidate.reviewed_at = timezone.now()
        candidate._history_user = self.user
        candidate.save()
        sync_duplicate_candidates()
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, DuplicateCandidate.Status.NOT_DUPLICATE)
        audit = self.client.get(reverse("imports:audit-log"))
        self.assertContains(
            audit,
            f"{candidate.left_asset.name} / {candidate.right_asset.name}",
        )
        self.assertNotContains(audit, f">{candidate.pk}<")

    def test_source_monitor_health_appears_in_review_workspace(self):
        asset = self.make_asset("Source Monitor Asset")
        Source.objects.create(
            asset=asset,
            title="Healthy monitored source",
            url="https://example.org/source",
            last_checked_at=timezone.now(),
            http_status=200,
        )

        response = self.client.get(reverse("imports:data-quality"))

        self.assertContains(response, "Source monitor")
        self.assertContains(response, "Healthy checks in the last 7 days")
