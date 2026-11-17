import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.assets.geography import STATES, current_state, internal_preview
from apps.assets.models import Asset, SavedView, UpdateSubmission
from apps.assets.quality import discover_duplicate_candidates
from apps.catalog.models import Capability, MissionArea, Region, StrategicCategory
from apps.imports.services import parse_csv


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="", MULTISTATE_PUBLIC=False)
class MultiStateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser("researcher", "r@example.org", "test")
        cls.guest = get_user_model().objects.create_user("viewer", password="test")
        cls.region = Region.objects.create(name="Hampton Roads")
        base = dict(
            record_type="facility",
            short_description="Documented test facility",
            unmanned_systems_relevance="Autonomy research",
            status="source-backed",
        )
        cls.va = Asset.objects.create(
            name="Virginia site", state="VA", region=cls.region, visibility="public", **base
        )
        cls.oh = Asset.objects.create(
            name="Ohio test site",
            state="OH",
            visibility="internal",
            internal_notes="Multistate starter: OH; research",
            benchmark_starter=True,
            **base,
        )
        cls.ca = Asset.objects.create(
            name="California public site", state="CA", visibility="public", **base
        )
        cls.private = Asset.objects.create(
            name="Unrelated internal Ohio record", state="OH", visibility="internal", **base
        )

    def test_default_remains_virginia_and_request_context_is_reset(self):
        self.client.force_login(self.staff)
        response = self.client.get("/api/assets.geojson")
        self.assertEqual(response.json()["result_count"], 1)
        self.assertEqual(response.json()["features"][0]["properties"]["name"], self.va.name)
        self.assertIsNone(current_state.get())
        self.assertFalse(internal_preview.get())
        self.assertEqual(Asset.public.count(), 2)

    def test_preview_requires_staff_permission_and_does_not_leak_names(self):
        for user in (None, self.guest):
            if user:
                self.client.force_login(user)
            for suffix in (
                "map/",
                "api/assets.geojson",
                "directory/",
                "compare/options/",
                f"assets/{self.oh.slug}/",
            ):
                response = self.client.get("/states/ohio/" + suffix)
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, self.oh.name, status_code=404)
        self.assertEqual(self.client.get(f"/assets/{self.oh.slug}/").status_code, 404)

    def test_staff_preview_scopes_every_query_surface(self):
        self.client.force_login(self.staff)
        prefix = "/states/ohio"
        response = self.client.get(prefix + "/api/assets.geojson")
        self.assertEqual(response.status_code, 200)
        features = response.json()["features"]
        self.assertEqual([f["properties"]["name"] for f in features], [self.oh.name])
        self.assertEqual(
            features[0]["properties"]["detail_url"], prefix + self.oh.get_absolute_url()
        )
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        for suffix in ("directory/", "compare/options/", f"assets/{self.oh.slug}/"):
            response = self.client.get(prefix + "/" + suffix)
            self.assertContains(response, self.oh.name)
            self.assertNotContains(response, self.va.name)
            self.assertNotContains(response, self.private.name)
        response = self.client.get(
            prefix + "/compare/selection/", {"asset": [self.oh.slug, self.va.slug]}
        )
        self.assertEqual([a["slug"] for a in response.json()["assets"]], [self.oh.slug])
        response = self.client.get(prefix + "/admin/imports/export/")
        self.assertContains(response, self.oh.name)
        self.assertNotContains(response, self.va.name)
        response = self.client.get(prefix + "/admin/imports/export/?scope=all")
        self.assertContains(response, self.private.name)
        self.assertNotContains(response, self.va.name)
        response = self.client.get("/admin/imports/export/")
        self.assertContains(response, self.va.name)
        self.assertNotContains(response, self.ca.name)
        self.assertEqual(self.client.get(prefix + f"/assets/{self.va.slug}/").status_code, 404)

    def test_switcher_lists_all_and_keeps_view_without_untrusted_redirect(self):
        self.client.force_login(self.staff)
        response = self.client.get("/map/")
        self.assertContains(response, 'name="state"')
        for state in STATES:
            self.assertContains(response, f'value="{state.slug}"')
        response = self.client.get("/select-state/", {"state": "ohio", "view": "directory"})
        self.assertEqual(response.url, "/states/ohio/directory/")
        response = self.client.get("/select-state/", {"state": "ohio", "view": "https://evil.test"})
        self.assertEqual(response.url, "/states/ohio/map/")
        self.assertEqual(self.client.get("/select-state/?state=unknown").status_code, 404)

    def test_peer_map_uses_own_geometry_and_hides_virginia_layers(self):
        self.client.force_login(self.staff)
        response = self.client.get("/states/ohio/map/")
        self.assertContains(response, "Ohio Asset Map")
        self.assertContains(response, "states/ohio-boundary.geojson")
        self.assertContains(response, "states/ohio-counties.geojson")
        self.assertContains(response, 'data-site-prefix="/states/ohio"')
        self.assertContains(response, "disabled data-unavailable-layer", count=8)
        self.assertNotContains(response, "All Virginia regions")
        self.assertNotContains(response, 'value="hampton-roads"')
        self.assertEqual(self.client.get("/states/ohio/api/filters/").json()["regions"], [])
        self.assertEqual(self.client.get("/states/ohio/references/maap/").status_code, 404)
        self.assertEqual(
            self.client.get("/states/ohio/api/regions/hampton-roads/summary/").status_code, 404
        )

    def test_region_definitions_are_state_specific(self):
        region = Region.objects.create(name="Central Ohio", state="oh")
        self.assertEqual(region.state, "OH")
        self.oh.region = self.region
        with self.assertRaises(ValidationError):
            self.oh.full_clean()
        self.oh.region = region
        self.oh.state = "oh"
        self.oh.save()
        self.assertEqual(self.oh.state, "OH")
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get("/states/ohio/api/filters/").json()["regions"],
            [{"name": region.name, "slug": region.slug}],
        )
        self.assertNotIn(
            region.slug, [row["slug"] for row in self.client.get("/api/filters/").json()["regions"]]
        )

    @override_settings(PUBLIC_REGION_SLUG="hampton-roads", PUBLIC_SCOPE_NAME="Hampton Roads")
    def test_regional_release_setting_does_not_filter_peer_states(self):
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get("/states/ohio/api/assets.geojson").json()["result_count"], 1
        )
        response = self.client.get("/states/ohio/map/")
        self.assertContains(response, "Ohio Asset Map")

    def test_saved_views_reopen_in_original_state_and_keep_old_virginia_urls(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            "/states/ohio/saved-views/",
            {
                "name": "Research",
                "view_type": "map",
                "query_string": "q=test",
                "is_shared": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        saved = SavedView.objects.get(name="Research")
        self.assertEqual(saved.state, "OH")
        response = self.client.get(reverse("core:open-saved-view", args=[saved.share_token]))
        self.assertEqual(response.url, "/states/ohio/map/?q=test")
        va = SavedView.objects.create(owner=self.staff, name="Research", view_type="map")
        response = self.client.get("/states/ohio/saved-views/" + str(va.share_token) + "/")
        self.assertEqual(response.url, "/map/")

    @override_settings(MULTISTATE_PUBLIC=True)
    def test_enabling_public_states_does_not_publish_internal_starters(self):
        self.assertEqual(
            self.client.get("/states/ohio/api/assets.geojson").json()["result_count"], 0
        )
        self.assertEqual(
            self.client.get("/states/california/api/assets.geojson").json()["result_count"], 1
        )
        self.assertEqual(self.client.get(f"/states/ohio/assets/{self.oh.slug}/").status_code, 404)

    def test_unknown_state_paths_are_not_accepted(self):
        self.client.force_login(self.staff)
        for state in ("unknown", "virginia", "OH", "ohio-extra"):
            self.assertEqual(self.client.get(f"/states/{state}/map/").status_code, 404)

    def test_suggestions_record_the_state_without_exposing_a_new_input(self):
        self.client.force_login(self.staff)
        response = self.client.post("/states/ohio/suggest-update/", {
            "kind": "addition", "subject": "Example research resource",
            "details": "Please review this documented Ohio research resource.",
            "submitter_name": "Researcher", "submitter_email": "research@example.org",
            "state": "VA",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(UpdateSubmission.objects.get().state, "OH")


class PeerImportTests(TestCase):
    def test_missing_predefined_peer_vocabulary_is_created_only_when_applying(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "peer.json"
            record = {
                "state": "OH", "name": "Peer vocabulary fixture", "record_type": "facility",
                "short_description": "Research fixture", "unmanned_systems_relevance": "Testing",
                "strategic_categories": [
                    "Digital, data, energy, and communications infrastructure",
                ],
                "capabilities": ["Cybersecurity and resilient systems"],
                "missions": ["Intelligence, surveillance, and reconnaissance",
                             "Mine countermeasures"],
                "sources": [{"title": "Research", "url": "https://example.edu/research/",
                             "supports": "Identity and research capability"}],
            }
            path.write_text(json.dumps({"research_date": "2026-11-17", "records": [record]}))
            call_command("seed_peer_states", catalog=[path], stdout=io.StringIO())
            for model in (StrategicCategory, Capability, MissionArea):
                self.assertFalse(model.objects.exists())
            call_command("seed_peer_states", catalog=[path], apply=True, stdout=io.StringIO())
            asset = Asset.objects.get()
            self.assertEqual(list(asset.strategic_categories.values_list("name", flat=True)),
                             record["strategic_categories"])
            self.assertEqual(list(asset.capabilities.values_list("name", flat=True)),
                             record["capabilities"])
            self.assertCountEqual(asset.missions.values_list("name", flat=True), record["missions"])

    def test_virginia_catalog_does_not_match_another_states_identity(self):
        peer = Asset.objects.create(
            name="Shared research name", city="Springfield", state="OH", record_type="facility",
            short_description="Ohio staff description", unmanned_systems_relevance="Testing",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "virginia.json"
            path.write_text(json.dumps({"records": [{
                "name": peer.name, "city": peer.city, "state": "VA", "record_type": "facility",
                "region": "Virginia test region", "provenance": "test-fixture",
                "short_description": "Virginia catalog description",
                "unmanned_systems_relevance": "Testing", "latitude": None, "longitude": None,
                "location_precision": "locality",
                "strategic_categories": [], "platform_domains": [], "capabilities": [],
                "missions": [], "sources": [],
            }]}))
            call_command("seed_real_data", catalog=path, add_missing=True, stdout=io.StringIO())
        peer.refresh_from_db()
        self.assertEqual(peer.short_description, "Ohio staff description")
        self.assertEqual(Asset.objects.get(state="VA").short_description,
                         "Virginia catalog description")

    def test_csv_identity_lookup_and_duplicates_include_state(self):
        asset = Asset.objects.create(
            name="Autonomy office", city="Springfield", state="VA", record_type="facility",
            short_description="Test fixture", unmanned_systems_relevance="Testing",
        )
        rows, errors = parse_csv(io.BytesIO((
            "name,record_type,short_description,unmanned_systems_relevance,city,state\n"
            "Autonomy office,facility,Fixture,Testing,Springfield,oh\n"
            "Autonomy office,facility,Fixture,Testing,Springfield,VA\n"
        ).encode()))
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["asset_id"], "")
        self.assertEqual(rows[0]["data"]["state"], "OH")
        self.assertEqual(rows[1]["asset_id"], str(asset.pk))
        self.assertFalse(any(row["errors"] for row in rows))

    def test_distinct_state_sites_are_not_duplicate_candidates(self):
        base = {"name": "Autonomy field office", "city": "Springfield",
                "record_type": "facility", "short_description": "Test fixture",
                "unmanned_systems_relevance": "Testing"}
        Asset.objects.create(state="VA", **base)
        Asset.objects.create(state="OH", **base)
        self.assertEqual(discover_duplicate_candidates(), [])
        base["name"] = "Autonomy Field Office"
        Asset.objects.create(state="VA", **base)
        self.assertEqual(len(discover_duplicate_candidates()), 1)

    def test_preview_insert_and_rerun_preserve_editorial_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            document = {
                "research_date": "2026-11-17",
                "records": [
                    {
                        "state": "OH",
                        "name": "Source-backed research site",
                        "record_type": "facility",
                        "city": "Columbus",
                        "short_description": "Documented research resources",
                        "overview": "Research and evaluation",
                        "unmanned_systems_relevance": "Autonomy",
                        "website_url": "https://example.edu/research/",
                        "sources": [
                            {
                                "title": "Research site",
                                "url": "https://example.edu/research/",
                                "supports": "Identity and research scope",
                            }
                        ],
                    }
                ],
            }
            path.write_text(json.dumps(document))
            call_command("seed_peer_states", catalog=[path], stdout=io.StringIO())
            self.assertEqual(Asset.objects.count(), 0)
            call_command("seed_peer_states", catalog=[path], apply=True, stdout=io.StringIO())
            asset = Asset.objects.get()
            self.assertEqual(asset.visibility, "internal")
            self.assertEqual(asset.location_precision, "locality")
            self.assertIsNotNone(asset.latitude)
            self.assertIsNone(asset.reviewed_at)
            self.assertEqual(asset.sources.get().verification_status, "unreviewed")
            asset.overview = "Staff replacement"
            asset.save()
            call_command("seed_peer_states", catalog=[path], apply=True, stdout=io.StringIO())
            asset.refresh_from_db()
            self.assertEqual(asset.overview, "Staff replacement")
            self.assertEqual(Asset.objects.count(), 1)
            asset.delete()
            call_command("seed_peer_states", catalog=[path], apply=True, stdout=io.StringIO())
            self.assertEqual(Asset.objects.count(), 0)
