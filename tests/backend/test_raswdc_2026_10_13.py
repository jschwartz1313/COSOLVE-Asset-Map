import json
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.assets.models import Asset, Relationship
from apps.catalog.models import Region
from apps.sources.models import Source

MANIFEST = settings.BASE_DIR / "data/asset_expansion_2026_10_13.json"
COMMAND = "Navy Robotic and Autonomous Systems Warfighting Development Center"
BASE = "Joint Expeditionary Base Little Creek-Fort Story"


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class RaswdcReleaseTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Hampton Roads")
        self.base = Asset.objects.create(
            name=BASE, region=self.region, status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC, record_type="organization",
            short_description="Existing installation.",
            unmanned_systems_relevance="Host installation.",
            overview="Staff-maintained installation description.",
        )

    def seed(self, catalog=MANIFEST):
        call_command("seed_real_data", catalog=catalog, add_missing=True, stdout=StringIO())

    def seed_without_identity_guard(self):
        catalog = json.loads(MANIFEST.read_text())
        catalog["records"][0].pop("identity_guard_terms")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "unguarded-catalog.json"
            path.write_text(json.dumps(catalog))
            self.seed(catalog=path)

    def test_new_command_stays_pending_and_links_to_preserved_base(self):
        before = Asset.objects.filter(pk=self.base.pk).values().get()
        self.seed()
        command = Asset.objects.get(name=COMMAND)
        self.assertEqual(command.status, Asset.Status.SOURCE_BACKED)
        self.assertIsNone(command.last_verified_at)
        self.assertEqual(command.activity_status, "developing")
        self.assertEqual(command.location_role, "headquarters")
        self.assertEqual(command.location_precision, "site")
        self.assertIn("not a command building", command.location_notes)
        self.assertEqual(command.sources.count(), 3)
        self.assertTrue(all(s.verification_status == "unreviewed" for s in command.sources.all()))
        self.assertEqual(Asset.objects.filter(pk=self.base.pk).values().get(), before)
        self.assertTrue(Relationship.objects.filter(
            from_asset=command, to_asset=self.base, relationship_type="located-at",
        ).exists())
        response = self.client.get(command.get_absolute_url())
        self.assertContains(response, "editorial review pending")
        self.assertContains(response, "commercial-testing intake")
        self.assertContains(response, "phased implementation")
        self.assertContains(response, self.base.get_absolute_url())
        payload = self.client.get(f"/api/assets/{command.slug}/").json()
        self.assertEqual(payload["location"]["precision"], "site")
        self.assertEqual(payload["activity"]["status"], "developing")

    def test_repeat_does_not_republish_hidden_relationship_or_add_source(self):
        self.seed()
        link = Relationship.objects.get(from_asset__name=COMMAND, to_asset=self.base)
        link.is_public = False
        link.description = "Staff held this relationship for review."
        link.save()
        history_count = link.history.count()
        self.seed()
        link.refresh_from_db()
        self.assertFalse(link.is_public)
        self.assertEqual(link.description, "Staff held this relationship for review.")
        self.assertEqual(link.history.count(), history_count)
        self.assertEqual(Asset.objects.filter(name=COMMAND).count(), 1)
        self.assertEqual(Source.objects.filter(asset__name=COMMAND).count(), 3)

    def test_existing_staff_command_and_sources_are_preserved(self):
        command = Asset.objects.create(
            name=COMMAND, region=self.region, status=Asset.Status.NEEDS_REVIEW,
            visibility=Asset.Visibility.INTERNAL, overview="Staff intake, do not replace.",
            record_type="organization", short_description="Staff command intake.",
            unmanned_systems_relevance="Pending command evidence.",
        )
        Source.objects.create(
            asset=command, title="Staff evidence", url="https://example.com/held", is_public=False,
        )
        before = Asset.objects.filter(pk=command.pk).values().get()
        asset_history_count = command.history.count()
        source_history_count = command.sources.get().history.count()
        self.seed()
        self.assertEqual(Asset.objects.filter(pk=command.pk).values().get(), before)
        self.assertEqual(command.sources.count(), 1)
        self.assertFalse(command.sources.get().is_public)
        self.assertEqual(command.history.count(), asset_history_count)
        self.assertEqual(command.sources.get().history.count(), source_history_count)
        self.assertFalse(Relationship.objects.filter(from_asset=command).exists())
        self.assertFalse(Relationship.history.filter(from_asset_id=command.pk).exists())

    def test_repeat_does_not_restore_a_deleted_relationship(self):
        self.seed()
        Relationship.objects.get(from_asset__name=COMMAND, to_asset=self.base).delete()
        history_count = Relationship.history.count()
        self.seed()
        self.assertFalse(Relationship.objects.filter(from_asset__name=COMMAND).exists())
        self.assertEqual(Relationship.history.count(), history_count)

    def test_existing_public_command_holds_new_relationships_in_both_directions(self):
        command = Asset.objects.create(
            name=COMMAND, region=self.region, status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC, record_type="organization",
            short_description="Staff-maintained public command.",
            unmanned_systems_relevance="Reviewed command identity.",
            internal_notes="Catalog provenance: retained through later staff review.",
            reviewed_at=timezone.now(), last_verified_at=date(2026, 10, 13),
        )
        before = Asset.objects.filter(pk=command.pk).values().get()
        history_count = command.history.count()
        catalog = json.loads(MANIFEST.read_text())
        catalog["relationships"].append({
            "from": BASE, "to": COMMAND, "type": "supports",
        })
        with TemporaryDirectory() as directory:
            path = Path(directory) / "incoming-and-outgoing-catalog.json"
            path.write_text(json.dumps(catalog))
            self.seed(catalog=path)

        self.assertEqual(Asset.objects.filter(pk=command.pk).values().get(), before)
        self.assertEqual(command.history.count(), history_count)
        self.assertFalse(command.sources.exists())
        self.assertFalse(Relationship.objects.filter(from_asset=command).exists())
        self.assertFalse(Relationship.objects.filter(to_asset=command).exists())
        self.assertFalse(Relationship.history.filter(from_asset_id=command.pk).exists())
        self.assertFalse(Relationship.history.filter(to_asset_id=command.pk).exists())

    def test_repeat_preserves_existing_public_relationship_and_history(self):
        self.seed()
        command = Asset.objects.get(name=COMMAND)
        link = Relationship.objects.get(from_asset=command, to_asset=self.base)
        link.description = "Staff-confirmed installation relationship."
        link.save()
        before = Relationship.objects.filter(pk=link.pk).values().get()
        history_count = link.history.count()

        self.seed()

        self.assertEqual(Relationship.objects.filter(pk=link.pk).values().get(), before)
        self.assertEqual(link.history.count(), history_count)
        self.assertEqual(Relationship.objects.count(), 1)

    def test_unguarded_deleted_relationship_still_stays_deleted(self):
        self.seed_without_identity_guard()
        Relationship.objects.get(from_asset__name=COMMAND, to_asset=self.base).delete()
        history_count = Relationship.history.count()

        self.seed_without_identity_guard()

        self.assertFalse(Relationship.objects.filter(from_asset__name=COMMAND).exists())
        self.assertEqual(Relationship.history.count(), history_count)

    def test_unguarded_identity_still_gets_intended_missing_catalog_relationship(self):
        command = Asset.objects.create(
            name=COMMAND, region=self.region, status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC, record_type="organization",
            short_description="Existing unguarded catalog identity.",
            unmanned_systems_relevance="Catalog relationship gap.",
        )
        before = Asset.objects.filter(pk=command.pk).values().get()

        self.seed_without_identity_guard()

        self.assertEqual(Asset.objects.filter(pk=command.pk).values().get(), before)
        self.assertFalse(command.sources.exists())
        self.assertTrue(Relationship.objects.filter(
            from_asset=command, to_asset=self.base,
            relationship_type=Relationship.RelationshipType.LOCATED_AT, is_public=True,
        ).exists())

    def test_staff_alias_identity_holds_addition_and_relationship(self):
        staff = Asset.objects.create(
            name="Staff RASWDC intake", search_aliases="RASWDC", region=self.region,
            record_type="organization", short_description="Staff command intake.",
            unmanned_systems_relevance="Pending command evidence.",
        )
        self.seed()
        self.assertFalse(Asset.objects.filter(name=COMMAND).exists())
        self.assertFalse(Relationship.objects.filter(to_asset=self.base).exists())
        staff.refresh_from_db()
        self.assertEqual(staff.search_aliases, "RASWDC")
