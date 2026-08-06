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

    def test_preview_rejects_unsourced_current_activity(self):
        content = (
            "name,record_type,short_description,unmanned_systems_relevance,"
            "activity_status,current_activity\n"
            "Demo Import,facility,Fixture,Supports testing,active,Current flight testing\n"
        )
        response = self.upload(content)
        self.assertContains(response, "Activity details require an activity source URL")
        self.assertContains(response, "Activity details require an activity review date")

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
        Source.objects.create(
            asset=asset,
            title="Unreviewed source",
            url="https://example.org/unreviewed",
        )
        response = self.client.get(reverse("imports:data-quality"))
        self.assertContains(response, "Needs Review")
        self.assertContains(response, "missing public sources")
        self.assertContains(response, "Unreviewed source")
        self.assertContains(response, "Repeated relevance copy")
        self.assertContains(response, "Incomplete profiles or contacts")

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

    def test_export_honors_active_asset_filters(self):
        matching = Asset.objects.create(
            name="Matching Facility",
            record_type=Asset.RecordType.FACILITY,
            short_description="Matching export fixture.",
            unmanned_systems_relevance="Supports filtered export testing.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        excluded = Asset.objects.create(
            name="Excluded University",
            record_type=Asset.RecordType.UNIVERSITY,
            short_description="Excluded export fixture.",
            unmanned_systems_relevance="Supports filtered export testing.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )

        response = self.client.get(
            reverse("imports:export"),
            {"record_type": Asset.RecordType.FACILITY},
        )

        content = response.content.decode()
        self.assertContains(response, matching.name)
        self.assertNotIn(excluded.name, content)

    def test_complete_export_can_be_imported_without_losing_data(self):
        asset = Asset.objects.create(
            name="Round Trip Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="Complete working export fixture.",
            overview="A full profile that should survive the spreadsheet round trip.",
            unmanned_systems_relevance="Supports round-trip spreadsheet review.",
            website_url="https://example.org/asset",
            contact_text="Facility public information",
            contact_phone="757-555-0123",
            contact_email="asset@example.org",
            contact_url="https://example.org/asset/contact",
            activity_status=Asset.ActivityStatus.ACTIVE,
            current_activity="Current source-backed flight testing.",
            partnership_opportunities="Public test participation inquiries are accepted.",
            activity_source_url="https://example.org/activity",
            activity_last_verified_at=timezone.localdate(),
            owner_operator="Example operator",
            available_acreage="12.50",
            development_status=Asset.DevelopmentStatus.IN_DEVELOPMENT,
            development_notes="A second test pad is planned.",
            infrastructure_access="Road, power, and controlled airspace access.",
            development_source_url="https://example.org/development",
            development_last_verified_at=timezone.localdate(),
            address_line="100 Test Way",
            city="Norfolk",
            state="VA",
            postal_code="23510",
            latitude="36.850000",
            longitude="-76.280000",
            region=self.region,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Preserve this staff note.",
        )
        asset.strategic_categories.add(self.category)
        Source.objects.create(
            asset=asset,
            title="Round trip source",
            url="https://example.org/source",
        )
        exported = self.client.get(reverse("imports:export"), {"scope": "all"})
        upload = SimpleUploadedFile(
            "round-trip.csv", exported.content, content_type="text/csv"
        )
        preview = self.client.post(reverse("imports:preview"), {"file": upload})
        self.assertContains(preview, "Ready")
        self.client.post(reverse("imports:commit"), {"update_existing": "1"})

        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.Status.NEEDS_REVIEW)
        self.assertEqual(asset.internal_notes, "Preserve this staff note.")
        self.assertEqual(
            asset.overview,
            "A full profile that should survive the spreadsheet round trip.",
        )
        self.assertEqual(asset.contact_phone, "757-555-0123")
        self.assertEqual(asset.contact_email, "asset@example.org")
        self.assertEqual(asset.contact_url, "https://example.org/asset/contact")
        self.assertEqual(asset.activity_status, Asset.ActivityStatus.ACTIVE)
        self.assertEqual(asset.current_activity, "Current source-backed flight testing.")
        self.assertEqual(asset.owner_operator, "Example operator")
        self.assertEqual(str(asset.available_acreage), "12.50")
        self.assertEqual(
            asset.development_status,
            Asset.DevelopmentStatus.IN_DEVELOPMENT,
        )
        self.assertEqual(list(asset.strategic_categories.all()), [self.category])
        self.assertEqual(asset.sources.get().url, "https://example.org/source")
