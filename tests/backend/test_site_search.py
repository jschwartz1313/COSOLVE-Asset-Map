import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.api.query import filter_public_assets
from apps.assets.admin import AssetAdmin
from apps.assets.models import Asset, SavedView
from apps.assets.testing import compare_site
from apps.catalog.models import PlatformDomain
from apps.imports.services import asset_csv_row, prepare_import_asset
from apps.sources.models import Source


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class TestSiteSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = Asset.objects.create(
            name="Documented aircraft site",
            record_type="facility",
            status="source-backed",
            visibility="public",
            short_description="Aircraft test environment",
            unmanned_systems_relevance="Operator-supported aircraft testing",
            test_max_weight_lb=55,
            test_max_weight_exclusive=True,
            test_max_span_ft=12,
            test_launch_methods=["vertical"],
            test_activities=["flight"],
            test_access_types=["commercial", "partnership"],
            test_suitability_source_url="https://operator.example/specifications",
            test_suitability_reviewed_at=timezone.localdate(),
            test_runway_length_ft=1000,
            test_source_url="https://operator.example/runway",
            test_last_verified_at=timezone.localdate(),
        )
        cls.site.platform_domains.add(
            PlatformDomain.objects.create(name="Unmanned aircraft systems")
        )
        cls.evidence = Source.objects.create(
            asset=cls.site,
            title="Operator criteria",
            url=cls.site.test_suitability_source_url,
            is_public=True,
        )
        Source.objects.create(
            asset=cls.site, title="Operator runway", url=cls.site.test_source_url, is_public=True
        )

    def test_no_requirements_does_not_claim_suitability(self):
        self.assertEqual(compare_site(self.site, {})["state"], "reference")

    def test_strict_weight_boundary_and_span(self):
        for weight, expected in (("54.99", "match"), ("55", "conflict"), ("55.01", "conflict")):
            with self.subTest(weight=weight):
                self.assertEqual(
                    compare_site(self.site, {"weight": Decimal(weight)})["state"], expected
                )
        self.assertEqual(compare_site(self.site, {"span": Decimal("12")})["state"], "match")
        self.assertEqual(compare_site(self.site, {"span": Decimal("12.01")})["state"], "conflict")

    def test_unknown_is_not_rejected_or_confirmed(self):
        self.site.test_max_span_ft = None
        self.assertEqual(compare_site(self.site, {"span": Decimal("8")})["state"], "unknown")
        for criteria in ({"launch": "runway"}, {"activity": "counter-uas"}):
            self.assertEqual(compare_site(self.site, criteria)["state"], "unknown")

    def test_launch_and_activity_positive_evidence(self):
        result = compare_site(self.site, {"launch": "vertical", "activity": "flight"})
        self.assertEqual(result["state"], "match")

    def test_runway_uses_its_own_evidence(self):
        self.assertEqual(compare_site(self.site, {"runway": 1000})["state"], "match")
        self.assertEqual(compare_site(self.site, {"runway": 1001})["state"], "conflict")
        Source.objects.filter(url=self.site.test_source_url).update(is_public=False)
        self.assertEqual(compare_site(self.site, {"runway": 1})["state"], "unknown")

    def test_unusable_criteria_sources_never_produce_a_match(self):
        for updates in (
            {"is_public": False},
            {"verification_status": "rejected"},
            {"verification_status": "stale"},
            {"link_review_status": "needs-replacement"},
        ):
            with self.subTest(updates=updates):
                Source.objects.filter(pk=self.evidence.pk).update(
                    is_public=True,
                    verification_status="unreviewed",
                    link_review_status="automatic",
                )
                Source.objects.filter(pk=self.evidence.pk).update(**updates)
                self.assertEqual(
                    compare_site(self.site, {"weight": Decimal("20")})["state"], "unknown"
                )
                self.assertNotIn(
                    self.site,
                    filter_public_assets(
                        self.client.get("/directory/?access=commercial").wsgi_request.GET,
                    ),
                )

    def test_future_or_missing_review_is_unknown(self):
        for reviewed in (None, timezone.localdate() + timedelta(days=1)):
            self.site.test_suitability_reviewed_at = reviewed
            self.assertEqual(compare_site(self.site, {"weight": Decimal("20")})["state"], "unknown")

    def test_pilot_does_not_confirm_operating_availability(self):
        self.site.activity_status = "pilot"
        self.assertEqual(compare_site(self.site, {"launch": "vertical"})["state"], "unknown")

    def test_private_and_historical_sites_are_not_results(self):
        for updates in ({"visibility": "internal"}, {"activity_status": "historical"}):
            Asset.objects.filter(pk=self.site.pk).update(visibility="public", activity_status="")
            Asset.objects.filter(pk=self.site.pk).update(**updates)
            response = self.client.get("/test-sites/?weight=20")
            self.assertEqual(response.context["result_count"], 0)

    @override_settings(PUBLIC_REGION_SLUG="hampton-roads")
    def test_regional_release_does_not_leak_out_of_scope_sites(self):
        response = self.client.get("/test-sites/?weight=20&region=northern-virginia")
        self.assertEqual(response.context["result_count"], 0)

    def test_invalid_inputs_show_errors_not_results(self):
        for query in (
            "weight=-1",
            "weight=NaN",
            "weight=Infinity",
            "span=0",
            "runway=1.5",
            "launch=bogus",
            "access=bogus",
            "weight=1e100",
        ):
            with self.subTest(query=query):
                response = self.client.get("/test-sites/?" + query)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "No comparison has been made")
                self.assertEqual(response.context["result_count"], 0)

    def test_results_export_and_outcome_filter_are_consistent(self):
        query = "weight=55&outcome=conflict&access=commercial"
        response = self.client.get("/test-sites/?" + query)
        self.assertEqual(response.context["result_count"], 1)
        self.assertContains(response, "Published limit conflict")
        exported = self.client.get("/test-sites/?" + query + "&download=csv")
        self.assertIn("text/csv", exported["Content-Type"])
        self.assertIn(b"Documented aircraft site", exported.content)
        self.assertIn(b"Published limit conflict", exported.content)
        self.assertIn(b"operator.example/specifications", exported.content)
        self.assertEqual(
            self.client.get("/test-sites/?weight=55&outcome=match").context["result_count"], 0
        )

    def test_api_and_directory_share_access_filter(self):
        api = self.client.get("/api/assets/?access=commercial").json()
        directory = self.client.get("/directory/?access=commercial")
        self.assertEqual(api["result_count"], 1)
        self.assertEqual(directory.context["result_count"], 1)
        self.assertEqual(
            self.client.get("/api/assets/?access=restricted").json()["result_count"], 0
        )
        saved = SavedView(
            name="Commercial test sites", view_type="map", query_string="access=commercial"
        )
        saved.full_clean(exclude=["owner"])

    def test_source_decisions_hide_structured_api_claims(self):
        self.evidence.is_public = False
        self.evidence.save()
        specs = self.client.get(f"/api/assets/{self.site.slug}/").json()["test_specifications"]
        self.assertIsNone(specs["test_max_weight_lb"])
        self.assertIsNone(specs["test_suitability_source_url"])
        public_row = asset_csv_row(self.site)
        self.assertEqual(public_row["test_max_weight_lb"], "")
        self.assertEqual(public_row["test_suitability_source_url"], "")
        self.assertEqual(json.loads(public_row["test_access_types"]), [])
        self.assertEqual(asset_csv_row(self.site, include_internal=True)["test_max_weight_lb"], 55)

    def test_model_requires_supported_values_and_evidence(self):
        for field, value in (
            ("test_access_types", ["invented"]),
            ("test_activities", [{"bad": "value"}]),
            ("test_launch_methods", ["runway", "runway"]),
            ("test_suitability_source_url", ""),
            ("test_suitability_reviewed_at", None),
        ):
            site = Asset.objects.get(pk=self.site.pk)
            setattr(site, field, value)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                site.full_clean()

    def test_import_export_preserves_structured_choices_and_limits(self):
        row = asset_csv_row(self.site)
        self.assertEqual(json.loads(row["test_access_types"]), ["commercial", "partnership"])
        imported = prepare_import_asset(row, Asset.objects.get(pk=self.site.pk))
        self.assertEqual(imported.test_access_types, self.site.test_access_types)
        self.assertEqual(imported.test_max_weight_lb, self.site.test_max_weight_lb)
        self.assertTrue(imported.test_max_weight_exclusive)
        self.assertEqual(imported.visibility, "internal")

    def test_empty_structured_defaults_do_not_block_legacy_spec_enrichment(self):
        site = Asset.objects.create(
            name="Legacy enrichment fixture",
            record_type="facility",
            status="source-backed",
            visibility="public",
            short_description="Legacy test fixture",
            unmanned_systems_relevance="Testing",
            internal_notes="Catalog provenance: fixture.",
        )
        record = {
            "name": site.name,
            "provenance": "fixture",
            "short_description": "Legacy test",
            "test_aircraft": "Operator test scope",
            "test_source_url": self.site.test_source_url,
            "test_last_verified_at": timezone.localdate().isoformat(),
            "sources": [{"url": self.site.test_source_url, "title": "Operator scope"}],
            "test_max_weight_lb": 500,
        }
        with TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text(json.dumps({"records": [record]}))
            call_command("enrich_asset_profiles", catalog=catalog, stdout=StringIO())
        site.refresh_from_db()
        self.assertEqual(site.test_aircraft, "Operator test scope")
        self.assertIsNone(site.test_max_weight_lb)
        site.full_clean()

    def test_admin_uses_choice_controls(self):
        from django.contrib.admin.sites import AdminSite
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        request = RequestFactory().get("/admin/")
        request.user = get_user_model().objects.create_superuser("criteria-admin", password="test")
        form = AssetAdmin(Asset, AdminSite()).get_form(request, self.site)
        self.assertEqual(
            form.base_fields["test_access_types"].widget.__class__.__name__,
            "CheckboxSelectMultiple",
        )
