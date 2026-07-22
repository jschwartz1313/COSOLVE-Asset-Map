from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages.storage.cookie import CookieStorage
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assets.admin import AssetAdmin, UpdateSubmissionAdmin, mark_verified, publish_eligible
from apps.assets.models import Asset, UpdateSubmission
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
        self.assertTrue({"status", "visibility", "last_verified_at", "published_at"} <= readonly)

    def test_update_submissions_can_move_through_review_queue(self):
        submission = UpdateSubmission.objects.create(
            kind=UpdateSubmission.Kind.GENERAL,
            subject="Workflow question",
            details="A sufficiently detailed question for the editorial team.",
            submitter_name="Taylor Morgan",
            submitter_email="taylor@example.org",
        )
        submission_admin = UpdateSubmissionAdmin(UpdateSubmission, admin.site)
        submission_admin.mark_in_review(
            self.request, UpdateSubmission.objects.filter(pk=submission.pk)
        )
        submission.refresh_from_db()
        self.assertEqual(submission.status, UpdateSubmission.Status.IN_REVIEW)


class StaffRoleCommandTests(TestCase):
    def test_setup_staff_roles_creates_cumulative_groups(self):
        call_command("setup_staff_roles", verbosity=0)

        viewer = Group.objects.get(name="COSOLVE Viewer")
        reviewer = Group.objects.get(name="COSOLVE Reviewer")
        editor = Group.objects.get(name="COSOLVE Editor")
        publisher = Group.objects.get(name="COSOLVE Publisher")
        viewer_permissions = set(viewer.permissions.values_list("codename", flat=True))
        reviewer_permissions = set(reviewer.permissions.values_list("codename", flat=True))
        editor_permissions = set(editor.permissions.values_list("codename", flat=True))
        publisher_permissions = set(publisher.permissions.values_list("codename", flat=True))

        self.assertIn("view_asset", viewer_permissions)
        self.assertTrue(viewer_permissions < reviewer_permissions)
        self.assertTrue(reviewer_permissions < editor_permissions)
        self.assertTrue(editor_permissions < publisher_permissions)
        self.assertIn("change_asset", reviewer_permissions)
        self.assertIn("change_source", reviewer_permissions)
        self.assertIn("can_verify_asset", reviewer_permissions)
        self.assertNotIn("add_asset", reviewer_permissions)
        self.assertNotIn("add_source", reviewer_permissions)
        self.assertNotIn("can_publish_asset", reviewer_permissions)
        self.assertNotIn("view_updatesubmission", reviewer_permissions)
        self.assertIn("can_export_asset", editor_permissions)
        self.assertNotIn("view_updatesubmission", viewer_permissions)
        self.assertIn("view_updatesubmission", editor_permissions)
        self.assertIn("change_updatesubmission", editor_permissions)
        self.assertIn("can_verify_asset", publisher_permissions)
        self.assertIn("can_publish_asset", publisher_permissions)

    def test_reviewer_admin_is_limited_to_existing_data_and_verification(self):
        call_command("setup_staff_roles", verbosity=0)
        reviewer = get_user_model().objects.create_user(
            "reviewer", password="reviewer-password", is_staff=True
        )
        reviewer.groups.add(Group.objects.get(name="COSOLVE Reviewer"))
        self.client.force_login(reviewer)
        Asset.objects.create(
            name="Reviewer Test Asset",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A record available for reviewer workflow testing.",
            unmanned_systems_relevance="Supports autonomous systems review workflows.",
        )

        dashboard = self.client.get(reverse("admin:index"))
        self.assertContains(dashboard, "Asset records")
        self.assertContains(dashboard, "Sources")
        self.assertContains(dashboard, "Data quality")
        self.assertNotContains(dashboard, "Add an asset")
        self.assertNotContains(dashboard, "Import CSV")
        self.assertNotContains(dashboard, "Update submissions")
        self.assertNotContains(dashboard, "Users and roles")

        asset_list = self.client.get(reverse("admin:assets_asset_changelist"))
        self.assertEqual(asset_list.status_code, 200)
        self.assertContains(asset_list, 'value="mark_verified"')
        self.assertNotContains(asset_list, 'value="publish_eligible"')
        self.assertNotContains(asset_list, 'value="export_selected"')
        self.assertEqual(
            self.client.get(reverse("admin:sources_source_changelist")).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("admin:assets_asset_add")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("admin:assets_updatesubmission_changelist")).status_code,
            403,
        )
