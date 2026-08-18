from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.assets.models import Asset, SavedView, UpdateSubmission
from apps.catalog.models import Region


class CoreViewTests(TestCase):
    def test_map_shell_renders(self):
        response = self.client.get(reverse("core:map"))
        self.assertContains(response, "Virginia Asset Map")
        self.assertContains(response, "Asset intelligence")
        self.assertContains(response, 'id="map"')
        self.assertContains(response, 'id="asset-layer-toggle"')
        self.assertContains(response, 'id="county-layer-toggle"')
        self.assertContains(response, 'id="region-layer-toggle"')
        self.assertContains(response, 'id="heliport-layer-toggle"')
        self.assertContains(response, 'id="state-boundary-toggle"')
        self.assertContains(response, 'id="verification-layer-toggle"')
        self.assertContains(response, 'id="precision-layer-toggle"')
        self.assertContains(response, 'id="nearby-search"')
        self.assertContains(response, 'id="presentation-view"')
        self.assertContains(response, "Save / export")
        self.assertContains(response, "Analyze")
        self.assertContains(response, "Layers")
        self.assertContains(response, 'data-active-filter-bar')
        self.assertContains(response, 'data-active-filter-chips')
        self.assertContains(response, "data-regions-url=")
        self.assertContains(response, "data-heliports-url=")
        self.assertContains(response, "data-state-boundary-url=")
        self.assertNotContains(response, 'id="relationship-layer-toggle"')
        self.assertNotContains(response, "data-relationships-url=")
        self.assertNotContains(response, 'data-region-quick-filter="hampton-roads"')
        self.assertNotContains(response, ">Network</a>")

    def test_relationship_network_page_is_not_public(self):
        self.assertEqual(self.client.get("/relationships/").status_code, 404)

    def test_health_endpoint(self):
        self.assertEqual(self.client.get(reverse("core:health")).json(), {"status": "ok"})

    def test_directory_renders_without_javascript(self):
        response = self.client.get(reverse("core:directory"), {"q": "test"})
        self.assertContains(response, "Asset directory")
        self.assertContains(response, 'class="directory-list"')
        self.assertNotContains(response, 'data-region-quick-filter="hampton-roads"')

    def test_hampton_roads_filter_limits_directory_results(self):
        hampton_roads = Region.objects.create(name="Hampton Roads")
        greater_richmond = Region.objects.create(name="Greater Richmond")
        Asset.objects.create(
            name="Hampton Roads Test Asset",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A Hampton Roads public listing.",
            unmanned_systems_relevance="Supports autonomous systems.",
            region=hampton_roads,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Asset.objects.create(
            name="Richmond Test Asset",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A Richmond public listing.",
            unmanned_systems_relevance="Supports autonomous systems.",
            region=greater_richmond,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )

        response = self.client.get(
            reverse("core:directory"), {"region": "hampton-roads"}
        )

        self.assertContains(response, "Hampton Roads Test Asset")
        self.assertNotContains(response, "Richmond Test Asset")
        self.assertContains(response, 'href="/directory/"')
        self.assertContains(
            response,
            '<option value="hampton-roads" selected>Hampton Roads</option>',
            html=True,
        )

    def test_directory_supports_predictable_sorting(self):
        Asset.objects.create(
            name="Alpha University",
            record_type=Asset.RecordType.UNIVERSITY,
            short_description="A published university record.",
            unmanned_systems_relevance="Supports autonomous systems education.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Asset.objects.create(
            name="Zulu Organization",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A published organization record.",
            unmanned_systems_relevance="Supports autonomous systems development.",
            status=Asset.Status.SOURCE_BACKED,
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

    def test_directory_pagination_uses_a_valid_query_string(self):
        for index in range(13):
            Asset.objects.create(
                name=f"Pagination Asset {index:02}",
                record_type=Asset.RecordType.ORGANIZATION,
                short_description="A public listing used to verify pagination.",
                unmanned_systems_relevance="Supports autonomous systems.",
                status=Asset.Status.SOURCE_BACKED,
                visibility=Asset.Visibility.PUBLIC,
            )
        response = self.client.get(reverse("core:directory"))
        self.assertContains(response, 'href="?page=2"')
        self.assertNotContains(response, "??page=2")

    def test_regional_comparison_renders(self):
        Region.objects.create(name="Hampton Roads")
        Region.objects.create(name="Northern Virginia")
        response = self.client.get(reverse("core:region-compare"))
        self.assertContains(response, "Regional comparison")
        self.assertContains(response, "Data confidence")
        self.assertContains(response, "Leading capabilities")
        self.assertContains(response, "documented inventory")

    def test_about_data_renders(self):
        response = self.client.get(reverse("core:about-data"))
        self.assertContains(response, "About the data")
        self.assertContains(response, "Editorial review")
        self.assertContains(response, "Suggest an update")
        self.assertNotContains(response, "Verification range")

    def test_asset_detail_includes_public_record_history(self):
        asset = Asset.objects.create(
            name="History Test Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="A public history test.",
            overview="A fuller source-backed profile of the public test asset.",
            unmanned_systems_relevance="Supports autonomous systems testing.",
            contact_text="Facility public information",
            contact_phone="757-555-0100",
            contact_email="contact@example.org",
            contact_url="https://example.org/contact",
            activity_status=Asset.ActivityStatus.ACTIVE,
            current_activity="A current source-backed pilot is underway.",
            partnership_opportunities="Public partner inquiries are accepted.",
            activity_source_url="https://example.org/activity",
            activity_last_verified_at=date(2026, 8, 6),
            owner_operator="Example site operator",
            available_acreage="8.00",
            development_status=Asset.DevelopmentStatus.OPERATIONAL,
            development_notes="The published test site is operational.",
            infrastructure_access="Road and utility access.",
            development_source_url="https://example.org/development",
            development_last_verified_at=date(2026, 8, 6),
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        asset.short_description = "An updated public history test."
        asset.save()

        response = self.client.get(reverse("core:asset-detail", args=[asset.slug]))

        self.assertContains(response, "Record history")
        self.assertContains(response, 'class="detail-disclosure record-history-disclosure"')
        self.assertNotContains(response, 'class="detail-disclosure record-history-disclosure" open')
        self.assertContains(response, 'class="detail-disclosure sources-disclosure"')
        self.assertContains(response, "2 entries")
        self.assertContains(response, "Record added")
        self.assertContains(response, "Short Description")
        self.assertContains(response, "What this asset is")
        self.assertContains(response, "Contact and information")
        self.assertContains(response, "757-555-0100")
        self.assertContains(response, "contact@example.org")
        self.assertContains(response, "Current activity and collaboration")
        self.assertContains(response, "A current source-backed pilot is underway")
        self.assertContains(response, "Site readiness")
        self.assertContains(response, "8 acres")

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
            status=Asset.Status.SOURCE_BACKED,
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


@override_settings(PUBLIC_REGION_SLUG="hampton-roads", PUBLIC_SCOPE_NAME="Hampton Roads")
class ScopedPublicSiteTests(TestCase):
    def setUp(self):
        self.hampton_roads = Region.objects.create(name="Hampton Roads")
        self.greater_richmond = Region.objects.create(name="Greater Richmond")
        self.regional = Asset.objects.create(
            name="Public Hampton Roads Asset",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A Hampton Roads public listing.",
            unmanned_systems_relevance="Supports autonomous systems.",
            region=self.hampton_roads,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        self.outside = Asset.objects.create(
            name="Private Statewide Working Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="A statewide working listing.",
            unmanned_systems_relevance="Supports autonomous systems.",
            region=self.greater_richmond,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )

    def test_public_map_and_directory_are_region_scoped(self):
        map_response = self.client.get(reverse("core:map"))
        self.assertEqual(map_response.context["total_assets"], 1)
        self.assertContains(map_response, "Hampton Roads ecosystem")
        self.assertContains(map_response, "Hampton Roads Asset Map")
        self.assertNotContains(map_response, 'data-region-quick-filter="hampton-roads"')
        self.assertNotContains(map_response, 'name="region"')
        self.assertNotContains(map_response, ">Regions</a>")

        directory_response = self.client.get(
            reverse("core:directory"), {"region": self.greater_richmond.slug}
        )
        self.assertContains(directory_response, self.regional.name)
        self.assertNotContains(directory_response, self.outside.name)
        self.assertEqual(directory_response.context["result_count"], 1)

    def test_out_of_scope_public_pages_are_not_found(self):
        self.assertEqual(
            self.client.get(
                reverse("core:asset-detail", args=[self.outside.slug])
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get(reverse("core:region-compare")).status_code, 404)

    def test_about_page_describes_regional_release(self):
        response = self.client.get(reverse("core:about-data"))
        self.assertContains(response, "Hampton Roads unmanned-systems ecosystem")
        self.assertContains(response, "<dd>Hampton Roads</dd>", html=True)
        self.assertContains(response, "<span>covered region</span>", html=True)

    def test_staff_admin_retains_statewide_working_records(self):
        user = get_user_model().objects.create_superuser(
            "regional-admin", "admin@example.org", "test-password"
        )
        self.client.force_login(user)
        response = self.client.get(reverse("admin:assets_asset_changelist"))

        self.assertContains(response, self.regional.name)
        self.assertContains(response, self.outside.name)
        self.assertEqual(Asset.objects.count(), 2)
        self.assertEqual(Asset.public.count(), 1)


@override_settings(REQUIRE_SITE_LOGIN=True)
class PrivateSiteTests(TestCase):
    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse("core:map"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('core:map')}",
            fetch_redirect_response=False,
        )

    def test_login_redirect_target_is_available(self):
        response = self.client.get(reverse("core:map"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(f"{reverse('login')}?next=%2Fmap%2F", 302)],
        )
        self.assertContains(response, "Sign in")

    def test_health_check_remains_public(self):
        self.assertEqual(self.client.get(reverse("core:health")).status_code, 200)

    def test_authenticated_user_can_open_site(self):
        user = get_user_model().objects.create_user("member", password="test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("core:map"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<form method="post" action="{reverse("logout")}" class="nav-logout">',
        )
        self.assertContains(response, "Sign out")


class SavedViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("owner", password="test-password")
        self.other = get_user_model().objects.create_user("other", password="test-password")

    def test_saved_view_is_private_until_sharing_is_enabled(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("core:saved-views"),
            {
                "name": "Hampton Roads universities",
                "view_type": SavedView.ViewType.DIRECTORY,
                "query_string": "region=hampton-roads&record_type=university",
            },
        )
        self.assertRedirects(response, reverse("core:saved-views"))
        saved_view = SavedView.objects.get(owner=self.owner)

        self.client.force_login(self.other)
        private_response = self.client.get(
            reverse("core:open-saved-view", args=[saved_view.share_token])
        )
        self.assertEqual(private_response.status_code, 403)

        saved_view.is_shared = True
        saved_view.save()
        shared_response = self.client.get(
            reverse("core:open-saved-view", args=[saved_view.share_token])
        )
        self.assertRedirects(
            shared_response,
            "/directory/?region=hampton-roads&record_type=university",
            fetch_redirect_response=False,
        )

    def test_saved_map_view_reopens_with_position_zoom_and_layers(self):
        self.client.force_login(self.owner)
        query_string = (
            "region=hampton-roads&record_type=university"
            "&map_lat=36.91235&map_lon=-76.30123&map_zoom=11"
            "&map_layers=assets%2Cstate%2Cmpz%2Ccounties%2Cheliports%2C"
            "controlled-airspace%2Cuas-facility-map%2Cflight-constraints%2C"
            "uas-test-sites%2Cverification"
            "&map_layers_v=5&map_basemap=light"
        )
        response = self.client.post(
            reverse("core:saved-views"),
            {
                "name": "Hampton Roads university map",
                "view_type": SavedView.ViewType.MAP,
                "query_string": query_string,
            },
        )
        self.assertRedirects(response, reverse("core:saved-views"))
        saved_view = SavedView.objects.get(owner=self.owner)

        response = self.client.get(
            reverse("core:open-saved-view", args=[saved_view.share_token])
        )
        self.assertRedirects(
            response,
            f"/map/?{query_string}",
            fetch_redirect_response=False,
        )

    def test_saved_map_view_reopens_with_polygon_analysis(self):
        self.client.force_login(self.owner)
        query_string = (
            "region=hampton-roads&map_lat=36.9&map_lon=-76.3&map_zoom=9"
            "&map_layers=assets%2Cstate&map_layers_v=3&map_basemap=street"
            "&map_analysis=polygon%7C36.8%2C-76.4%3B36.8%2C-76.2%3B37.0%2C-76.3"
        )
        response = self.client.post(
            reverse("core:saved-views"),
            {
                "name": "Saved polygon",
                "view_type": SavedView.ViewType.MAP,
                "query_string": query_string,
            },
        )
        self.assertRedirects(response, reverse("core:saved-views"))
        saved_view = SavedView.objects.get(owner=self.owner)
        response = self.client.get(
            reverse("core:open-saved-view", args=[saved_view.share_token])
        )
        self.assertRedirects(
            response,
            f"/map/?{query_string}",
            fetch_redirect_response=False,
        )

    def test_saved_map_view_rejects_invalid_analysis_geometry(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("core:saved-views"),
            {
                "name": "Invalid polygon",
                "view_type": SavedView.ViewType.MAP,
                "query_string": "map_analysis=polygon%7C36.8%2C-76.4%3Binvalid",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid saved map analysis")
        self.assertFalse(SavedView.objects.exists())
