from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.assets.models import Asset, AssetReviewComment
from apps.assets.profile_media import photo_manifest, public_profile_photo


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class ProfilePhotoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.entry = photo_manifest()["photos"][0]
        cls.asset = Asset.objects.create(
            name=cls.entry["asset_name"], state="VA", record_type="facility",
            status="source-backed", visibility="public", short_description="Research facility",
            unmanned_systems_relevance="Flight dynamics testing",
        )

    def seed(self, apply=True):
        call_command("seed_profile_photos", *(["--apply"] if apply else []), stdout=StringIO())

    def test_seed_is_opt_in_idempotent_and_does_not_verify_asset(self):
        self.seed(apply=False)
        self.assertFalse(self.asset.site_diagrams.exists())
        self.seed()
        self.seed()
        self.assertEqual(self.asset.site_diagrams.count(), 1)
        self.assertEqual(AssetReviewComment.objects.filter(asset=self.asset).count(), 1)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, "source-backed")
        self.assertIsNone(self.asset.last_verified_at)
        self.assertIsNone(self.asset.reviewed_at)
        photo = public_profile_photo(self.asset)
        self.assertIn(self.entry["static_path"], photo["image_url"])
        self.assertEqual(photo["credit"], "NASA")

    def test_staff_unapproval_deletion_and_replacement_survive_reseeding(self):
        self.seed()
        image = self.asset.site_diagrams.get()
        image.publication_approved = False
        image.save()
        self.seed()
        self.assertIsNone(public_profile_photo(self.asset))
        image.publication_approved = True
        image.image_url = "https://example.com/staff-replacement.jpg"
        image.save()
        self.seed()
        self.assertEqual(public_profile_photo(self.asset)["image_url"], image.image_url)
        image.delete()
        AssetReviewComment.objects.filter(asset=self.asset).delete()
        self.seed()
        self.assertFalse(self.asset.site_diagrams.exists())

    def test_private_or_other_state_assets_are_not_seeded(self):
        self.asset.visibility = "internal"
        self.asset.save()
        self.seed()
        self.assertFalse(self.asset.site_diagrams.exists())
        self.asset.visibility, self.asset.state = "public", "NC"
        self.asset.save()
        self.seed()
        self.assertFalse(self.asset.site_diagrams.exists())

    def test_approved_photo_can_render_without_an_about_paragraph(self):
        self.seed()
        response = self.client.get(self.asset.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="profile-photo"')
        self.assertContains(response, "Photo source")
        self.assertEqual(list(response.context["site_diagrams"]), [])
        self.asset.site_diagrams.update(publication_approved=False)
        self.assertNotContains(
            self.client.get(self.asset.get_absolute_url()), 'class="profile-photo"',
        )

    def test_bundled_images_are_small_and_traceable_to_primary_sources(self):
        for entry in photo_manifest()["photos"]:
            path = Path(settings.BASE_DIR) / "static" / entry["static_path"]
            self.assertTrue(path.is_file())
            self.assertLess(path.stat().st_size, 500_000)
            self.assertTrue(entry["source_url"].startswith("https://www.nasa.gov/"))
            self.assertEqual(entry["width"], 1024)
            self.assertTrue(entry["alt_text"])
