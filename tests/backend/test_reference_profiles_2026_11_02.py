import json
from copy import deepcopy
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.api.serializers import asset_feature
from apps.assets.management.commands.apply_catalog_corrections import (
    ALLOWED_FIELDS,
    TAXONOMY_FIELDS,
    current_value,
    same_value,
)
from apps.assets.models import Asset
from apps.catalog.models import Region
from apps.sources.models import Source
from scripts.build_real_asset_catalog import (
    NOVEMBER_REFERENCE_PROFILES_PATH,
    apply_reviewed_corrections,
    validate,
)


def manifest():
    return json.loads(NOVEMBER_REFERENCE_PROFILES_PATH.read_text())


def catalog():
    return json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())


class ReferenceProfileEvidenceTests(SimpleTestCase):
    def test_scoped_manifest_matches_catalog_and_rebuild_is_repeatable(self):
        payload = catalog()
        changes = manifest()["corrections"]
        # Later reviews may supersede these fields; validate this dated pass in isolation.
        dated_records = apply_reviewed_corrections(deepcopy(payload["records"]), changes)
        dated_by_name = {record["name"]: record for record in dated_records}
        self.assertEqual(len(changes), 15)
        self.assertEqual(len({change["name"] for change in changes}), 15)
        for change in changes:
            with self.subTest(name=change["name"]):
                self.assertEqual(set(change["before"]), set(change["after"]))
                self.assertTrue(set(change["after"]) <= ALLOWED_FIELDS | TAXONOMY_FIELDS.keys())
                self.assertFalse(
                    {"status", "reviewed_at", "last_verified_at"} & change["after"].keys()
                )
                self.assertTrue(change["add_sources"])
                record = dated_by_name[change["name"]]
                for field, value in change["after"].items():
                    self.assertEqual(record[field], value, field)
                urls = {source["url"] for source in record["sources"]}
                for source in change["add_sources"]:
                    self.assertIn(source["url"], urls)
                for field in ("website_url", "test_source_url", "location_source_url"):
                    if change["after"].get(field):
                        self.assertIn(change["after"][field], urls)
        rebuilt = deepcopy(payload["records"])
        apply_reviewed_corrections(rebuilt)
        self.assertEqual(payload["records"], rebuilt)
        validate(payload["records"], [
            (edge["from"], edge["type"], edge["to"]) for edge in payload["relationships"]
        ])

    def test_airfield_is_on_the_island_not_the_mainland_airport(self):
        record = next(r for r in catalog()["records"]
                      if r["name"] == "MARS Unmanned Aircraft Systems Airfield")
        self.assertAlmostEqual(record["latitude"], 37.8853, places=5)
        self.assertAlmostEqual(record["longitude"], -75.43706, places=5)
        self.assertEqual(record["location_precision"], "approximate")
        self.assertIn("not the separate mainland", record["location_notes"])
        self.assertIn("90 x 50", record["test_dimensions"])
        self.assertIn("95 x 50", record["test_dimensions"])
        layer = json.loads(
            (settings.BASE_DIR / "static/data/virginia-uas-test-sites.geojson").read_text()
        )
        point = next(f for f in layer["features"] if f["properties"]["name"] == "MARS UAS Airfield")
        self.assertEqual(point["geometry"]["coordinates"],
                         [record["longitude"], record["latitude"]])
        nasa = next(f["properties"] for f in layer["features"]
                    if "CERTAIN" in f["properties"]["name"])
        self.assertIn("800 acres", nasa["published_size"])
        self.assertIn("2024", nasa["published_size"])
        self.assertIn("historical", nasa["published_size"])
        self.assertEqual(layer["metadata"]["generated_at"], "2026-11-02")

    def test_unresolved_sites_stay_unmapped_and_programs_use_actual_operator_pages(self):
        records = {record["name"]: record for record in catalog()["records"]}
        for name in (
            "Xelevate Luray Mountain Range",
            "NASA Wallops UAS Test and Integration Facility",
            "Virginia Tech Corporate Research Center Newport News and Secure Energy Future Center",
        ):
            with self.subTest(name=name):
                self.assertIsNone(records[name]["latitude"])
                self.assertIsNone(records[name]["longitude"])
        self.assertEqual(records["UVA Coastal Research Center UAS Operations"]["platform_domains"],
                         ["Unmanned aircraft systems"])
        self.assertEqual(records["UVA Coastal Research Center UAS Operations"]["website_url"],
                         "https://abcrc.virginia.edu/permits-access-drones")
        training = records["Southern Virginia Higher Education Center Robotics Training"]
        self.assertEqual(training["website_url"],
                         "https://www.svhec.org/job-training/automation/")
        self.assertFalse(records["Smith Mountain Lake"]["website_url"])
        self.assertIn("police component", records["City of Virginia Beach UAS Program"]["overview"])

    def test_faa_retrieval_does_not_redate_maap_or_authorize_flight(self):
        for filename in (
            "virginia-uas-facility-map.geojson", "virginia-surface-controlled-airspace.geojson",
            "virginia-flight-constraints.geojson", "virginia-heliports.geojson",
        ):
            layer = json.loads((settings.BASE_DIR / "static/data" / filename).read_text())
            self.assertGreaterEqual(date.fromisoformat(layer["metadata"]["generated_at"]),
                                    date(2026, 11, 2))
            self.assertEqual(layer["metadata"]["feature_count"], len(layer["features"]))
        maap = json.loads((settings.BASE_DIR / "static/data/maap-flight-areas.geojson").read_text())
        self.assertNotEqual(maap["metadata"]["generated_at"], "2026-11-02")


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class ReferenceProfileCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        records = {record["name"]: record for record in catalog()["records"]}
        cls.changes = manifest()["corrections"]
        for change in cls.changes:
            record = records[change["name"]]
            asset = Asset(
                name=record["name"], status="source-backed", visibility="public",
                region=Region.objects.get_or_create(name=record["region"])[0],
                internal_notes=f"Catalog provenance: {change['provenance']}.",
            )
            for field in Asset._meta.concrete_fields:
                if field.name not in record or field.name == "region":
                    continue
                value = record[field.name]
                value = str(value) if isinstance(value, float) else value
                setattr(asset, field.name, field.to_python(value))
            for name, value in change["before"].items():
                if name in TAXONOMY_FIELDS:
                    continue
                field = Asset._meta.get_field(name)
                if value is None and not field.null:
                    value = field.get_default()
                value = str(value) if isinstance(value, float) else value
                setattr(asset, name, field.to_python(value))
            asset.save()
            for field, model in TAXONOMY_FIELDS.items():
                for name in change["after"].get(field, []):
                    model.objects.get_or_create(name=name)
                values = change["before"].get(field, record[field])
                getattr(asset, field).set([
                    model.objects.get_or_create(name=name)[0] for name in values
                ])

    def apply(self):
        output = StringIO()
        call_command("apply_catalog_corrections", corrections=NOVEMBER_REFERENCE_PROFILES_PATH,
                     stdout=output)
        return output.getvalue()

    def test_applies_valid_profiles_once_without_claiming_editorial_verification(self):
        self.assertIn("Applied 15", self.apply())
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                self.assertTrue(same_value(current_value(asset, field), value), (asset.name, field))
            asset.full_clean()
            self.assertEqual(asset.status, "source-backed")
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())
        before = Asset.history.count(), Source.objects.count()
        self.assertIn("Applied 0", self.apply())
        self.assertEqual(before, (Asset.history.count(), Source.objects.count()))
        spa = Asset.objects.get(name="Systems Planning & Analysis")
        self.assertIsNotNone(asset_feature(spa)["geometry"])

    def test_staff_edits_conflicts_and_source_decisions_are_preserved(self):
        staff = Asset.objects.get(name="Lynk Global")
        staff._history_user = get_user_model().objects.create_user("november-reviewer")
        staff.overview = "Staff-maintained company profile."
        staff.save()
        conflict = Asset.objects.get(name="MARS Unmanned Aircraft Systems Airfield")
        conflict.latitude = "37.880000"
        conflict.save()
        private = Asset.objects.get(name="NASA Langley CERTAIN")
        private.visibility = "internal"
        private.save()
        source_asset = Asset.objects.get(name="UVA Coastal Research Center UAS Operations")
        Source.objects.create(
            asset=source_asset, title="Staff-hidden operator page",
            url="https://abcrc.virginia.edu/permits-access-drones", is_public=False,
        )
        self.assertIn("Applied 11", self.apply())
        staff.refresh_from_db()
        conflict.refresh_from_db()
        private.refresh_from_db()
        source_asset.refresh_from_db()
        self.assertEqual(staff.overview, "Staff-maintained company profile.")
        self.assertIsNone(staff.latitude)
        self.assertEqual(str(conflict.latitude), "37.880000")
        self.assertEqual(str(conflict.longitude), "-75.467000")
        self.assertEqual(private.visibility, "internal")
        self.assertFalse(source_asset.website_url)

    def test_known_generated_contact_placeholders_are_accepted_atomically(self):
        legacy_count = 0
        for change in self.changes:
            for baseline in change.get("accepted_baselines", []):
                self.assertEqual(set(baseline), set(change["before"]))
                asset = Asset.objects.get(name=change["name"])
                for name, value in baseline.items():
                    if name in TAXONOMY_FIELDS:
                        continue
                    field = Asset._meta.get_field(name)
                    if value is None and not field.null:
                        value = field.get_default()
                    value = str(value) if isinstance(value, float) else value
                    setattr(asset, name, field.to_python(value))
                asset.save()
                legacy_count += 1
        self.assertEqual(legacy_count, 4)
        self.assertIn("Applied 15", self.apply())
        self.assertFalse(Asset.objects.filter(
            review_comments__body__startswith="Catalog correction conflict:"
        ).exists())
