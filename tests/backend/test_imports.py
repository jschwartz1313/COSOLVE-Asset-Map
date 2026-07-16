from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.assets.models import Asset
from apps.catalog.models import Region, StrategicCategory


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
