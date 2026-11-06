import json
from copy import deepcopy
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.assets.management.commands.apply_catalog_corrections import (
    ALLOWED_FIELDS,
    current_value,
    same_value,
)
from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source
from scripts.build_real_asset_catalog import FACILITY_PROFILES_PATH, apply_reviewed_corrections


def manifest():
    return json.loads(FACILITY_PROFILES_PATH.read_text())


def records():
    return {
        record["name"]: record
        for record in json.loads(
            (settings.BASE_DIR / "data/virginia_real_assets.json").read_text()
        )["records"]
    }


class FacilityProfileEvidenceTests(SimpleTestCase):
    def test_scoped_profiles_are_repeatable_and_have_primary_evidence(self):
        changes = manifest()["corrections"]
        catalog = records()
        self.assertEqual(len(changes), 24)
        self.assertEqual(len({change["name"] for change in changes}), 24)
        previous = json.loads(
            (settings.BASE_DIR / "data/decision_profiles_2026_11_05.json").read_text()
        )
        self.assertFalse(
            {c["name"] for c in changes} & {c["name"] for c in previous["corrections"]}
        )
        forbidden = {
            "status",
            "visibility",
            "reviewed_at",
            "last_verified_at",
            "latitude",
            "longitude",
            "test_max_weight_lb",
            "test_max_span_ft",
            "test_runway_length_ft",
        }
        for change in changes:
            with self.subTest(asset=change["name"]):
                self.assertEqual(set(change["before"]), set(change["after"]))
                self.assertTrue(set(change["after"]) <= ALLOWED_FIELDS)
                self.assertFalse(forbidden & change["after"].keys())
                for baseline in change.get("accepted_baselines", []):
                    self.assertEqual(set(baseline), set(change["before"]))
                record = catalog[change["name"]]
                self.assertGreaterEqual(len(record["overview"].split()), 80)
                urls = {source["url"] for source in record["sources"]}
                self.assertIn(record["contact_url"], urls)
                for source in change["add_sources"]:
                    self.assertIn(source["url"], urls)
                for field, value in change["after"].items():
                    self.assertEqual(record[field], value, field)
        rebuilt = deepcopy(list(catalog.values()))
        apply_reviewed_corrections(rebuilt)
        self.assertEqual(rebuilt, list(catalog.values()))
        release = (settings.BASE_DIR / "release.sh").read_text()
        self.assertLess(
            release.index("data/decision_profiles_2026_11_05.json"),
            release.index("data/facility_profiles_2026_11_06.json"),
        )
        self.assertLess(
            release.index("data/facility_profiles_2026_11_06.json"),
            release.index("python manage.py enrich_asset_profiles"),
        )

    def test_published_equipment_is_not_an_aircraft_acceptance_limit(self):
        catalog = records()
        self.assertIn(
            "not maximum aircraft dimensions",
            catalog["NASA Flight Dynamics Research Facility"]["test_dimensions"],
        )
        self.assertIn("Total building area is not", catalog["HUSH Aerospace"]["overview"])
        self.assertIn(
            "crane rating is not", catalog["ODU Maritime Autonomous Systems Test Site"]["overview"]
        )
        self.assertIn("calibration conditions", catalog["Aeroprobe"]["overview"])
        for name in (
            "HUSH Aerospace",
            "NASA Flight Dynamics Research Facility",
            "NASA Autonomy Lab for Intelligent Flight Systems",
            "ODU Maritime Autonomous Systems Test Site",
        ):
            self.assertIsNone(catalog[name].get("test_max_weight_lb"))
            self.assertIsNone(catalog[name].get("test_max_span_ft"))
        self.assertIsNone(catalog["Xelevate Luray Mountain Range"]["latitude"])
        self.assertIsNone(catalog["Xelevate Luray Mountain Range"]["longitude"])

    def test_existing_activity_announcements_keep_their_specific_citations(self):
        catalog = records()
        for change in manifest()["corrections"]:
            record = catalog[change["name"]]
            if record.get("current_activity") and "activity_source_url" in change["after"]:
                self.assertEqual(
                    change["after"]["activity_source_url"], change["before"]["activity_source_url"]
                )
                self.assertEqual(
                    change["after"]["activity_last_verified_at"],
                    change["before"]["activity_last_verified_at"],
                )

    def test_project_dates_future_capacity_and_contact_scopes_stay_explicit(self):
        catalog = records()
        self.assertIn(
            "completed 2021-22",
            catalog["Global Center for Automotive Performance Simulation"]["overview"],
        )
        self.assertIn(
            "announced future capacity",
            catalog["L3Harris Orange County Propulsion Manufacturing Site"]["overview"],
        )
        self.assertIn(
            "2024", catalog["NASA Autonomy Lab for Intelligent Flight Systems"]["overview"]
        )
        self.assertIn(
            "not a site booking",
            catalog["Wrap Technologies Norton Manufacturing Headquarters"]["contact_text"],
        )
        self.assertEqual(
            catalog["NASA Flight Dynamics Research Facility"]["contact_email"],
            "thomas.g.ivanco@nasa.gov",
        )
        self.assertEqual(
            catalog["Fulcrum Concepts Newport News Machine Shop"]["contact_email"],
            "fulcrummachineshop@fulcrumconceptsllc.com",
        )
        self.assertEqual(
            catalog["UVision USA Stafford Production and Training Center"]["contact_email"], ""
        )


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class FacilityProfileCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        catalog = records()
        for change in manifest()["corrections"]:
            record = catalog[change["name"]]
            asset = Asset(
                status="source-backed",
                visibility="public",
                internal_notes=f"Catalog provenance: {change['provenance']}.",
                region=Region.objects.get_or_create(name=record["region"])[0],
            )
            for field in Asset._meta.concrete_fields:
                if field.name in record and field.name != "region":
                    value = record[field.name]
                    setattr(
                        asset,
                        field.name,
                        field.to_python(str(value) if isinstance(value, float) else value),
                    )
            for name, value in change["before"].items():
                setattr(asset, name, Asset._meta.get_field(name).to_python(value))
            asset.save()
            for field, model in (
                ("strategic_categories", StrategicCategory),
                ("platform_domains", PlatformDomain),
                ("capabilities", Capability),
                ("missions", MissionArea),
            ):
                getattr(asset, field).set(
                    [model.objects.get_or_create(name=name)[0] for name in record[field]]
                )
            for source in record["sources"]:
                Source.objects.create(
                    asset=asset, title=source["title"], url=source["url"], is_public=True
                )

    def apply(self):
        output = StringIO()
        call_command("apply_catalog_corrections", corrections=FACILITY_PROFILES_PATH, stdout=output)
        return output.getvalue()

    def test_updates_valid_profiles_once_without_verifying_or_relocating_assets(self):
        positions = {a.name: (a.latitude, a.longitude) for a in Asset.objects.all()}
        self.assertIn("Applied 24 catalog corrections; preserved 0 conflicts", self.apply())
        for change in manifest()["corrections"]:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                self.assertTrue(same_value(current_value(asset, field), value), (asset.name, field))
            asset.full_clean()
            self.assertEqual((asset.latitude, asset.longitude), positions[asset.name])
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
            response = self.client.get(asset.get_absolute_url())
            self.assertContains(response, "About this asset")
            self.assertNotContains(response, "Catalog updated")
        before = Asset.history.count(), Source.history.count()
        self.assertIn("Applied 0 catalog corrections; preserved 0 conflicts", self.apply())
        self.assertEqual(before, (Asset.history.count(), Source.history.count()))

    def test_staff_text_conflicts_and_hidden_source_decisions_are_preserved(self):
        staff = Asset.objects.get(name="Fulcrum Concepts Newport News Machine Shop")
        staff._history_user = get_user_model().objects.create_user("facility-editor")
        staff.overview = "Staff-maintained manufacturing profile."
        staff.save()
        conflict = Asset.objects.get(name="Radian Forge Portsmouth Manufacturing Facility")
        conflict.overview = "Independent newer manufacturing profile."
        conflict.save()
        Source.objects.filter(
            asset__name="HUSH Aerospace", url="https://www.hush.aero/what-we-do"
        ).update(is_public=False)
        self.assertIn("Applied 21", self.apply())
        staff.refresh_from_db()
        conflict.refresh_from_db()
        self.assertEqual(staff.overview, "Staff-maintained manufacturing profile.")
        self.assertEqual(conflict.overview, "Independent newer manufacturing profile.")
        self.assertFalse(
            Source.objects.get(
                asset__name="HUSH Aerospace", url="https://www.hush.aero/what-we-do"
            ).is_public
        )

    def test_exact_known_catalog_variants_update_without_weakening_staff_guards(self):
        legacy_names = []
        for change in manifest()["corrections"]:
            for baseline in change.get("accepted_baselines", []):
                asset = Asset.objects.get(name=change["name"])
                for field, value in baseline.items():
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
                asset.save()
                legacy_names.append(asset.name)
        self.assertEqual(
            set(legacy_names),
            {
                "HUSH Aerospace",
                "Aeroprobe",
                "Inertial Labs",
                "Volvo Trucks New River Valley Plant",
                "UVA Coastal Research Center UAS Operations",
                "Virginia Tech Transportation Institute",
            },
        )
        self.assertIn("Applied 24 catalog corrections; preserved 0 conflicts", self.apply())

    def test_public_html_evidence_does_not_republish_a_hidden_pdf_version(self):
        asset = Asset.objects.get(name="Wrap Technologies Norton Manufacturing Headquarters")
        hidden = Source.objects.create(
            asset=asset,
            title="Staff-hidden PDF version",
            is_public=False,
            verification_status="stale",
            link_review_status="needs-replacement",
            link_review_notes="Retain the existing decision not to publish this PDF URL.",
            url="https://ir.wrap.com/sec-filings/annual-reports/content/0001140361-26-011401/0001140361-26-011401.pdf",
        )
        self.assertIn("Applied 24", self.apply())
        hidden.refresh_from_db()
        asset.refresh_from_db()
        self.assertFalse(hidden.is_public)
        self.assertEqual(hidden.verification_status, "stale")
        self.assertEqual(hidden.link_review_status, "needs-replacement")
        self.assertEqual(asset.activity_source_url, "https://ir.wrap.com/node/12121/html")
