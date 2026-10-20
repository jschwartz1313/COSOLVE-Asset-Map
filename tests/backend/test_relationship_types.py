import json
from io import StringIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.assets.models import Relationship
from scripts import build_real_asset_catalog


class CatalogRelationshipValidationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())

    def relationships(self):
        return [(item["from"], item["type"], item["to"])
                for item in self.catalog["relationships"]]

    def test_complete_catalog_uses_model_supported_relationship_types(self):
        self.assertEqual(
            set(build_real_asset_catalog.RELATIONSHIP_TYPES),
            set(Relationship.RelationshipType.values),
        )
        build_real_asset_catalog.validate(self.catalog["records"], self.relationships())

    def test_builder_rejects_unknown_and_blank_relationship_types(self):
        for invalid_type in ("unknown-relationship", ""):
            with self.subTest(relationship_type=invalid_type):
                relationships = self.relationships()
                origin, _original_type, target = relationships[0]
                relationships[0] = (origin, invalid_type, target)
                with self.assertRaisesMessage(ValueError, "Unknown relationship types:"):
                    build_real_asset_catalog.validate(self.catalog["records"], relationships)


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class CatalogRelationshipTypesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        call_command("seed_real_data", add_missing=True, stdout=StringIO())

    def test_every_seeded_catalog_relationship_passes_model_validation(self):
        relationships = Relationship.objects.select_related("from_asset", "to_asset")
        self.assertEqual(relationships.count(), len(self.catalog["relationships"]))
        self.assertEqual(
            {(item.from_asset.name, item.relationship_type, item.to_asset.name)
             for item in relationships},
            {(item["from"], item["type"], item["to"])
             for item in self.catalog["relationships"]},
        )
        for relationship in relationships:
            with self.subTest(relationship=str(relationship)):
                relationship.full_clean()

    def test_legacy_semantic_types_have_readable_labels_without_changing_records(self):
        legacy = Relationship.objects.filter(
            relationship_type__in=("hosts", "manufactures-for"),
        ).select_related("from_asset", "to_asset")
        before = list(legacy.order_by("pk").values())
        history_before = list(Relationship.history.order_by("history_id").values())
        self.assertEqual(legacy.filter(relationship_type="hosts").count(), 3)
        self.assertEqual(legacy.filter(relationship_type="manufactures-for").count(), 1)
        labels = {"hosts": "Hosts", "manufactures-for": "Manufactures for"}
        field = Relationship._meta.get_field("relationship_type").formfield()

        for relationship in legacy:
            with self.subTest(relationship_type=relationship.relationship_type):
                label = labels[relationship.relationship_type]
                relationship.full_clean()
                self.assertEqual(field.clean(relationship.relationship_type),
                                 relationship.relationship_type)
                self.assertEqual(relationship.get_relationship_type_display(), label)
                response = self.client.get(relationship.from_asset.get_absolute_url())
                self.assertContains(response, f"<span>{label}</span>", html=True)
                for asset, related, direction in (
                    (relationship.from_asset, relationship.to_asset, "outgoing"),
                    (relationship.to_asset, relationship.from_asset, "incoming"),
                ):
                    payload = self.client.get(f"/api/assets/{asset.slug}/").json()
                    self.assertIn({
                        "name": related.public_name,
                        "relationship": label,
                        "direction": direction,
                        "url": related.get_absolute_url(),
                    }, payload["related_entities"])

        self.assertEqual(list(legacy.order_by("pk").values()), before)
        self.assertEqual(list(Relationship.history.order_by("history_id").values()), history_before)

    def test_model_and_form_reject_unknown_relationship_types(self):
        original = Relationship.objects.select_related("from_asset", "to_asset").first()
        field = Relationship._meta.get_field("relationship_type").formfield()
        for invalid_type in ("unknown-relationship", ""):
            with self.subTest(relationship_type=invalid_type):
                relationship = Relationship(
                    from_asset=original.from_asset, to_asset=original.to_asset,
                    relationship_type=invalid_type,
                )
                with self.assertRaises(ValidationError) as error:
                    relationship.full_clean()
                self.assertIn("relationship_type", error.exception.message_dict)
                with self.assertRaises(ValidationError):
                    field.clean(invalid_type)
