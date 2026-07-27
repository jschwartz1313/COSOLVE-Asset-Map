from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.assets.models import Asset, Relationship
from apps.catalog.models import Region


class AssetModelTests(TestCase):
    def make_asset(self, **overrides):
        values = {
            "name": "Demo Model Asset",
            "record_type": Asset.RecordType.FACILITY,
            "short_description": "A representative record.",
            "unmanned_systems_relevance": "Supports unmanned systems testing.",
            "city": "Norfolk",
        }
        values.update(overrides)
        return Asset(**values)

    def test_slug_is_created(self):
        asset = self.make_asset()
        asset.save()
        self.assertEqual(asset.slug, "demo-model-asset")

    def test_coordinates_must_be_paired(self):
        asset = self.make_asset(latitude=Decimal("36.850000"))
        with self.assertRaises(ValidationError):
            asset.save()

    def test_public_manager_excludes_draft_and_internal_records(self):
        public = self.make_asset(
            name="Public",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        public.save()
        self.make_asset(name="Draft").save()
        self.make_asset(name="Internal", visibility=Asset.Visibility.INTERNAL).save()
        self.assertQuerySetEqual(Asset.public.all(), [public])

    @override_settings(PUBLIC_REGION_SLUG="hampton-roads")
    def test_public_manager_enforces_deployment_region(self):
        hampton_roads = Region.objects.create(name="Hampton Roads")
        greater_richmond = Region.objects.create(name="Greater Richmond")
        regional = self.make_asset(
            name="Regional Public",
            region=hampton_roads,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        regional.save()
        self.make_asset(
            name="Out of Scope Public",
            region=greater_richmond,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        ).save()

        self.assertQuerySetEqual(Asset.public.all(), [regional])
        self.assertEqual(Asset.objects.count(), 2)

    def test_source_backed_record_is_not_labeled_editorially_reviewed(self):
        asset = self.make_asset(
            status=Asset.Status.SOURCE_BACKED, visibility=Asset.Visibility.PUBLIC
        )
        asset.save()
        self.assertFalse(asset.is_editorially_reviewed)
        self.assertIn("review pending", asset.verification_label)

    def test_published_record_requires_editorial_review_dates(self):
        asset = self.make_asset(
            status=Asset.Status.PUBLISHED, visibility=Asset.Visibility.PUBLIC
        )
        with self.assertRaises(ValidationError):
            asset.save()
        asset.last_verified_at = timezone.localdate()
        asset.reviewed_at = timezone.now()
        asset.save()
        self.assertTrue(asset.is_editorially_reviewed)

    def test_asset_edits_create_field_level_history(self):
        asset = self.make_asset()
        asset.save()
        asset.short_description = "A revised representative record."
        asset.save()
        delta = asset.history.latest().diff_against(asset.history.earliest())
        self.assertIn("short_description", [change.field for change in delta.changes])

    def test_relationship_cannot_target_itself(self):
        asset = self.make_asset()
        asset.save()
        relationship = Relationship(
            from_asset=asset,
            to_asset=asset,
            relationship_type=Relationship.RelationshipType.SUPPORTS,
        )
        with self.assertRaises(ValidationError):
            relationship.full_clean()
