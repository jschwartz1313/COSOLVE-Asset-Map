import io

from django.contrib import admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from apps.assets.access import can_preview_peer_states
from apps.assets.admin import OutgoingRelationshipInline
from apps.assets.models import (
    Asset,
    AssetReviewComment,
    DuplicateCandidate,
    Relationship,
    SavedView,
    UpdateSubmission,
)
from apps.assets.quality import discover_duplicate_candidates
from apps.imports.services import parse_csv
from apps.sources.models import Source


@override_settings(
    REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="", MULTISTATE_PUBLIC=False,
    MULTISTATE_PREVIEW_USERS=("jschwartz",),
)
class PeerAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.allowed = [users.objects.create_superuser("jschwartz", "", None)]
        cls.denied_named = []
        view_asset = Permission.objects.get(content_type__app_label="assets", codename="view_asset")
        for name in ("Ale", "Chelsea"):
            user = users.objects.create_user(name, is_staff=True)
            user.user_permissions.add(view_asset)
            cls.denied_named.append(user)
        cls.denied = users.objects.create_superuser("OtherAdmin", "", None)
        cls.denied_staff = users.objects.create_user("OtherEditor", is_staff=True)
        cls.denied_staff.user_permissions.add(view_asset)
        cls.guest = users.objects.create_user("Guest")
        base = dict(record_type="facility", status="source-backed",
                    short_description="Documented facility", unmanned_systems_relevance="Testing")
        cls.va = Asset.objects.create(name="Virginia visible site", state="VA",
                                      visibility="public", **base)
        cls.oh = Asset.objects.create(name="Ohio restricted site", state="OH",
                                      visibility="internal", benchmark_starter=True, **base)
        cls.oh2 = Asset.objects.create(name="Ohio restricted second site", state="OH",
                                       visibility="internal", benchmark_starter=True, **base)
        cls.va_source = Source.objects.create(asset=cls.va, title="Virginia citation",
                                               url="https://example.org/virginia")
        cls.peer_source = Source.objects.create(asset=cls.oh, title="Restricted Ohio citation",
                                                 url="https://example.org/ohio")
        cls.comment = AssetReviewComment.objects.create(asset=cls.oh, body="Restricted Ohio note")
        cls.relationship = Relationship.objects.create(
            from_asset=cls.va, to_asset=cls.oh, relationship_type="supports",
        )
        cls.duplicate = DuplicateCandidate.objects.create(
            left_asset=cls.oh, right_asset=cls.oh2, score=90, match_reasons=["Similar names"],
        )
        cls.submission = UpdateSubmission.objects.create(
            state="OH", asset=cls.oh, kind="correction", subject="Restricted Ohio submission",
            details="Private draft", submitter_name="Operator", submitter_email="op@example.org",
        )

    def request(self):
        request = RequestFactory().get("/admin/")
        request.user = self.denied
        return request

    def test_only_named_accounts_can_preview_even_among_superusers(self):
        for user in self.allowed:
            self.assertTrue(can_preview_peer_states(user))
            self.client.force_login(user)
            self.assertEqual(self.client.get("/states/ohio/map/").status_code, 200)
        self.assertFalse(can_preview_peer_states(self.denied))
        self.assertFalse(can_preview_peer_states(self.guest))
        with override_settings(MULTISTATE_PREVIEW_USERS=()):
            self.assertFalse(can_preview_peer_states(self.allowed[0]))

    def test_inactive_or_unprivileged_named_account_does_not_gain_asset_permissions(self):
        user = self.allowed[0]
        user.is_active = False
        self.assertFalse(can_preview_peer_states(user))
        user.is_active, user.is_staff = True, False
        self.assertFalse(can_preview_peer_states(user))

    def test_other_staff_and_guests_get_virginia_only_and_no_selector(self):
        for user in (self.denied, self.denied_staff, self.guest, *self.denied_named):
            self.client.force_login(user)
            for path in ("/map/", "/directory/", "/assets/" + self.va.slug + "/"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "data-state-switcher")
                self.assertNotContains(response, self.oh.name)
            for path in ("map/", "directory/", "api/assets.geojson", "compare/options/",
                         "admin/imports/export/", f"assets/{self.oh.slug}/"):
                response = self.client.get("/states/ohio/" + path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertEqual(self.client.get("/select-state/?state=ohio").status_code, 404)

    def test_admin_lists_and_related_choices_are_virginia_only(self):
        self.client.force_login(self.denied)
        records = ((Asset, self.oh), (Source, self.peer_source),
                   (AssetReviewComment, self.comment), (Relationship, self.relationship),
                   (DuplicateCandidate, self.duplicate), (UpdateSubmission, self.submission))
        for model, obj in records:
            opts = model._meta
            response = self.client.get(f"/admin/{opts.app_label}/{opts.model_name}/")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(obj.pk, response.context["cl"].queryset.values_list("pk", flat=True))
        response = self.client.get(f"/admin/assets/asset/{self.va.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.oh.name)
        self.assertNotIn("state", response.context["adminform"].form.fields)
        inline = OutgoingRelationshipInline(Asset, admin.site)
        field = inline.formfield_for_foreignkey(
            Relationship._meta.get_field("to_asset"), self.request(),
        )
        self.assertFalse(field.queryset.filter(state="OH").exists())

    def test_mismatched_submission_links_do_not_expose_a_peer_asset(self):
        self.submission.state = "VA"
        self.submission.save()
        self.client.force_login(self.denied)
        response = self.client.get("/admin/assets/updatesubmission/")
        self.assertNotContains(response, self.oh.name)
        self.assertNotContains(response, self.submission.subject)

    def test_direct_admin_history_and_versions_do_not_bypass_the_allowlist(self):
        self.client.force_login(self.denied)
        for model, obj in ((Asset, self.oh), (Source, self.peer_source),
                           (AssetReviewComment, self.comment), (Relationship, self.relationship)):
            opts = model._meta
            version = obj.history.first().history_id
            prefix = f"/admin/{opts.app_label}/{opts.model_name}/{obj.pk}/"
            for suffix in ("change/", "history/", f"history/{version}/"):
                response = self.client.get(prefix + suffix)
                self.assertIn(response.status_code, (302, 403, 404))
                self.assertNotIn(self.oh.name, response.content.decode())
        deleted_id = self.oh.pk
        version = self.oh.history.first().history_id
        self.oh.delete()
        for suffix in ("history/", f"history/{version}/"):
            response = self.client.get(f"/admin/assets/asset/{deleted_id}/" + suffix)
            self.assertIn(response.status_code, (403, 404))
            self.assertNotIn("Ohio restricted site", response.content.decode())

    def test_autocomplete_and_working_exports_cannot_reveal_peers(self):
        self.client.force_login(self.denied)
        response = self.client.get("/admin/autocomplete/", {
            "app_label": "sources", "model_name": "source", "field_name": "asset", "term": "Ohio",
        })
        self.assertEqual(response.json()["results"], [])
        response = self.client.get("/admin/imports/export/?scope=all")
        self.assertContains(response, self.va.name)
        self.assertNotContains(response, self.oh.name)
        response = self.client.post("/admin/assets/asset/", {
            "action": "export_selected",
            "_selected_action": [str(self.va.pk), str(self.oh.pk)],
        })
        self.assertNotContains(response, self.oh.name)

    def test_review_audit_and_recent_action_surfaces_do_not_reveal_peers(self):
        self.client.force_login(self.denied)
        for path in ("/admin/imports/data-quality/", "/admin/imports/audit-log/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            for text in (self.oh.name, self.peer_source.title, self.comment.body):
                self.assertNotContains(response, text)
        LogEntry.objects.log_actions(
            user_id=self.denied.pk, queryset=Asset.objects.filter(pk=self.oh.pk),
            action_flag=ADDITION,
        )
        self.assertNotContains(self.client.get("/admin/"), self.oh.name)

    def test_delete_confirmation_never_discloses_or_deletes_cross_state_dependents(self):
        self.client.force_login(self.denied)
        url = f"/admin/assets/asset/{self.va.pk}/delete/"
        self.assertNotContains(self.client.get(url), self.oh.name)
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
        self.assertTrue(Asset.objects.filter(pk=self.va.pk).exists())
        self.assertTrue(Relationship.objects.filter(pk=self.relationship.pk).exists())

    def test_csv_matching_and_stale_import_sessions_cannot_access_peers(self):
        content = ("name,record_type,short_description,unmanned_systems_relevance,state,slug\n"
                   f"{self.oh.name},facility,Site,Testing,OH,{self.oh.slug}\n").encode()
        rows, errors = parse_csv(io.BytesIO(content), allowed_states=("VA",))
        self.assertFalse(errors)
        self.assertFalse(rows[0]["duplicate"])
        self.assertEqual(rows[0]["asset_id"], "")
        self.assertTrue(rows[0]["errors"])
        self.client.force_login(self.denied)
        response = self.client.post("/admin/imports/preview/", {
            "file": SimpleUploadedFile("assets.csv", content, "text/csv"),
        })
        self.assertEqual(response.status_code, 200)
        session = self.client.session
        rows[0]["errors"] = []
        rows[0]["asset_id"] = str(self.oh.pk)
        session["asset_import_rows"] = rows
        session.save()
        response = self.client.post("/admin/imports/commit/", {"update_existing": "1"})
        self.assertEqual(response.status_code, 403)

    def test_saved_peer_views_are_hidden_after_access_is_removed(self):
        saved = SavedView.objects.create(owner=self.denied, name="Restricted saved peer view",
                                        state="OH", view_type="map", is_shared=True)
        self.client.force_login(self.denied)
        self.assertNotContains(self.client.get("/saved-views/"), saved.name)
        response = self.client.get(f"/saved-views/{saved.share_token}/")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("Location", response)

    def test_empty_scoped_duplicate_scan_does_not_fall_back_to_other_states(self):
        self.assertEqual(discover_duplicate_candidates(Asset.objects.none()), [])
        self.client.force_login(self.denied)
        response = self.client.post("/admin/imports/data-quality/scan-duplicates/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DuplicateCandidate.objects.filter(pk=self.duplicate.pk).exists())

    def test_named_accounts_retain_cross_state_admin_and_export_access(self):
        self.client.force_login(self.allowed[0])
        response = self.client.get("/admin/assets/asset/")
        self.assertContains(response, self.oh.name)
        response = self.client.get("/admin/imports/export/?scope=all")
        self.assertContains(response, self.oh.name)
        response = self.client.get(f"/admin/assets/asset/{self.oh.pk}/history/")
        self.assertEqual(response.status_code, 200)
