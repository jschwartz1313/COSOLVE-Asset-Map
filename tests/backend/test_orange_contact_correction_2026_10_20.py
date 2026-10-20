from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Asset, AssetReviewComment, Relationship
from apps.catalog.models import Capability, MissionArea, PlatformDomain, StrategicCategory
from apps.sources.models import Source

NAME = "Orange County Sheriff's Office Drone Team"
OLD_URL = "https://www.louisacounty.gov/m/newsflash?cat=22%2C1"
NEW_URL = "https://www.orangecountyva.gov/sheriff"
MANIFEST = settings.BASE_DIR / "data" / "orange_contact_correction_2026_10_20.json"
TAXONOMIES = ("strategic_categories", "platform_domains", "capabilities", "missions")


class OrangeContactCorrectionTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            name=NAME,
            record_type=Asset.RecordType.PROGRAM,
            short_description="Publicly documented county drone team.",
            unmanned_systems_relevance="Public safety UAS program.",
            city="Orange",
            contact_url=OLD_URL,
            website_url=NEW_URL,
            internal_notes="Catalog provenance: curated-public-source.",
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
            reviewed_at=timezone.now(),
            last_verified_at=date(2026, 9, 4),
            review_priority=Asset.ReviewPriority.HIGH,
            review_notes="Retain the existing review choices.",
        )
        self.unrelated = Asset.objects.create(
            name="Unrelated county program",
            record_type=Asset.RecordType.PROGRAM,
            short_description="Another county program.",
            unmanned_systems_relevance="Public safety program.",
            contact_url=OLD_URL,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        for field, model in zip(
            TAXONOMIES, (StrategicCategory, PlatformDomain, Capability, MissionArea), strict=True
        ):
            getattr(self.asset, field).add(model.objects.create(name=f"Retained {field}"))
        Source.objects.create(
            asset=self.asset,
            title="Official county route",
            url=NEW_URL,
            notes="Catalog provenance: curated-public-source",
            verification_status="verified",
            last_verified_at=date(2026, 9, 4),
            link_review_status=Source.LinkReviewStatus.ACCEPTED,
            link_review_notes="Retain this manual source choice.",
        )
        Source.objects.create(
            asset=self.asset,
            title="Hidden retained evidence",
            url="https://example.org/retained-evidence",
            is_public=False,
            verification_status="rejected",
        )
        Relationship.objects.create(
            from_asset=self.asset,
            to_asset=self.unrelated,
            relationship_type=Relationship.RelationshipType.SUPPORTS,
            is_public=False,
            description="Retain this hidden relationship.",
        )

    def apply(self):
        call_command("apply_catalog_corrections", corrections=MANIFEST, stdout=StringIO())

    def snapshot(self):
        return {
            "assets": list(Asset.objects.order_by("pk").values()),
            "sources": list(Source.objects.order_by("pk").values()),
            "relationships": list(Relationship.objects.order_by("pk").values()),
            "taxonomy": {
                field: list(getattr(Asset, field).through.objects.order_by("pk").values())
                for field in TAXONOMIES
            },
            "asset_history": list(Asset.history.order_by("history_id").values()),
            "source_history": list(Source.history.order_by("history_id").values()),
            "relationship_history": list(Relationship.history.order_by("history_id").values()),
        }

    def assert_only_contact_changed(self, before):
        after = self.snapshot()
        for old, new in zip(before["assets"], after["assets"], strict=True):
            if old["id"] == self.asset.pk:
                self.assertEqual(new["contact_url"], NEW_URL)
                self.assertEqual(
                    {k: v for k, v in old.items() if k not in {"contact_url", "updated_at"}},
                    {k: v for k, v in new.items() if k not in {"contact_url", "updated_at"}},
                )
            else:
                self.assertEqual(old, new)
        for key in (
            "sources", "relationships", "taxonomy", "source_history", "relationship_history"
        ):
            self.assertEqual(before[key], after[key])
        self.assertEqual(before["asset_history"], after["asset_history"][:-1])
        self.assertEqual(len(after["asset_history"]), len(before["asset_history"]) + 1)
        self.assertEqual(self.asset.review_comments.count(), 1)

    def test_exact_published_baseline_changes_only_contact_and_repeat_does_nothing(self):
        before = self.snapshot()
        self.apply()
        self.assert_only_contact_changed(before)
        corrected = self.snapshot()
        comments = list(AssetReviewComment.objects.order_by("pk").values())
        self.apply()
        self.assertEqual(self.snapshot(), corrected)
        self.assertEqual(list(AssetReviewComment.objects.order_by("pk").values()), comments)

    def test_source_backed_baseline_is_corrected_without_editorial_promotion(self):
        self.asset.status = Asset.Status.SOURCE_BACKED
        self.asset.reviewed_at = None
        self.asset.last_verified_at = None
        self.asset.published_at = None
        self.asset.save()
        before = self.snapshot()
        self.apply()
        self.assert_only_contact_changed(before)

    def test_different_staff_contact_is_preserved_with_one_conflict_receipt(self):
        self.asset.contact_url = "https://example.org/staff-selected-contact"
        self.asset.save()
        before = self.snapshot()
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.asset.review_comments.count(), 1)
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.asset.review_comments.count(), 1)

    def test_already_correct_contact_does_not_rewrite_asset_or_source_choices(self):
        self.asset.contact_url = NEW_URL
        self.asset.save()
        before = self.snapshot()
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.asset.review_comments.count(), 1)
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.asset.review_comments.count(), 1)

    def test_renamed_identity_is_not_restored_or_changed(self):
        self.asset.name = "Staff-renamed county program"
        self.asset.save()
        before = self.snapshot()
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.asset.review_comments.exists())

    def test_different_provenance_is_not_changed(self):
        self.asset.internal_notes = "Staff-managed identity."
        self.asset.save()
        before = self.snapshot()
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.asset.review_comments.exists())

    def test_ambiguous_exact_name_does_not_select_a_record(self):
        Asset.objects.create(
            name=NAME,
            city="Different city",
            record_type=Asset.RecordType.PROGRAM,
            short_description="Different identity using the same name.",
            unmanned_systems_relevance="Public safety program.",
            contact_url=OLD_URL,
            internal_notes="Catalog provenance: curated-public-source.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        before = self.snapshot()
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(AssetReviewComment.objects.exists())

    def test_deleted_record_is_not_recreated(self):
        self.asset.delete()
        before = self.snapshot()
        self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(Asset.objects.filter(name=NAME).exists())

    def test_hidden_archived_and_staff_managed_records_are_preserved(self):
        user = get_user_model().objects.create_user("isolated-orange-correction-reviewer")
        cases = ("hidden", "archived", "reviewed-by", "assignee", "due", "history", "comment")
        for case in cases:
            with self.subTest(case=case):
                # Each fixture starts inside a rolled-back nested test transaction.
                from django.db import transaction

                with transaction.atomic():
                    asset = Asset.objects.get(pk=self.asset.pk)
                    if case == "hidden":
                        asset.visibility = Asset.Visibility.INTERNAL
                        asset.status = Asset.Status.VERIFIED
                    elif case == "archived":
                        asset.status = Asset.Status.ARCHIVED
                    elif case == "reviewed-by":
                        asset.reviewed_by = user
                    elif case == "assignee":
                        asset.review_assignee = user
                    elif case == "due":
                        asset.review_due_at = date(2026, 10, 27)
                    elif case == "history":
                        asset._history_user = user
                    elif case == "comment":
                        AssetReviewComment.objects.create(asset=asset, author=user, body="Retain.")
                    asset.save()
                    before = self.snapshot()
                    comments = list(AssetReviewComment.objects.order_by("pk").values())
                    self.apply()
                    self.assertEqual(self.snapshot(), before)
                    self.assertEqual(
                        list(AssetReviewComment.objects.order_by("pk").values()), comments
                    )
                    transaction.set_rollback(True)
