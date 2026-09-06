import csv
import json
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import QueryDict
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.api.query import filter_public_assets
from apps.assets.discovery import RESOURCE_CHOICES, TEST_SPEC_FIELDS
from apps.assets.models import Asset, SavedView
from apps.catalog.models import Capability, MissionArea, Region, StrategicCategory
from apps.imports.services import asset_csv_row, prepare_import_asset
from apps.sources.models import Source


class ResourceDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hampton Roads")
        cls.other_region = Region.objects.create(name="New River Valley")
        cls.user = get_user_model().objects.create_superuser(
            "reviewer", password="test-only-password"
        )
        cls.site = Asset.objects.create(
            name="Documented range",
            record_type="facility",
            short_description="Range",
            unmanned_systems_relevance="Public UAS testing",
            region=cls.region,
            status="source-backed",
            visibility="public",
            activity_status="pilot",
            activity_source_url="https://example.org/activity",
            activity_last_verified_at=date(2026, 9, 6),
            test_aircraft="Small UAS",
            test_dimensions="3000 x 75 ft runway",
            test_runway_length_ft=3000,
            test_access="Operator scheduling required",
            test_source_url="https://example.org/specs",
            test_last_verified_at=date(2026, 9, 6),
        )
        for name in (
            "Test and operational environments",
            "Workforce and talent",
            "Commercialization and capital",
            "Manufacturing facilities",
        ):
            cls.site.strategic_categories.add(StrategicCategory.objects.create(name=name))
        cls.site.capabilities.add(
            Capability.objects.create(name="Safety, policy, regulatory, and airspace integration")
        )
        cls.site.missions.add(MissionArea.objects.create(name="Counter-UAS"))
        cls.unknown = Asset.objects.create(
            name="Workforce program",
            record_type="program",
            short_description="Program",
            unmanned_systems_relevance="Technical workforce",
            region=cls.other_region,
            status="source-backed",
            visibility="public",
        )
        cls.private = Asset.objects.create(
            name="Internal test project",
            record_type="program",
            short_description="Private",
            unmanned_systems_relevance="Do not publish",
            visibility="internal",
            test_runway_length_ft=9000,
            test_source_url="https://example.org/internal",
            test_last_verified_at=date(2026, 9, 6),
        )

    def results(self, query):
        return list(filter_public_assets(QueryDict(query)).values_list("pk", flat=True))

    def test_resource_shortcuts_and_activity_filters(self):
        for purpose, _label in RESOURCE_CHOICES:
            with self.subTest(purpose=purpose):
                expected = self.unknown if purpose == "projects" else self.site
                self.assertEqual(self.results(f"purpose={purpose}"), [expected.pk])
        self.assertEqual(self.results("purpose=testing&activity=pilot"), [self.site.pk])
        self.assertEqual(self.results("purpose=testing&activity=planned"), [])
        self.assertEqual(self.results("activity=undocumented"), [self.unknown.pk])

    def test_runway_filter_excludes_unknown_and_private_records(self):
        self.assertEqual(self.results("min_runway=3000&test_specs=1"), [self.site.pk])
        self.assertEqual(self.results("min_runway=3001"), [])
        for invalid in ("NaN", "-5", "0", "1.5", "999999999999999999999"):
            self.assertEqual(self.results(f"min_runway={invalid}"), [])

    def test_specification_search_and_empty_filters(self):
        self.assertEqual(self.results("q=Operator+scheduling"), [self.site.pk])
        self.assertEqual(
            set(self.results("purpose=&activity=&test_specs=&min_runway=")),
            {self.site.pk, self.unknown.pk},
        )

    @override_settings(PUBLIC_REGION_SLUG="hampton-roads")
    def test_resource_filters_cannot_bypass_regional_release(self):
        self.assertEqual(self.results("purpose=projects&region=new-river-valley"), [])
        self.assertEqual(self.results("purpose=testing&region=new-river-valley"), [self.site.pk])

    def test_specifications_require_evidence_and_positive_length(self):
        for field, value in (
            ("test_source_url", ""),
            ("test_last_verified_at", None),
            ("test_runway_length_ft", 0),
        ):
            site = Asset.objects.get(pk=self.site.pk)
            setattr(site, field, value)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                site.full_clean()

    def test_source_alone_is_not_a_specification(self):
        self.unknown.test_source_url = "https://example.org/no-specs"
        self.unknown.test_last_verified_at = date(2026, 9, 6)
        self.unknown.save()
        self.assertEqual(self.results("test_specs=1"), [self.site.pk])

    def test_old_test_site_evidence_enters_staff_review_queue(self):
        self.site.test_last_verified_at = date(2000, 1, 1)
        self.site.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("imports:data-quality"))
        self.assertIn(self.site, response.context["dynamic_claims_stale"])

    def test_public_pages_api_and_export_agree(self):
        params = {"purpose": "testing", "activity": "pilot", "min_runway": "2500"}
        page = self.client.get(reverse("core:directory"), params)
        self.assertContains(page, self.site.name)
        self.assertNotContains(page, self.unknown.name)
        geo = self.client.get(reverse("api:asset-geojson"), params).json()
        self.assertEqual(geo["result_count"], 1)
        self.assertEqual(
            geo["features"][0]["properties"]["activity_status_label"], "Pilot or demonstration"
        )
        detail = self.client.get(self.site.get_absolute_url())
        self.assertContains(detail, "Testing and access")
        self.assertContains(detail, "3000 ft")
        self.client.force_login(self.user)
        rows = list(
            csv.DictReader(
                StringIO(self.client.get(reverse("imports:export"), params).content.decode())
            )
        )
        self.assertEqual([row["name"] for row in rows], [self.site.name])
        self.assertEqual(rows[0]["test_runway_length_ft"], "3000")

    def test_specifications_round_trip_and_history(self):
        row = {
            key: str(value) if value is not None else ""
            for key, value in asset_csv_row(self.site).items()
        }
        imported = prepare_import_asset(row, self.site)
        for field in TEST_SPEC_FIELDS:
            self.assertEqual(
                getattr(imported, field), getattr(Asset.objects.get(pk=self.site.pk), field)
            )
        imported.save()
        self.assertEqual(imported.history.first().test_runway_length_ft, 3000)

    def test_saved_view_accepts_new_filters(self):
        view = SavedView(
            owner=self.user,
            name="Test sites",
            view_type="map",
            query_string="purpose=testing&activity=pilot&test_specs=1&min_runway=2500",
        )
        view.full_clean()

    def test_filter_metadata_includes_resource_and_lifecycle_choices(self):
        metadata = self.client.get(reverse("api:filter-values")).json()
        self.assertEqual(len(metadata["resources"]), len(RESOURCE_CHOICES))
        self.assertIn({"slug": "planned", "name": "Planned"}, metadata["activity_statuses"])

    @override_settings(REQUIRE_SITE_LOGIN=True)
    def test_connection_page_obeys_private_site_login(self):
        self.assertEqual(self.client.get(reverse("core:connect")).status_code, 302)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("core:connect")), "NASA Langley")


class InterviewCatalogTests(TestCase):
    def test_enrichment_does_not_publish_a_rejected_specification_source(self):
        site = Asset.objects.create(
            name="Virginia Tech Drone Park",
            city="Blacksburg",
            record_type="facility",
            short_description="Test",
            unmanned_systems_relevance="Test",
            status="source-backed",
            visibility="public",
            internal_notes="Catalog provenance: curated-public-source",
        )
        Source.objects.create(
            asset=site,
            title="Rejected operator source",
            url="https://ictas.vt.edu/Facilities/ictas-drone-park.html",
            verification_status="rejected",
        )
        call_command("enrich_asset_profiles", stdout=StringIO())
        site.refresh_from_db()
        self.assertFalse(site.has_test_details)
        self.assertEqual(site.test_source_url, "")

    def test_new_catalog_data_and_guarded_enrichment(self):
        path = settings.BASE_DIR / "data/virginia_real_assets.json"
        catalog = json.loads(path.read_text())
        by_name = {record["name"]: record for record in catalog["records"]}
        self.assertEqual(
            by_name["MARS Unmanned Aircraft Systems Airfield"]["test_runway_length_ft"], 3000
        )
        self.assertIn("2015", by_name["NASA Langley UAS Test Range"]["test_aircraft"])
        for record in catalog["records"]:
            if record.get("test_source_url"):
                self.assertIn(
                    record["test_source_url"], [source["url"] for source in record["sources"]]
                )
        site = Asset.objects.create(
            name="Virginia Tech Drone Park",
            city="Blacksburg",
            record_type="facility",
            short_description="Test",
            unmanned_systems_relevance="Test",
            status="source-backed",
            visibility="public",
            internal_notes="Catalog provenance: curated-public-source",
            test_access="Staff-entered restriction",
            test_source_url="https://example.org/staff",
            test_last_verified_at=date(2026, 9, 1),
        )
        call_command("enrich_asset_profiles", stdout=StringIO())
        site.refresh_from_db()
        self.assertEqual(site.test_access, "Staff-entered restriction")
        self.assertEqual(site.test_dimensions, "")
        self.assertEqual(site.test_source_url, "https://example.org/staff")
