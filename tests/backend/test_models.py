from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.assets.models import Asset, Relationship


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
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
        )
        public.save()
        self.make_asset(name="Draft").save()
        self.make_asset(name="Internal", visibility=Asset.Visibility.INTERNAL).save()
        self.assertQuerySetEqual(Asset.public.all(), [public])

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
