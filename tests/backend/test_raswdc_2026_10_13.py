from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

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

    def seed(self):
        call_command("seed_real_data", catalog=MANIFEST, add_missing=True, stdout=StringIO())

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
        self.seed()
        self.assertEqual(Asset.objects.filter(pk=command.pk).values().get(), before)
        self.assertEqual(command.sources.count(), 1)
        self.assertFalse(command.sources.get().is_public)

    def test_repeat_does_not_restore_a_deleted_relationship(self):
        self.seed()
        Relationship.objects.get(from_asset__name=COMMAND, to_asset=self.base).delete()
        self.seed()
        self.assertFalse(Relationship.objects.filter(from_asset__name=COMMAND).exists())

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
