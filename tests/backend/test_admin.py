from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages.storage.cookie import CookieStorage
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.assets.admin import AssetAdmin, mark_verified, publish_eligible
from apps.assets.models import Asset
from apps.sources.models import Source


class AdminWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            "publisher", email="publisher@example.test", password="test"
        )
        self.request = RequestFactory().post("/admin/assets/asset/")
        self.request.user = self.user
        self.request._messages = CookieStorage(self.request)
        self.admin = AssetAdmin(Asset, admin.site)

    def make_asset(self, name, status=Asset.Status.DRAFT):
        return Asset.objects.create(
            name=name,
            record_type=Asset.RecordType.FACILITY,
            short_description="Fixture",
            unmanned_systems_relevance="Supports testing",
            status=status,
        )

    def test_verification_requires_verified_public_source(self):
        eligible = self.make_asset("Eligible")
        ineligible = self.make_asset("Ineligible")
        Source.objects.create(
            asset=eligible,
            title="Verified source",
            verification_status="verified",
            is_public=True,
        )
        Source.objects.create(asset=ineligible, title="Unreviewed source", is_public=True)

        mark_verified(self.admin, self.request, Asset.objects.all())

        eligible.refresh_from_db()
        ineligible.refresh_from_db()
        self.assertEqual(eligible.status, Asset.Status.VERIFIED)
        self.assertEqual(eligible.last_verified_at, timezone.localdate())
        self.assertEqual(eligible.reviewed_by, self.user)
        self.assertIsNotNone(eligible.reviewed_at)
        self.assertEqual(ineligible.status, Asset.Status.DRAFT)

    def test_publication_requires_verified_status_and_source(self):
        eligible = self.make_asset("Eligible", Asset.Status.VERIFIED)
        draft = self.make_asset("Draft")
        for asset in (eligible, draft):
            Source.objects.create(
                asset=asset,
                title=f"{asset.name} source",
                verification_status="verified",
                is_public=True,
            )

        publish_eligible(self.admin, self.request, Asset.objects.all())

        eligible.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(eligible.status, Asset.Status.PUBLISHED)
        self.assertEqual(eligible.visibility, Asset.Visibility.PUBLIC)
        self.assertEqual(draft.status, Asset.Status.DRAFT)

    def test_lifecycle_fields_are_read_only_in_asset_form(self):
        readonly = set(self.admin.get_readonly_fields(self.request))
        self.assertTrue(
            {"status", "visibility", "last_verified_at", "published_at"} <= readonly
        )


class StaffRoleCommandTests(TestCase):
    def test_setup_staff_roles_creates_cumulative_groups(self):
        call_command("setup_staff_roles", verbosity=0)

        viewer = Group.objects.get(name="COSOLVE Viewer")
        editor = Group.objects.get(name="COSOLVE Editor")
        publisher = Group.objects.get(name="COSOLVE Publisher")
        viewer_permissions = set(viewer.permissions.values_list("codename", flat=True))
        editor_permissions = set(editor.permissions.values_list("codename", flat=True))
        publisher_permissions = set(publisher.permissions.values_list("codename", flat=True))

        self.assertIn("view_asset", viewer_permissions)
        self.assertTrue(viewer_permissions < editor_permissions)
        self.assertTrue(editor_permissions < publisher_permissions)
        self.assertIn("can_export_asset", editor_permissions)
        self.assertIn("can_verify_asset", publisher_permissions)
        self.assertIn("can_publish_asset", publisher_permissions)
