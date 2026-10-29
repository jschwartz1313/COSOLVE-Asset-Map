from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Asset, SavedView, UpdateSubmission
from apps.catalog.models import Region
from apps.sources.models import Source


class CoreViewTests(TestCase):
    def test_map_shell_renders(self):
        response = self.client.get(reverse("core:map"))
        self.assertContains(response, "Virginia Asset Map")
        self.assertContains(response, "Find assets")
        self.assertNotContains(response, "<h1>Asset intelligence</h1>")
        self.assertNotContains(response, '<span class="eyebrow">Public listings</span>')
        self.assertContains(response, 'id="directory-link"', count=1)
        self.assertNotContains(response, ">Directory view</a>")
        self.assertContains(response, 'data-legend-toggle="asset-layer-toggle"', count=6)
        self.assertContains(response, 'data-legend-toggle="county-layer-toggle" hidden')
        self.assertContains(response, 'id="map"')
        self.assertContains(response, 'class="basemap-picker"')
        self.assertContains(response, 'data-basemap-topo-url=')
        self.assertContains(response, 'name="map-basemap"', count=4)
        self.assertNotContains(response, 'class="basemap-options"')
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

    def test_public_pages_only_load_the_standard_design(self):
        for name in ("core:map", "core:directory", "core:about-data", "core:region-compare"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, "js/site-header.js")
                self.assertContains(response, 'class="navigation-menu header-menu"')
                self.assertNotContains(response, "appearance-menu")
                self.assertNotContains(response, "data-theme-choice")
                self.assertNotContains(response, "theme-switcher.js")
                self.assertNotContains(response, "themes.css")
                self.assertNotContains(response, "cosolve-display-mode")
                self.assertNotContains(response, "showcase-cover")

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
        self.assertContains(response, "does not establish that a real-world capability is absent")
        self.assertNotContains(response, 'class="comparison-note"')

    def test_about_data_renders(self):
        response = self.client.get(reverse("core:about-data"))
        self.assertContains(response, "About the data")
        self.assertContains(response, "Editorial review")
        self.assertContains(response, "Suggest an update")
        self.assertNotContains(response, "Verification range")

    @override_settings(PUBLIC_REGION_SLUG="", REQUIRE_SITE_LOGIN=False)
    def test_about_data_counts_public_listings_and_preserves_pending_distinction(self):
        for name, status, visibility, reviewed in (
            ("Reviewed public asset", Asset.Status.PUBLISHED, Asset.Visibility.PUBLIC, True),
            ("Pending public asset", Asset.Status.SOURCE_BACKED, Asset.Visibility.PUBLIC, False),
            ("Internal reviewed asset", Asset.Status.VERIFIED, Asset.Visibility.INTERNAL, True),
            ("Partner pending asset", Asset.Status.SOURCE_BACKED, Asset.Visibility.PARTNER, False),
        ):
            Asset.objects.create(
                name=name,
                record_type=Asset.RecordType.ORGANIZATION,
                short_description="An asset used to check the public listing summary.",
                unmanned_systems_relevance="Supports autonomous systems.",
                status=status,
                visibility=visibility,
                reviewed_at=timezone.now() if reviewed else None,
                last_verified_at=date(2026, 10, 13) if reviewed else None,
            )

        response = self.client.get(reverse("core:about-data"))

        self.assertEqual(response.context["asset_count"], 2)
        self.assertEqual(response.context["reviewed_count"], 1)
        self.assertEqual(response.context["pending_review_count"], 1)
        self.assertContains(
            response,
            "<div><strong>2</strong><span>listed assets</span></div>",
            html=True,
        )
        self.assertContains(response, "<dd>1 records pending</dd>", html=True)
        self.assertNotContains(response, "<span>published assets</span>", html=True)

    def test_asset_detail_preserves_profile_without_public_review_metadata(self):
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
            reviewed_at=timezone.now(),
            last_verified_at=date(2026, 8, 21),
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        asset.short_description = "An updated public history test."
        asset.save()

        response = self.client.get(reverse("core:asset-detail", args=[asset.slug]))

        self.assertNotContains(response, "Record history")
        self.assertNotContains(response, "record-history")
        self.assertNotIn("history_entries", response.context)
        self.assertEqual(asset.history.count(), 2)
        self.assertContains(response, 'class="detail-disclosure supporting-disclosure"')
        self.assertContains(response, "About this asset")
        self.assertContains(response, "Contact and location")
        self.assertContains(response, "757-555-0100")
        self.assertContains(response, "contact@example.org")
        self.assertContains(response, "Current activity and collaboration")
        self.assertContains(response, "A current source-backed pilot is underway")
        self.assertContains(response, "Site readiness")
        self.assertContains(response, "8 acres")
        self.assertNotContains(response, "Review status")
        self.assertNotContains(response, "Editorially reviewed")
        self.assertNotContains(response, "Reviewed Aug 21, 2026")
        self.assertNotContains(response, "Record updated")
        self.assertNotContains(response, "detail-verification-footer")

        staff = get_user_model().objects.create_user(username="history-staff", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("core:asset-detail", args=[asset.slug]))
        self.assertNotContains(response, "Record history")
        self.assertNotContains(response, "record-history")
        self.assertNotContains(response, "Review status")
        self.assertNotContains(response, "Editorially reviewed")
        self.assertNotContains(response, "Reviewed Aug 21, 2026")
        self.assertNotContains(response, "Record updated")
        self.assertNotContains(response, "detail-verification-footer")
        asset.refresh_from_db()
        self.assertTrue(asset.is_editorially_reviewed)
        self.assertEqual(asset.last_verified_at, date(2026, 8, 21))
        self.assertEqual(asset.history.count(), 2)

    def test_asset_web_links_open_new_tabs_without_changing_internal_navigation(self):
        asset = Asset.objects.create(
            name="External Link Test Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="A source-backed public testing facility.",
            unmanned_systems_relevance="Supports autonomous systems testing.",
            website_url="https://example.org/",
            contact_url="https://example.org/contact",
            contact_email="contact@example.org",
            contact_phone="757-555-0100",
            current_activity="Documented testing activity.",
            activity_source_url="https://example.org/activity",
            activity_last_verified_at=date(2026, 10, 16),
            owner_operator="Example operator",
            development_source_url="https://example.org/development",
            development_last_verified_at=date(2026, 10, 16),
            test_aircraft="Small unmanned aircraft.",
            test_source_url="https://example.org/testing",
            test_last_verified_at=date(2026, 10, 16),
            location_source_url="https://example.org/location",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Source.objects.create(
            asset=asset,
            title="Official facility information",
            url="https://example.org/source",
        )

        response = self.client.get(asset.get_absolute_url())

        for url, label in (
            (asset.contact_url, "Open contact information"),
            (asset.activity_source_url, "Activity source"),
            (asset.development_source_url, "Development source"),
            (asset.test_source_url, "Operator specification source"),
            (asset.location_source_url, "View location source"),
            ("https://example.org/source", "Official facility information"),
        ):
            with self.subTest(url=url):
                self.assertContains(
                    response,
                    f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>',
                    html=True,
                )
        self.assertContains(
            response,
            '<a class="button primary full" href="https://example.org/" '
            'target="_blank" rel="noopener noreferrer">Visit website</a>',
            html=True,
        )
        for href, label in (
            (reverse("core:directory"), "Directory"),
            ("mailto:contact@example.org", "contact@example.org"),
            ("tel:757-555-0100", "757-555-0100"),
        ):
            self.assertContains(response, f'<a href="{href}">{label}</a>', html=True)

        response = self.client.get(reverse("core:directory"))
        self.assertContains(
            response,
            f'<a href="{asset.get_absolute_url()}">{asset.public_name}</a>',
            html=True,
        )

    def test_profile_layout_keeps_public_details_and_taxonomy_without_editing_data(self):
        asset = Asset.objects.create(
            name="Organized public profile",
            record_type=Asset.RecordType.PROGRAM,
            short_description="A short public summary.",
            overview="The complete published overview remains available.",
            unmanned_systems_relevance="The full documented UxS relevance remains available.",
            contact_text="Public information route; direct contact is not published.",
            contact_phone="757-555-0100",
            contact_email="contact@example.org",
            contact_url="https://example.org/contact",
            website_url="https://example.org/",
            address_line="123 Research Lane",
            city="Hampton",
            state="VA",
            postal_code="23666",
            latitude="37.04",
            longitude="-76.38",
            location_precision=Asset.LocationPrecision.SITE,
            location_method=Asset.LocationMethod.PUBLISHED,
            location_source_url="https://example.org/location",
            location_last_verified_at=date(2026, 10, 21),
            location_notes="The point represents the campus, not a building entrance.",
            current_activity="Documented flight trials are underway.",
            activity_status=Asset.ActivityStatus.ACTIVE,
            partnership_opportunities="Research partners may contact the operator.",
            activity_source_url="https://example.org/activity",
            activity_last_verified_at=date(2026, 10, 21),
            test_aircraft="Small fixed-wing aircraft and multirotors.",
            test_dimensions="A 30-acre documented testing area.",
            test_access="Prior operator permission is required.",
            test_runway_length_ft=1200,
            test_source_url="https://example.org/testing",
            test_last_verified_at=date(2026, 10, 21),
            owner_operator="Example public site operator",
            available_acreage="30.00",
            infrastructure_access="Published road and utility access.",
            development_notes="Availability must be confirmed directly.",
            development_source_url="https://example.org/development",
            development_last_verified_at=date(2026, 10, 21),
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        asset.capabilities.create(name="Documented flight testing")
        asset.missions.create(name="Training and experimentation")
        asset.strategic_categories.create(name="Research and testing")
        asset.platform_domains.create(name="Air")
        Source.objects.create(asset=asset, title="Official program details", url=asset.website_url)
        before = Asset.objects.filter(pk=asset.pk).values().get()
        history_count = asset.history.count()

        response = self.client.get(asset.get_absolute_url())

        for text in (
            asset.public_name,
            asset.short_description,
            asset.overview,
            asset.unmanned_systems_relevance,
            asset.contact_text,
            asset.contact_phone,
            asset.contact_email,
            asset.address_line,
            asset.city,
            asset.postal_code,
            asset.location_notes,
            asset.get_location_precision_display(),
            asset.get_location_method_display(),
            "Documented flight testing",
            asset.current_activity,
            asset.partnership_opportunities,
            asset.test_aircraft,
            asset.test_dimensions,
            asset.test_access,
            "1200 ft",
            asset.owner_operator,
            "30 acres",
            asset.infrastructure_access,
            asset.development_notes,
            "Training and experimentation",
            "Research and testing",
            "Air",
            "Official program details",
            "Suggest an update",
        ):
            with self.subTest(text=text):
                self.assertContains(response, text)
        self.assertContains(response, 'class="overview-section"')
        self.assertContains(response, 'class="focus-section"')
        self.assertContains(response, 'class="detail-taxonomy-list"', count=2)
        self.assertContains(
            response,
            'class="location-evidence"',
        )
        self.assertContains(response, 'class="classification-section"')
        self.assertContains(response, "<h2>About this asset</h2>", html=True)
        self.assertContains(response, "<h2>Capabilities and uses</h2>", html=True)
        self.assertContains(
            response, '<h2 id="contact-location-heading">Contact and location</h2>', html=True
        )
        self.assertContains(response, 'class="detail-disclosure supporting-disclosure"')
        self.assertEqual(response.content.count(b">Visit website</a>"), 1)
        self.assertEqual(Asset.objects.filter(pk=asset.pk).values().get(), before)
        self.assertEqual(asset.history.count(), history_count)

    def test_profile_removes_only_complete_repeated_opening_text_from_presentation(self):
        asset = Asset.objects.create(
            name="Repeated public profile",
            record_type=Asset.RecordType.FACILITY,
            short_description="A public testing site.",
            overview="A public testing site. Its outdoor range supports documented flight trials.",
            unmanned_systems_relevance="A public testing site.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        before = Asset.objects.filter(pk=asset.pk).values().get()
        response = self.client.get(asset.get_absolute_url())
        self.assertEqual(
            response.context["about_paragraphs"],
            ["Its outdoor range supports documented flight trials."],
        )
        self.assertContains(response, '<p class="lead">A public testing site.</p>', html=True)
        self.assertNotContains(response, "<p>A public testing site.</p>", html=True)
        self.assertEqual(Asset.objects.filter(pk=asset.pk).values().get(), before)

    def test_profile_preserves_partial_sentence_prefixes_and_unique_relevance(self):
        for summary, overview in (
            ("Research", "Research and testing facilities support local industry."),
            ("Lab.", "Lab.oratory is the published project name."),
        ):
            with self.subTest(summary=summary):
                asset = Asset.objects.create(
                    name=f"Prefix {summary}",
                    record_type=Asset.RecordType.ORGANIZATION,
                    short_description=summary,
                    overview=overview,
                    unmanned_systems_relevance="Unique published relevance.",
                    status=Asset.Status.SOURCE_BACKED,
                    visibility=Asset.Visibility.PUBLIC,
                )
                response = self.client.get(asset.get_absolute_url())
                self.assertEqual(
                    response.context["about_paragraphs"],
                    [overview, "Unique published relevance."],
                )

    def test_profile_without_an_overview_still_shows_its_relevance(self):
        asset = Asset.objects.create(
            name="Minimal public profile",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A concise summary.",
            unmanned_systems_relevance="Documented relevance without an extended overview.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        response = self.client.get(asset.get_absolute_url())
        self.assertContains(response, "Documented relevance without an extended overview.")
        self.assertNotContains(response, 'class="focus-section"')
        self.assertNotContains(response, 'class="contact-section"')

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
        self.assertContains(map_response, "Find assets")
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
            "uas-test-sites%2Cmaap-flight-areas%2Cverification"
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

    def test_saved_topographic_map_reopens_without_changing_filters(self):
        self.client.force_login(self.owner)
        query_string = (
            "q=airport&region=hampton-roads&map_lat=36.9&map_lon=-76.3&map_zoom=9"
            "&map_layers=assets%2Cstate&map_layers_v=5&map_basemap=topo"
        )
        response = self.client.post(reverse("core:saved-views"), {
            "name": "Topographic airports", "view_type": SavedView.ViewType.MAP,
            "query_string": query_string,
        })
        self.assertRedirects(response, reverse("core:saved-views"))
        saved = SavedView.objects.get(owner=self.owner)
        response = self.client.get(reverse("core:open-saved-view", args=[saved.share_token]))
        self.assertRedirects(response, f"/map/?{query_string}", fetch_redirect_response=False)

    def test_saved_map_rejects_unknown_basemap(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("core:saved-views"), {
            "name": "Unknown map", "view_type": SavedView.ViewType.MAP,
            "query_string": "map_basemap=unrecognized",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported map basemap selection")
        self.assertFalse(SavedView.objects.exists())

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

    def test_saved_map_view_reopens_with_nearby_analysis(self):
        self.client.force_login(self.owner)
        query_string = "q=airport&map_analysis=radius%7C37%2C-77%2C25"
        response = self.client.post(reverse("core:saved-views"), {
            "name": "Nearby airports", "view_type": SavedView.ViewType.MAP,
            "query_string": query_string,
        })
        self.assertRedirects(response, reverse("core:saved-views"))
        saved = SavedView.objects.get(owner=self.owner)
        response = self.client.get(reverse("core:open-saved-view", args=[saved.share_token]))
        self.assertRedirects(response, f"/map/?{query_string}", fetch_redirect_response=False)

    def test_saved_map_view_rejects_invalid_nearby_analysis(self):
        self.client.force_login(self.owner)
        for value in ("radius|37,-77,0", "radius|37,-77,101", "radius|37,-77,nan",
                      "radius|,-77,25", "radius|37,-77,25,5"):
            response = self.client.post(reverse("core:saved-views"), {
                "name": "Invalid nearby", "view_type": SavedView.ViewType.MAP,
                "query_string": f"map_analysis={value}",
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Invalid saved map analysis")
        self.assertFalse(SavedView.objects.exists())
