from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.assets.diagrams import SiteDiagram
from apps.assets.models import Asset
from apps.sources.models import Source


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class DecisionToolTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.asset = Asset.objects.create(
            name="Example Manufacturing", record_type="facility", status="source-backed",
            visibility="public", short_description="Virginia prototyping facility",
            unmanned_systems_relevance="Composite test articles", contact_email="info@example.com",
        )
        cls.other = Asset.objects.create(
            name="Example Test Site", record_type="facility", status="source-backed",
            visibility="public", short_description="Research test site",
            unmanned_systems_relevance="Prototype evaluation",
        )
        cls.private = Asset.objects.create(
            name="Internal project", record_type="program", visibility="internal",
            status="source-backed", short_description="Private information",
            unmanned_systems_relevance="Not public",
        )

    def test_compare_preserves_order_and_deduplicates(self):
        response = self.client.get("/compare/", {"asset": [self.other.slug, self.asset.slug,
                                                         self.other.slug]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a.pk for a in response.context["assets"]],
                         [self.other.pk, self.asset.pk])
        self.assertContains(response, "Not documented")

    def test_private_missing_and_region_scoped_records_do_not_leak(self):
        response = self.client.get("/compare/", {"asset": [self.private.slug, "missing"]})
        self.assertEqual(response.context["assets"], [])
        self.assertNotContains(response, self.private.name)
        self.assertEqual(self.client.get(f"/assets/{self.private.slug}/inquiry/").status_code, 404)
        with override_settings(PUBLIC_REGION_SLUG="hampton-roads"):
            response = self.client.get("/compare/", {"asset": self.asset.slug})
            self.assertEqual(response.context["assets"], [])

    def test_too_many_selections_and_invalid_methods_rejected(self):
        self.assertEqual(self.client.get("/compare/", {"asset": list("abcdef")}).status_code, 400)
        self.assertEqual(self.client.post("/compare/").status_code, 405)

    def test_compare_search_is_public_and_preserves_selection(self):
        response = self.client.get("/compare/", {"q": "Manufacturing", "asset": self.other.slug})
        self.assertEqual(response.context["candidates"][0]["asset"], self.asset)
        self.assertIn(self.other.slug, response.context["candidates"][0]["query"])

    def test_csv_escapes_spreadsheet_formula_and_excludes_private_fields(self):
        self.asset.display_name = "=SUM(1,2)"
        self.asset.internal_notes = "Private editorial note"
        self.asset.save()
        response = self.client.get("/compare/", {"asset": self.asset.slug, "download": "csv"})
        self.assertIn("'=SUM", response.content.decode())
        self.assertNotIn("Private editorial note", response.content.decode())

    def test_hidden_or_rejected_test_evidence_not_in_comparison(self):
        self.asset.test_aircraft = "Sensitive test specification"
        self.asset.test_source_url = "https://example.com/specs"
        self.asset.test_last_verified_at = timezone.localdate()
        self.asset.save()
        Source.objects.create(asset=self.asset, title="Private source",
                              url=self.asset.test_source_url, is_public=False)
        response = self.client.get("/compare/", {"asset": self.asset.slug})
        self.assertNotContains(response, self.asset.test_aircraft)

    def test_inquiry_is_draft_only_and_not_persisted(self):
        from django.core import mail
        response = self.client.post(f"/assets/{self.asset.slug}/inquiry/", {
            "purpose": "Evaluate a new prototype", "requirements": "A 3 metre airframe",
            "timing": "Early next year", "organization": "Example buyer",
        })
        self.assertContains(response, "Evaluate a new prototype")
        self.assertContains(response, self.asset.contact_email)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(len(mail.outbox), 0)
        self.asset.refresh_from_db()
        self.assertNotIn("Evaluate a new prototype", self.asset.overview)
        download = self.client.post(f"/assets/{self.asset.slug}/inquiry/", {
            "purpose": "Discuss prototyping", "download": "text",
        })
        self.assertEqual(download.headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("attachment", download.headers["Content-Disposition"])

    def test_invalid_inquiry_and_html_escape(self):
        url = f"/assets/{self.asset.slug}/inquiry/"
        self.assertContains(self.client.post(url, {}), "This field is required")
        response = self.client.post(url, {"purpose": "</textarea><script>alert(1)</script>"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertEqual(self.client.post(url, {"purpose": "x" * 2001}).context["draft"], "")

    def test_approved_operator_contacts_are_consistent_and_private_identity_never_exposed(self):
        from apps.assets.operator_review import OperatorReview

        staff = get_user_model().objects.create_superuser("operator-admin", password=None)
        review = OperatorReview.issue(asset=self.asset, created_by=staff)
        review.submit(proposal={"use_cases": "Operator-supplied prototype evaluation",
                                "contact_email": "projects@example.com"},
                      submitter_name="Private Contact", submitter_email="private@example.com",
                      publication_consent=True)
        review.approve(user=staff)
        for url, params in ((self.asset.get_absolute_url(), {}),
                            (f"/assets/{self.asset.slug}/inquiry/", {}),
                            ("/compare/", {"asset": self.asset.slug})):
            with self.subTest(url=url):
                response = self.client.get(url, params)
                self.assertContains(response, "projects@example.com")
                for private in ("Private Contact", "private@example.com", str(review.token)):
                    self.assertNotContains(response, private)
                self.assertNotContains(response, self.asset.contact_email)
        review.revoke(user=staff)
        self.assertContains(
            self.client.get(self.asset.get_absolute_url()), self.asset.contact_email
        )

    def test_diagrams_require_safe_urls_and_publication_approval(self):
        diagram = SiteDiagram.objects.create(
            asset=self.asset, title="Site overview", image_url="https://example.com/site.png",
            alt_text="Public site diagram", credit="Operator", source_url="https://example.com/site",
        )
        url = self.asset.get_absolute_url()
        self.assertNotContains(self.client.get(url), "Public site diagram")
        diagram.publication_approved = True
        diagram.save()
        self.assertContains(self.client.get(url), "Public site diagram")
        self.assertContains(self.client.get(url), 'referrerpolicy="no-referrer"')
        for image in ("http://example.com/site.png", "https://127.0.0.1/site.png",
                      "https://localhost/site.png", "https://10.0.0.1/site.png",
                      "https://example.com/site.png?secret=abc", "https://example.com/site.svg",
                      "https://username:password@example.com/site.png"):
            diagram.image_url = image
            with self.subTest(image=image), self.assertRaises(ValidationError):
                diagram.full_clean()

    @override_settings(REQUIRE_SITE_LOGIN=True)
    def test_planning_tools_remain_behind_existing_login(self):
        for url in ("/compare/", f"/assets/{self.asset.slug}/inquiry/"):
            self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user("viewer", password="test-unique-password")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/compare/").status_code, 200)
