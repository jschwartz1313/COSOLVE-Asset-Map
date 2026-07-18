from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Asset
from apps.catalog.models import Region, StrategicCategory
from apps.sources.models import Source


class ImportWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            "staff", email="staff@example.test", password="test"
        )
        self.client.force_login(self.user)
        self.region = Region.objects.create(name="Hampton Roads")
        self.category = StrategicCategory.objects.create(name="Test environments")

    def upload(self, content):
        file = SimpleUploadedFile("assets.csv", content.encode(), content_type="text/csv")
        return self.client.post(reverse("imports:preview"), {"file": file})

    def test_import_requires_staff(self):
        self.client.logout()
        response = self.client.get(reverse("imports:preview"))
        self.assertEqual(response.status_code, 302)

    def test_preview_and_commit_create_internal_draft(self):
        content = (
            "name,record_type,short_description,unmanned_systems_relevance,city,region,strategic_categories\n"
            "Demo Import,facility,Fixture,Supports testing,Norfolk,"
            f"{self.region.slug},{self.category.slug}\n"
        )
        response = self.upload(content)
        self.assertContains(response, "Ready")
        response = self.client.post(reverse("imports:commit"), follow=True)
        self.assertEqual(response.status_code, 200)
        asset = Asset.objects.get(name="Demo Import")
        self.assertEqual(asset.status, Asset.Status.DRAFT)
        self.assertEqual(asset.visibility, Asset.Visibility.INTERNAL)
        self.assertEqual(list(asset.strategic_categories.all()), [self.category])

    def test_invalid_taxonomy_blocks_commit(self):
        content = (
            "name,record_type,short_description,unmanned_systems_relevance,strategic_categories\n"
            "Demo Import,facility,Fixture,Supports testing,unknown-category\n"
        )
        response = self.upload(content)
        self.assertContains(response, "Unknown strategic_categories")
        self.client.post(reverse("imports:commit"))
        self.assertFalse(Asset.objects.exists())

    def test_duplicate_can_be_updated_and_returned_to_review(self):
        existing = Asset.objects.create(
            name="Demo Import",
            city="Norfolk",
            record_type=Asset.RecordType.FACILITY,
            short_description="Old description",
            unmanned_systems_relevance="Old relevance",
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
            reviewed_at=timezone.now(),
            last_verified_at=timezone.localdate(),
        )
        content = (
            "name,record_type,short_description,unmanned_systems_relevance,city\n"
            "Demo Import,facility,Updated description,Updated relevance,Norfolk\n"
        )
        response = self.upload(content)
        self.assertContains(response, "Existing record")
        self.client.post(reverse("imports:commit"), {"update_existing": "1"})
        existing.refresh_from_db()
        self.assertEqual(existing.short_description, "Updated description")
        self.assertEqual(existing.status, Asset.Status.NEEDS_REVIEW)
        self.assertEqual(existing.visibility, Asset.Visibility.INTERNAL)
        self.assertIsNone(existing.reviewed_at)

    def test_data_quality_dashboard_requires_staff(self):
        self.client.logout()
        response = self.client.get(reverse("imports:data-quality"))
        self.assertEqual(response.status_code, 302)

    def test_data_quality_dashboard_reports_missing_fields(self):
        asset = Asset.objects.create(
            name="Needs Review",
            record_type=Asset.RecordType.FACILITY,
            short_description="Fixture",
            unmanned_systems_relevance="Supports testing",
            status=Asset.Status.NEEDS_REVIEW,
        )
        Source.objects.create(asset=asset, title="Unreviewed source")
        response = self.client.get(reverse("imports:data-quality"))
        self.assertContains(response, "Needs Review")
        self.assertContains(response, "missing public sources")
        self.assertContains(response, "Unreviewed source")
        self.assertContains(response, "Repeated relevance copy")

    def test_export_requires_staff(self):
        self.client.logout()
        response = self.client.get(reverse("imports:export"))
        self.assertEqual(response.status_code, 302)

    def test_export_requires_export_permission(self):
        user = get_user_model().objects.create_user(
            "viewer", password="test", is_staff=True
        )
        user.user_permissions.add(Permission.objects.get(codename="view_asset"))
        self.client.force_login(user)
        response = self.client.get(reverse("imports:export"))
        self.assertEqual(response.status_code, 403)
