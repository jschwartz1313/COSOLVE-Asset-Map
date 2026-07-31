from datetime import timedelta
from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages.storage.cookie import CookieStorage
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.assets.admin import (
    AssetAdmin,
    DuplicateCandidateAdmin,
    UpdateSubmissionAdmin,
    assign_to_me,
    clear_review_assignment,
    mark_unverified,
    mark_verified,
    publish_eligible,
    set_review_due,
)
from apps.assets.models import Asset, DuplicateCandidate, UpdateSubmission
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
        values = {
            "name": name,
            "record_type": Asset.RecordType.FACILITY,
            "short_description": "Fixture",
            "unmanned_systems_relevance": "Supports testing",
            "status": status,
        }
        if status == Asset.Status.VERIFIED:
            values.update(
                {
                    "last_verified_at": timezone.localdate(),
                    "reviewed_at": timezone.now(),
                    "reviewed_by": self.user,
                }
            )
        return Asset.objects.create(
            **values
        )

    def test_verification_requires_verified_public_source(self):
        eligible = self.make_asset("Eligible")
        ineligible = self.make_asset("Ineligible")
        Source.objects.create(
            asset=eligible,
            title="Verified source",
            url="https://example.org/eligible",
            verification_status="verified",
            last_verified_at=timezone.localdate(),
            is_public=True,
        )
        Source.objects.create(
            asset=ineligible,
            title="Unreviewed source",
            url="https://example.org/ineligible",
            is_public=True,
        )

        mark_verified(self.admin, self.request, Asset.objects.all())

        eligible.refresh_from_db()
        ineligible.refresh_from_db()
        self.assertEqual(eligible.status, Asset.Status.VERIFIED)
        self.assertEqual(eligible.last_verified_at, timezone.localdate())
        self.assertEqual(eligible.reviewed_by, self.user)
        self.assertIsNotNone(eligible.reviewed_at)
        self.assertEqual(ineligible.status, Asset.Status.DRAFT)

    def test_unverify_restores_source_backed_status_and_preserves_source_review(self):
        asset = self.make_asset("Accidental verification", Asset.Status.VERIFIED)
        asset.visibility = Asset.Visibility.PUBLIC
        asset.published_at = timezone.now()
        asset.save()
        source = Source.objects.create(
            asset=asset,
            title="Verified source",
            url="https://example.org/verified-source",
            verification_status="verified",
            last_verified_at=timezone.localdate(),
            is_public=True,
        )

        mark_unverified(self.admin, self.request, Asset.objects.filter(pk=asset.pk))

        asset.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
        self.assertEqual(asset.visibility, Asset.Visibility.PUBLIC)
        self.assertIsNone(asset.last_verified_at)
        self.assertIsNone(asset.reviewed_at)
        self.assertIsNone(asset.reviewed_by)
        self.assertIsNone(asset.published_at)
        self.assertEqual(source.verification_status, "verified")
        latest_history = asset.history.latest("history_date")
        self.assertEqual(latest_history.history_user, self.user)
        self.assertEqual(
            latest_history.history_change_reason,
            "Editorial verification reversed from the admin action.",
        )

    def test_publication_requires_verified_status_and_source(self):
        eligible = self.make_asset("Eligible", Asset.Status.VERIFIED)
        draft = self.make_asset("Draft")
        for asset in (eligible, draft):
            Source.objects.create(
                asset=asset,
                title=f"{asset.name} source",
                url=f"https://example.org/{asset.slug}",
                verification_status="verified",
                last_verified_at=timezone.localdate(),
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

    def test_bulk_review_actions_assign_schedule_and_clear_records(self):
        asset = self.make_asset("Bulk Review")
        queryset = Asset.objects.filter(pk=asset.pk)

        assign_to_me(self.admin, self.request, queryset)
        set_review_due(self.admin, self.request, queryset)
        asset.refresh_from_db()
        self.assertEqual(asset.review_assignee, self.user)
        self.assertEqual(asset.review_due_at, timezone.localdate() + timedelta(days=14))

        clear_review_assignment(self.admin, self.request, queryset)
        asset.refresh_from_db()
        self.assertIsNone(asset.review_assignee)
        self.assertIsNone(asset.review_due_at)

    def test_individual_duplicate_decision_records_reviewer_and_timestamp(self):
        first = self.make_asset("First duplicate")
        second = self.make_asset("Second duplicate")
        candidate = DuplicateCandidate.objects.create(
            left_asset=first,
            right_asset=second,
            score=92,
            match_reasons=["Fixture match"],
            status=DuplicateCandidate.Status.NOT_DUPLICATE,
        )
        duplicate_admin = DuplicateCandidateAdmin(DuplicateCandidate, admin.site)

        duplicate_admin.save_model(
            self.request,
            candidate,
            SimpleNamespace(changed_data=["status"]),
            change=True,
        )

        candidate.refresh_from_db()
        self.assertEqual(candidate.reviewed_by, self.user)
        self.assertIsNotNone(candidate.reviewed_at)

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
        administrator = Group.objects.get(name="COSOLVE Administrator")
        viewer_permissions = set(viewer.permissions.values_list("codename", flat=True))
        reviewer_permissions = set(reviewer.permissions.values_list("codename", flat=True))
        editor_permissions = set(editor.permissions.values_list("codename", flat=True))
        publisher_permissions = set(publisher.permissions.values_list("codename", flat=True))
        administrator_permissions = set(
            administrator.permissions.values_list("codename", flat=True)
        )

        self.assertIn("view_asset", viewer_permissions)
        self.assertTrue(viewer_permissions < reviewer_permissions)
        self.assertTrue(reviewer_permissions < editor_permissions)
        self.assertTrue(editor_permissions < publisher_permissions)
        self.assertTrue(publisher_permissions < administrator_permissions)
        self.assertIn("change_asset", reviewer_permissions)
        self.assertIn("change_source", reviewer_permissions)
        self.assertIn("can_verify_asset", reviewer_permissions)
        self.assertIn("add_assetreviewcomment", reviewer_permissions)
        self.assertIn("change_duplicatecandidate", reviewer_permissions)
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
        self.assertIn("add_user", administrator_permissions)
        self.assertIn("change_user", administrator_permissions)
        self.assertIn("view_user", administrator_permissions)
        self.assertNotIn("delete_user", administrator_permissions)

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
        self.assertContains(asset_list, 'value="mark_unverified"')
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

    def test_administrator_can_manage_site_data_and_users_without_superuser_status(self):
        call_command("setup_staff_roles", verbosity=0)
        administrator = get_user_model().objects.create_user(
            "administrator", password="administrator-password", is_staff=True
        )
        administrator.groups.add(Group.objects.get(name="COSOLVE Administrator"))
        self.client.force_login(administrator)

        dashboard = self.client.get(reverse("admin:index"))
        self.assertContains(dashboard, "Add an asset")
        self.assertContains(dashboard, "Import CSV")
        self.assertContains(dashboard, "Export working data")
        self.assertContains(dashboard, "Update submissions")
        self.assertContains(dashboard, "Users and roles")
        self.assertEqual(self.client.get(reverse("admin:auth_user_add")).status_code, 200)
        account_page = self.client.get(reverse("admin:auth_user_change", args=[administrator.pk]))
        self.assertNotContains(account_page, 'id="id_is_superuser"')
        self.assertNotContains(account_page, 'id="id_user_permissions"')
        superuser = get_user_model().objects.create_superuser(
            "protected-superuser", password="protected-password"
        )
        self.assertEqual(
            self.client.get(reverse("admin:auth_user_change", args=[superuser.pk])).status_code,
            403,
        )
        self.assertFalse(administrator.is_superuser)
