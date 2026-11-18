from decimal import Decimal
from difflib import SequenceMatcher
from itertools import combinations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Asset, AssetReviewComment, DuplicateCandidate
from apps.assets.quality import (
    _candidate_details,
    _distance_miles,
    _normalized_text,
    _normalized_url,
    sync_duplicate_candidates,
)
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

    def test_duplicate_scan_ignores_shared_institutional_sites_and_campus_points(self):
        self.make_asset(
            "Example University",
            city="Norfolk",
            address_line="100 College Drive",
            website_url="https://example.edu/",
            latitude="36.850000",
            longitude="-76.290000",
        )
        self.make_asset(
            "Autonomous Systems Certificate",
            city="Norfolk",
            address_line="100 College Drive",
            website_url="https://example.edu/",
            latitude="36.850000",
            longitude="-76.290000",
        )

        result = sync_duplicate_candidates()

        self.assertEqual(result["detected"], 0)
        self.assertFalse(DuplicateCandidate.objects.exists())

    def test_source_monitor_health_appears_in_review_workspace(self):
        asset = self.make_asset("Source Monitor Asset")
        Source.objects.create(
            asset=asset,
            title="Healthy monitored source",
            url="https://example.org/source",
            last_checked_at=timezone.now(),
            http_status=200,
        )
        Source.objects.create(
            asset=asset,
            title="No HTTP result",
            url="https://example.org/no-result",
            last_checked_at=timezone.now(),
        )

        response = self.client.get(reverse("imports:data-quality"))

        self.assertContains(response, "Source monitor")
        self.assertContains(response, "Healthy checks in the last 7 days")
        self.assertEqual(response.context["healthy_source_count"], 1)

    def test_faster_duplicate_matching_preserves_original_scores_and_reasons(self):
        def reference(first, second):
            if first.state != second.state:
                return None
            first_name, second_name = _normalized_text(first.name), _normalized_text(second.name)
            ratio = SequenceMatcher(None, first_name, second_name).ratio()
            city = bool(
                first.city and _normalized_text(first.city) == _normalized_text(second.city)
            )
            address = _normalized_text(first.address_line)
            website = _normalized_url(first.website_url)
            distance = _distance_miles(first, second)
            reasons, scores = [], []
            if first_name == second_name:
                reasons.append("Same normalized name")
                scores.append(100)
            if (
                website
                and website == _normalized_url(second.website_url)
                and city
                and ratio >= 0.75
            ):
                reasons.append(f"Same website URL with related names ({ratio:.0%})")
                scores.append(round(90 + ratio * 8))
            if (
                address
                and address == _normalized_text(second.address_line)
                and city
                and ratio >= 0.9
            ):
                reasons.append(f"Same street address and related names ({ratio:.0%})")
                scores.append(round(88 + ratio * 8))
            if city and ratio >= 0.9:
                reasons.append(f"Similar names in the same city ({ratio:.0%})")
                scores.append(round(86 + ratio * 10))
            if distance is not None and distance <= 0.05 and ratio >= 0.9:
                reasons.append(f"Locations within {distance:.2f} miles with related names")
                scores.append(round(82 + ratio * 10))
            return {"score": min(max(scores), 100), "match_reasons": reasons} if reasons else None

        fixtures = []
        for name in (
            "Autonomy Laboratory",
            "Autonomy Laboratories",
            "Different Campus",
            "AUTONOMY-LABORATORY",
        ):
            for city, offset in (("Norfolk", "0"), ("Hampton", "0.0001"), ("", "0.0011")):
                for state in ("VA", "NC"):
                    fixtures.append(
                        Asset(
                            name=name,
                            city=city,
                            state=state,
                            address_line="1 Research Way",
                            website_url="https://lab.example.edu/",
                            latitude=Decimal("36.85") + Decimal(offset),
                            longitude=Decimal("-76.29"),
                        )
                    )
        fixtures.append(Asset(name="Autonomy Laboratory", city="", state="VA"))
        for first, second in combinations(fixtures, 2):
            with self.subTest(
                first=first.name, second=second.name, cities=(first.city, second.city)
            ):
                self.assertEqual(_candidate_details(first, second), reference(first, second))
