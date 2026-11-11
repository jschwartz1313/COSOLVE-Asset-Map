import uuid
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.storage.cookie import CookieStorage
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from apps.assets.models import Asset
from apps.assets.operator_admin import OperatorReviewAdmin, create_operator_review_invitation
from apps.assets.operator_review import (
    PUBLIC_FIELD_LIMITS,
    OperatorReview,
    OperatorReviewConflict,
    OperatorReviewUnavailable,
    get_public_operator_details,
)
from apps.catalog.models import Capability
from apps.core.operator_forms import OperatorReviewForm
from apps.core.operator_views import operator_review
from apps.core.urls import urlpatterns as core_patterns

review_admin_site = admin.AdminSite(name="operator_test_admin")
review_admin_site.register(OperatorReview, OperatorReviewAdmin)
review_admin_site.register(Asset)
urlpatterns = [
    path("admin/imports/", include("apps.imports.urls")),
    path("admin/", review_admin_site.urls),
    path("", include(([
        path("operator-review/<str:token>/", operator_review, name="operator-review"),
        *core_patterns,
    ], "core"))),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("auth/", include("allauth.urls")),
]


@override_settings(
    ROOT_URLCONF=__name__, REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="",
    PUBLIC_SITE_URL="https://catalog.example.test", DEBUG=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class OperatorReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            "operator-editor", email="editor@example.test", password="test",
        )
        cls.asset = Asset.objects.create(
            name="Public operator facility", record_type=Asset.RecordType.FACILITY,
            short_description="An operator-review fixture.",
            unmanned_systems_relevance="Published research capability.",
            status=Asset.Status.SOURCE_BACKED, visibility=Asset.Visibility.PUBLIC,
            internal_notes="Never expose these internal notes.",
            review_notes="Private editorial discussion.",
        )

    def issue(self, **kwargs):
        return OperatorReview.issue(asset=self.asset, created_by=self.staff, **kwargs)

    def payload(self, **kwargs):
        return {
            "use_cases": "Survey research and controlled demonstrations.",
            "access_notes": "Prior arrangement with the operator is required.",
            "contact_text": "Public scheduling team", "contact_phone": "+1 555 0100",
            "contact_email": "public@example.test",
            "contact_url": "https://operator.example.test/contact",
            "submitter_name": "Private Person", "submitter_email": "private@example.test",
            "publication_consent": "on", **kwargs,
        }

    def submit(self, review=None, **kwargs):
        review = review or self.issue()
        form = OperatorReviewForm(self.payload(**kwargs))
        self.assertTrue(form.is_valid(), form.errors)
        form.submit(review)
        return review

    def assert_private_headers(self, response):
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "strict-origin")

    def request(self, user=None, method="post"):
        request = getattr(RequestFactory(), method)("/admin/assets/operatorreview/")
        request.user = user or self.staff
        request._messages = CookieStorage(request)
        return request

    def test_invitation_snapshots_asset_and_expires_without_email(self):
        review = self.issue()
        self.assertEqual(review.created_by, self.staff)
        self.assertEqual(review.baseline["asset"]["name"], self.asset.name)
        self.assertNotIn("internal_notes", review.baseline["asset"])
        self.assertNotIn("review_notes", review.baseline["asset"])
        self.assertEqual(review.proposal, {})
        self.assertIsInstance(review.token, uuid.UUID)
        self.assertTrue(review.is_available)
        self.assertGreater(review.expires_at, timezone.now() + timedelta(days=13))
        self.assertNotIn(str(review.token), str(review))
        self.assertEqual(len(mail.outbox), 0)

    def test_only_asset_public_manager_members_can_be_invited(self):
        for field, value in (
            ("visibility", Asset.Visibility.INTERNAL),
            ("status", Asset.Status.ARCHIVED),
            ("status", Asset.Status.VERIFIED),
        ):
            with self.subTest(field=field, value=value):
                original = getattr(self.asset, field)
                Asset.objects.filter(pk=self.asset.pk).update(**{field: value})
                with self.assertRaises(ValidationError):
                    self.issue()
                Asset.objects.filter(pk=self.asset.pk).update(**{field: original})
        self.assertEqual(OperatorReview.objects.count(), 0)

    @override_settings(PUBLIC_REGION_SLUG="not-this-region")
    def test_out_of_scope_asset_cannot_be_invited(self):
        with self.assertRaises(ValidationError):
            self.issue()

    def test_past_expiry_rejected_at_creation(self):
        with self.assertRaises(ValidationError):
            self.issue(expires_at=timezone.now() - timedelta(seconds=1))

    def test_submission_is_single_use_private_and_unpublished(self):
        review = self.submit()
        self.assertIsNotNone(review.submitted_at)
        self.assertTrue(review.publication_consent)
        self.assertEqual(review.submitter_email, "private@example.test")
        self.assertNotIn("submitter_email", review.proposal)
        self.assertEqual(get_public_operator_details(self.asset), {})
        form = OperatorReviewForm(self.payload(use_cases="A replacement proposal"))
        with self.assertRaises(OperatorReviewUnavailable):
            form.submit(review)
        review.refresh_from_db()
        self.assertEqual(review.proposal["use_cases"], self.payload()["use_cases"])

    def test_stale_instance_cannot_replace_a_submission(self):
        review = self.issue()
        stale_instance = OperatorReview.objects.get(pk=review.pk)
        self.submit(review)
        form = OperatorReviewForm(self.payload(use_cases="Attempt to replace"))
        with self.assertRaises(OperatorReviewUnavailable):
            form.submit(stale_instance)

    def test_consent_is_required_by_form_and_service(self):
        form = OperatorReviewForm(self.payload(publication_consent=""))
        self.assertFalse(form.is_valid())
        self.assertIn("publication_consent", form.errors)
        review = self.issue()
        for consent in (False, "on", 1):
            with self.subTest(consent=consent), self.assertRaises(ValidationError):
                review.submit(
                    proposal={"use_cases": "Research"}, submitter_name="Person",
                    submitter_email="person@example.test", publication_consent=consent,
                )
        review.refresh_from_db()
        self.assertIsNone(review.submitted_at)

    def test_empty_proposal_and_honeypot_are_rejected(self):
        empty = self.payload(**{key: "" for key in PUBLIC_FIELD_LIMITS})
        self.assertFalse(OperatorReviewForm(empty).is_valid())
        self.assertFalse(OperatorReviewForm(self.payload(confirmation="bot")).is_valid())

    def test_all_field_length_limits(self):
        for key, limit in {
            **PUBLIC_FIELD_LIMITS, "submitter_name": 120, "submitter_email": 254,
        }.items():
            with self.subTest(field=key):
                form = OperatorReviewForm(self.payload(**{key: "x" * (limit + 1)}))
                self.assertFalse(form.is_valid())
                self.assertIn(key, form.errors)

    def test_only_valid_public_http_urls_are_allowed(self):
        for url in (
            "javascript:alert(1)", "data:text/html,unsafe", "ftp://example.test/file",
            "//example.test/contact", "https://user:secret@example.test/contact",
            "https://example.test/a\nb", "https://example.test/a b",
        ):
            with self.subTest(url=url):
                form = OperatorReviewForm(self.payload(contact_url=url))
                self.assertFalse(form.is_valid())
                self.assertIn("contact_url", form.errors)

    def test_model_service_validates_payload_and_private_identity(self):
        invalid_proposals = (
            [], {"submitter_email": "private@example.test"}, {"use_cases": ["research"]},
            {"use_cases": "x" * 3001}, {"contact_url": "javascript:alert(1)"},
            {"contact_email": "not-an-email"}, {"use_cases": "Research\x00"},
        )
        review = self.issue()
        for proposal in invalid_proposals:
            with self.subTest(proposal=proposal), self.assertRaises(ValidationError):
                review.submit(
                    proposal=proposal, submitter_name="Person", submitter_email="p@example.test",
                    publication_consent=True,
                )
        for name, email in (("", "p@example.test"), ("Person", "bad"), ("x" * 121, "p@e.test")):
            with self.subTest(name=name, email=email), self.assertRaises(ValidationError):
                review.submit(
                    proposal={"use_cases": "Research"}, submitter_name=name,
                    submitter_email=email, publication_consent=True,
                )

    def test_expired_revoked_and_hidden_assets_reject_submission(self):
        for condition in ("expired", "revoked", "private"):
            with self.subTest(condition=condition):
                review = self.issue()
                if condition == "expired":
                    OperatorReview.objects.filter(pk=review.pk).update(
                        expires_at=timezone.now() - timedelta(seconds=1),
                    )
                elif condition == "revoked":
                    review.revoke(user=self.staff)
                else:
                    Asset.objects.filter(pk=self.asset.pk).update(visibility=Asset.Visibility.INTERNAL)
                form = OperatorReviewForm(self.payload())
                with self.assertRaises(OperatorReviewUnavailable):
                    form.submit(review)
                Asset.objects.filter(pk=self.asset.pk).update(visibility=Asset.Visibility.PUBLIC)

    def test_approval_is_supplemental_and_never_saves_asset(self):
        before = Asset.objects.filter(pk=self.asset.pk).values().get()
        history_count = self.asset.history.count()
        review = self.submit()
        review.approve(user=self.staff)
        self.assertEqual(Asset.objects.filter(pk=self.asset.pk).values().get(), before)
        self.assertEqual(self.asset.history.count(), history_count)
        self.assertIsNotNone(review.approved_at)
        self.assertEqual(review.approved_by, self.staff)
        public = get_public_operator_details(self.asset)
        self.assertEqual(set(public), set(PUBLIC_FIELD_LIMITS))
        self.assertEqual(public["contact_email"], "public@example.test")
        for private_value in ("private@example.test", "Private Person", str(review.token)):
            self.assertNotIn(private_value, str(public))
        self.assertNotIn("approved_at", public)
        self.assertEqual(len(mail.outbox), 0)
        with self.assertRaises(OperatorReviewUnavailable):
            review.approve(user=self.staff)

    def test_changed_asset_field_blocks_approval_without_overwriting(self):
        review = self.submit()
        Asset.objects.filter(pk=self.asset.pk).update(contact_email="editor-change@example.test")
        with self.assertRaises(OperatorReviewConflict):
            review.approve(user=self.staff)
        review.refresh_from_db()
        self.assertIsNone(review.approved_at)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.contact_email, "editor-change@example.test")
        self.assertEqual(get_public_operator_details(self.asset), {})

    def test_changed_taxonomy_blocks_approval(self):
        review = self.submit()
        capability = Capability.objects.create(name="Review test capability", slug="review-test")
        self.asset.capabilities.add(capability)
        with self.assertRaises(OperatorReviewConflict):
            review.approve(user=self.staff)

    def test_sibling_invitation_cannot_replace_newly_accepted_proposal(self):
        first = self.submit()
        sibling = self.submit(self.issue(), use_cases="A sibling proposal")
        first.approve(user=self.staff)
        with self.assertRaises(OperatorReviewConflict):
            sibling.approve(user=self.staff)
        self.assertEqual(get_public_operator_details(self.asset)["use_cases"],
                         self.payload()["use_cases"])

    def test_latest_approved_proposal_is_used_and_remains_after_invite_expiry(self):
        first = self.submit()
        first.approve(user=self.staff)
        latest = self.submit(self.issue(), use_cases="New accepted research scope")
        latest.approve(user=self.staff)
        OperatorReview.objects.filter(pk=latest.pk).update(
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(get_public_operator_details(self.asset)["use_cases"],
                         "New accepted research scope")

    def test_accepted_output_is_hidden_when_asset_baseline_changes(self):
        review = self.submit()
        review.approve(user=self.staff)
        Asset.objects.filter(pk=self.asset.pk).update(test_access="Changed by editorial staff")
        # Deliberately pass the stale instance: the helper must fetch current values.
        self.assertEqual(get_public_operator_details(self.asset), {})

    def test_private_editorial_change_does_not_hide_accepted_public_details(self):
        review = self.submit()
        review.approve(user=self.staff)
        Asset.objects.filter(pk=self.asset.pk).update(internal_notes="An internal-only change")
        self.assertTrue(get_public_operator_details(self.asset))

    def test_revocation_hides_accepted_details(self):
        review = self.submit()
        review.approve(user=self.staff)
        review.revoke(user=self.staff)
        revoked_at = review.revoked_at
        review.revoke(user=self.staff)
        self.assertEqual(review.revoked_at, revoked_at)
        self.assertEqual(get_public_operator_details(self.asset), {})

    def test_unsubmitted_expired_revoked_private_and_nonconsented_cannot_be_approved(self):
        for state in ("unsubmitted", "expired", "revoked", "private", "no-consent"):
            with self.subTest(state=state):
                review = self.issue() if state == "unsubmitted" else self.submit()
                if state == "expired":
                    OperatorReview.objects.filter(pk=review.pk).update(
                        expires_at=timezone.now() - timedelta(seconds=1),
                    )
                elif state == "revoked":
                    review.revoke(user=self.staff)
                elif state == "private":
                    Asset.objects.filter(pk=self.asset.pk).update(visibility=Asset.Visibility.INTERNAL)
                elif state == "no-consent":
                    # Invalid states are rejected before any write to the database.
                    review.publication_consent = False
                    with self.assertRaises(ValidationError):
                        review.full_clean()
                    continue
                with self.assertRaises(OperatorReviewUnavailable):
                    review.approve(user=self.staff)
                Asset.objects.filter(pk=self.asset.pk).update(visibility=Asset.Visibility.PUBLIC)

    def test_staff_permissions_require_both_changes_for_every_transition_and_admin(self):
        review = self.submit()
        modeladmin = OperatorReviewAdmin(OperatorReview, review_admin_site)
        cases = (
            (True, True, ()), (True, True, ("change_asset",)),
            (True, True, ("change_operatorreview",)),
            (False, True, ("change_asset", "change_operatorreview")),
            (True, False, ("change_asset", "change_operatorreview")),
        )
        for index, (is_staff, is_active, codenames) in enumerate(cases):
            with self.subTest(index=index):
                user = get_user_model().objects.create_user(
                    f"limited-{index}", is_staff=is_staff, is_active=is_active,
                )
                user.user_permissions.add(*Permission.objects.filter(
                    content_type__app_label="assets", codename__in=codenames,
                ))
                for operation in (
                    lambda user=user: OperatorReview.issue(asset=self.asset, created_by=user),
                    lambda user=user: review.approve(user=user),
                    lambda user=user: review.revoke(user=user),
                ):
                    with self.assertRaises(PermissionDenied):
                        operation()
                request = self.request(user)
                self.assertFalse(modeladmin.has_module_permission(request))
                self.assertFalse(modeladmin.has_view_permission(request, review))
                self.assertFalse(modeladmin.has_add_permission(request))
                self.assertFalse(modeladmin.has_change_permission(request, review))
        permitted = get_user_model().objects.create_user("both-changes", is_staff=True)
        permitted.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="assets",
            codename__in=("change_asset", "change_operatorreview"),
        ))
        review.approve(user=permitted)
        self.assertEqual(review.approved_by, permitted)

    def test_guest_form_does_not_echo_token_or_private_data(self):
        review = self.issue()
        response = self.client.get(review.get_absolute_url())
        self.assertContains(response, self.asset.public_name)
        self.assertContains(response, "Public details")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, '<meta name="referrer" content="strict-origin">')
        self.assert_private_headers(response)
        for secret in (str(review.token), self.staff.email, self.asset.internal_notes,
                       self.asset.review_notes, "baseline", "created_by"):
            self.assertNotContains(response, secret)

    def test_guest_submission_success_does_not_echo_any_submitted_values(self):
        review = self.issue()
        response = self.client.post(review.get_absolute_url(), self.payload())
        self.assertContains(response, "Thank you")
        self.assert_private_headers(response)
        for secret in ("Private Person", "private@example.test", str(review.token),
                       self.payload()["use_cases"], "public@example.test"):
            self.assertNotContains(response, secret)
        second = self.client.post(review.get_absolute_url(), self.payload())
        self.assertEqual(second.status_code, 404)
        self.assert_private_headers(second)

    def test_unknown_expired_revoked_submitted_and_private_links_have_same_generic_page(self):
        review = self.issue()
        expected = self.client.get(reverse("core:operator-review", args=(uuid.uuid4(),)))
        self.assertEqual(expected.status_code, 404)
        for state in ("expired", "revoked", "submitted", "private"):
            with self.subTest(state=state):
                if state == "expired":
                    OperatorReview.objects.filter(pk=review.pk).update(
                        expires_at=timezone.now() - timedelta(seconds=1),
                    )
                elif state == "revoked":
                    review.revoke(user=self.staff)
                elif state == "submitted":
                    review = self.submit(self.issue())
                else:
                    review = self.issue()
                    Asset.objects.filter(pk=self.asset.pk).update(visibility=Asset.Visibility.INTERNAL)
                response = self.client.get(review.get_absolute_url())
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.content, expected.content)
                self.assert_private_headers(response)
                self.assertNotContains(response, str(review.token), status_code=404)

    def test_malformed_tokens_are_generic_and_no_store(self):
        response = self.client.get("/operator-review/not-a-valid-token/")
        self.assertEqual(response.status_code, 404)
        self.assert_private_headers(response)
        self.assertNotContains(response, "not-a-valid-token", status_code=404)

    def test_csrf_is_enforced_with_private_headers_and_valid_csrf_works(self):
        review = self.issue()
        client = Client(enforce_csrf_checks=True)
        page = client.get(review.get_absolute_url())
        self.assertEqual(page.status_code, 200)
        failure = client.post(review.get_absolute_url(), self.payload())
        self.assertEqual(failure.status_code, 403)
        self.assert_private_headers(failure)
        review.refresh_from_db()
        self.assertIsNone(review.submitted_at)
        success = client.post(
            review.get_absolute_url(), {
                **self.payload(), "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            }, HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(success.status_code, 200)
        review.refresh_from_db()
        self.assertIsNotNone(review.submitted_at)

    def test_unsupported_methods_have_privacy_headers(self):
        response = self.client.head(self.issue().get_absolute_url())
        self.assertEqual(response.status_code, 405)
        self.assert_private_headers(response)

    def test_guest_html_is_escaped_on_validation_errors(self):
        review = self.issue()
        response = self.client.post(review.get_absolute_url(), self.payload(
            use_cases='<script>alert("unsafe")</script>', publication_consent="",
        ))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("unsafe")</script>')
        self.assert_private_headers(response)

    @override_settings(REQUIRE_SITE_LOGIN=True)
    def test_parent_login_gate_exempts_operator_links(self):
        response = self.client.get(self.issue().get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assert_private_headers(response)

    def test_admin_creates_invite_and_redirects_to_private_token_url(self):
        self.client = Client(HTTP_HOST="localhost:8013")
        self.client.force_login(self.staff)
        expiry = timezone.localtime(timezone.now() + timedelta(days=7))
        response = self.client.post(reverse("operator_test_admin:assets_operatorreview_add"), {
            "asset": str(self.asset.pk), "expires_at_0": expiry.strftime("%Y-%m-%d"),
            "expires_at_1": expiry.strftime("%H:%M:%S"), "_save": "Save",
        })
        review = OperatorReview.objects.get()
        change_url = reverse("operator_test_admin:assets_operatorreview_change", args=(review.pk,))
        self.assertRedirects(response, change_url)
        page = self.client.get(change_url)
        self.assertContains(page, f"http://localhost:8013{review.get_absolute_url()}")
        self.assert_private_headers(page)
        self.assertEqual(review.created_by, self.staff)
        self.assertEqual(len(mail.outbox), 0)

    def test_admin_invitation_origin_is_bound_to_each_request_object(self):
        review = self.issue()
        modeladmin = OperatorReviewAdmin(OperatorReview, review_admin_site)
        first_request = RequestFactory().get("/admin/", HTTP_HOST="localhost:8013")
        first_request.user = self.staff
        second_request = RequestFactory().get("/admin/", HTTP_HOST="127.0.0.1:8014")
        second_request.user = self.staff
        first = modeladmin.get_object(first_request, str(review.pk))
        second = modeladmin.get_object(second_request, str(review.pk))
        self.assertIn(f"http://localhost:8013{review.get_absolute_url()}",
                      modeladmin.invitation_url(first))
        self.assertIn(f"http://127.0.0.1:8014{review.get_absolute_url()}",
                      modeladmin.invitation_url(second))
        self.assertIn(f"http://localhost:8013{review.get_absolute_url()}",
                      modeladmin.invitation_url(first))
        self.assertFalse(hasattr(modeladmin, "_request_invitation_url"))
        self.assertIn(f"https://catalog.example.test{review.get_absolute_url()}",
                      modeladmin.invitation_url(OperatorReview.objects.get(pk=review.pk)))

    def test_admin_proposals_cannot_be_edited_or_deleted(self):
        review = self.submit()
        self.client.force_login(self.staff)
        change_url = reverse("operator_test_admin:assets_operatorreview_change", args=(review.pk,))
        response = self.client.post(change_url, {"proposal": '{"use_cases":"overwrite"}'})
        self.assertEqual(response.status_code, 403)
        review.refresh_from_db()
        self.assertEqual(review.proposal["use_cases"], self.payload()["use_cases"])
        modeladmin = OperatorReviewAdmin(OperatorReview, review_admin_site)
        self.assertFalse(modeladmin.has_delete_permission(self.request(), review))

    def test_admin_actions_guard_conflicts_and_revoke(self):
        review = self.submit()
        modeladmin = OperatorReviewAdmin(OperatorReview, review_admin_site)
        request = self.request()
        queryset = OperatorReview.objects.filter(pk=review.pk)
        Asset.objects.filter(pk=self.asset.pk).update(contact_text="Changed by editor")
        modeladmin.approve_proposals(request, queryset)
        review.refresh_from_db()
        self.assertIsNone(review.approved_at)
        modeladmin.revoke_invitations(request, queryset)
        review.refresh_from_db()
        self.assertIsNotNone(review.revoked_at)
        with self.assertRaises(PermissionDenied):
            modeladmin.revoke_invitations(self.request(method="get"), queryset)

    def test_asset_admin_action_creates_one_public_invite_and_shows_admin_page(self):
        modeladmin = review_admin_site._registry[Asset]
        response = create_operator_review_invitation(
            modeladmin, self.request(), Asset.objects.filter(pk=self.asset.pk),
        )
        review = OperatorReview.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse(
            "operator_test_admin:assets_operatorreview_change", args=(review.pk,),
        ))
        self.assert_private_headers(response)
        self.assertEqual(len(mail.outbox), 0)
