from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.assets.models import Asset, UpdateSubmission
from apps.catalog.models import Region


class CoreViewTests(TestCase):
    def test_map_shell_renders(self):
        response = self.client.get(reverse("core:map"))
        self.assertContains(response, "Asset intelligence")
        self.assertContains(response, 'id="map"')
        self.assertContains(response, 'id="county-layer-toggle"')
        self.assertContains(response, 'id="state-boundary-toggle"')
        self.assertContains(response, "data-state-boundary-url=")

    def test_health_endpoint(self):
        self.assertEqual(self.client.get(reverse("core:health")).json(), {"status": "ok"})

    def test_directory_renders_without_javascript(self):
        response = self.client.get(reverse("core:directory"), {"q": "test"})
        self.assertContains(response, "Asset directory")
        self.assertContains(response, 'class="directory-list"')

    def test_directory_supports_predictable_sorting(self):
        Asset.objects.create(
            name="Alpha University",
            record_type=Asset.RecordType.UNIVERSITY,
            short_description="A published university record.",
            unmanned_systems_relevance="Supports autonomous systems education.",
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Asset.objects.create(
            name="Zulu Organization",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A published organization record.",
            unmanned_systems_relevance="Supports autonomous systems development.",
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
        )
        response = self.client.get(reverse("core:directory"), {"sort": "type"})
        results = list(response.context["page_obj"].object_list)
        self.assertEqual(
            [asset.name for asset in results], ["Zulu Organization", "Alpha University"]
        )
        self.assertContains(
            response, '<option value="type" selected>Asset type</option>', html=True
        )

    def test_regional_comparison_renders(self):
        Region.objects.create(name="Hampton Roads")
        Region.objects.create(name="Northern Virginia")
        response = self.client.get(reverse("core:region-compare"))
        self.assertContains(response, "Regional comparison")

    def test_about_data_renders(self):
        response = self.client.get(reverse("core:about-data"))
        self.assertContains(response, "About the data")
        self.assertContains(response, "Editorial review")
        self.assertContains(response, "Suggest an update")
        self.assertNotContains(response, "Verification range")

    def test_general_update_submission_enters_staff_queue(self):
        response = self.client.post(
            reverse("core:suggest-update"),
            {
                "kind": UpdateSubmission.Kind.ADDITION,
                "subject": "Example autonomous systems lab",
                "details": "Please consider this Virginia lab for inclusion in the directory.",
                "source_url": "https://example.org/lab",
                "submitter_name": "Alex Morgan",
                "submitter_organization": "Example Organization",
                "submitter_email": "alex@example.org",
                "confirmation": "",
            },
        )
        self.assertRedirects(response, reverse("core:update-thanks"))
        submission = UpdateSubmission.objects.get()
        self.assertEqual(submission.status, UpdateSubmission.Status.NEW)
        self.assertEqual(submission.kind, UpdateSubmission.Kind.ADDITION)
        self.assertIsNone(submission.asset)

    def test_asset_update_submission_is_linked_to_public_record(self):
        asset = Asset.objects.create(
            name="Public Test Asset",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A published test record.",
            unmanned_systems_relevance="Supports autonomous systems development.",
            city="Richmond",
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
        )
        response = self.client.post(
            reverse("core:asset-suggest-update", args=[asset.slug]),
            {
                "details": "The public website now lists a different program name.",
                "source_url": "https://example.org/current-program",
                "submitter_name": "Jordan Lee",
                "submitter_organization": "",
                "submitter_email": "jordan@example.org",
                "confirmation": "",
            },
        )
        self.assertRedirects(response, reverse("core:update-thanks"))
        submission = UpdateSubmission.objects.get()
        self.assertEqual(submission.asset, asset)
        self.assertEqual(submission.subject, asset.name)
        self.assertEqual(submission.kind, UpdateSubmission.Kind.CORRECTION)

    def test_update_honeypot_rejects_automated_submission(self):
        response = self.client.post(
            reverse("core:suggest-update"),
            {
                "kind": UpdateSubmission.Kind.GENERAL,
                "subject": "Automated message",
                "details": "This message has enough content to pass the normal length check.",
                "submitter_name": "Automated Sender",
                "submitter_email": "sender@example.org",
                "confirmation": "https://spam.example",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UpdateSubmission.objects.exists())

    @override_settings(DEBUG=False)
    def test_custom_not_found_page_renders(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)


@override_settings(REQUIRE_SITE_LOGIN=True)
class PrivateSiteTests(TestCase):
    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("core:map"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('core:map')}",
            fetch_redirect_response=False,
        )

    def test_health_check_remains_public(self):
        self.assertEqual(self.client.get(reverse("core:health")).status_code, 200)

    def test_authenticated_user_can_open_site(self):
        user = get_user_model().objects.create_user("member", password="test-password")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("core:map")).status_code, 200)
