import json
from copy import deepcopy
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils.html import escape

from apps.api.query import filter_public_assets
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
    MAAP_CORRECTIONS_PATH,
    OCTOBER_WEBSITE_CORRECTIONS_PATH,
    TEST_CAPABILITY_PROFILES_PATH,
    TEST_ENVIRONMENT_EXPANSION_PATH,
    apply_reviewed_corrections,
    finalize_record,
    validate,
)

CATALOG = settings.BASE_DIR / "data/virginia_real_assets.json"


class TestEnvironmentManifestTests(SimpleTestCase):
    def test_profiles_match_catalog_and_have_guarded_evidence(self):
        catalog = json.loads(CATALOG.read_text())
        by_name = {r["name"]: r for r in catalog["records"]}
        changes = json.loads(TEST_CAPABILITY_PROFILES_PATH.read_text())["corrections"]
        followups = {}
        for path in (MAAP_CORRECTIONS_PATH, OCTOBER_WEBSITE_CORRECTIONS_PATH):
            for change in json.loads(path.read_text())["corrections"]:
                followups.setdefault(change["name"], {}).update(change["after"])
        self.assertEqual(len(changes), 29)
        self.assertEqual(len({c["name"] for c in changes}), 29)
        for change in changes:
            with self.subTest(name=change["name"]):
                after = change["after"]
                record = by_name[change["name"]]
                self.assertEqual(set(change["before"]), set(after))
                self.assertTrue(set(after) <= ALLOWED_FIELDS | set(TAXONOMY_FIELDS))
                self.assertFalse({"latitude", "longitude", "status"}.intersection(after))
                self.assertNotIn("Public sources support its classification", after["overview"])
                self.assertTrue(change["add_sources"])
                urls = {s["url"] for s in record["sources"]}
                for field in ("test_source_url", "activity_source_url", "website_url"):
                    expected = followups.get(change["name"], {}).get(field, after.get(field))
                    if expected:
                        self.assertIn(expected, urls)
                for field, value in after.items():
                    expected = followups.get(change["name"], {}).get(field, value)
                    self.assertEqual(record[field], expected)
                for baseline in change.get("accepted_baselines", []):
                    self.assertEqual(set(baseline), set(after))
        validate(
            catalog["records"],
            [(r["from"], r["type"], r["to"]) for r in catalog["relationships"]],
        )

    def test_new_facilities_are_distinct_and_repeatable(self):
        additions = json.loads(TEST_ENVIRONMENT_EXPANSION_PATH.read_text())
        self.assertEqual(additions["record_count"], 5)
        self.assertEqual(len(additions["records"]), 5)
        by_name = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        for record in additions["records"]:
            with self.subTest(name=record["name"]):
                self.assertEqual(by_name[record["name"]], finalize_record(deepcopy(record)))
                self.assertIsNone(record["test_runway_length_ft"])
                self.assertIn(record["website_url"], {s["url"] for s in record["sources"]})
                self.assertIn("Test and operational environments", record["strategic_categories"])
                self.assertEqual(record["test_last_verified_at"], "2026-09-29")
        records = list(by_name.values())
        original = json.dumps(records, sort_keys=True)
        apply_reviewed_corrections(records)
        self.assertEqual(original, json.dumps(records, sort_keys=True))

    def test_uncertain_locations_permissions_and_availability_are_not_invented(self):
        records = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        for name in (
            "Xelevate Luray Mountain Range",
            "NASA Wallops UAS Test and Integration Facility",
        ):
            self.assertIsNone(records[name]["latitude"])
            self.assertIsNone(records[name]["longitude"])
            self.assertEqual(records[name]["location_method"], "unmapped")
        tunnel = records["Virginia Tech Stability Wind Tunnel"]
        self.assertIn("Supporting ecosystem asset", tunnel["strategic_categories"])
        self.assertIn("schedule", tunnel["overview"])
        self.assertNotEqual(tunnel.get("activity_status"), "active")
        longbow = records["Longbow Unmanned Systems Research and Test Center"]
        self.assertEqual(longbow["activity_status"], "")
        self.assertEqual(longbow["partnership_opportunities"], "")
        self.assertIn("2021", longbow["overview"])
        dahlgren = records["NSWC Dahlgren Outdoor Autonomy Laboratory"]
        self.assertNotIn("Unmanned aircraft systems", dahlgren["platform_domains"])
        self.assertIn("government sponsorship", dahlgren["test_access"])


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class TestEnvironmentDeploymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changes = json.loads(TEST_CAPABILITY_PROFILES_PATH.read_text())["corrections"]
        records = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        for change in cls.changes:
            record = records[change["name"]]
            region, _ = Region.objects.get_or_create(name=record["region"])
            asset = Asset(
                name=change["name"],
                region=region,
                status="source-backed",
                visibility="public",
                internal_notes=f"Catalog provenance: {change['provenance']}.",
            )
            for field in Asset._meta.concrete_fields:
                if field.name in record and field.name != "region":
                    value = record[field.name]
                    if isinstance(value, float):
                        value = str(value)
                    setattr(asset, field.name, field.to_python(value))
            for field, value in change["before"].items():
                if field not in TAXONOMY_FIELDS:
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
            asset.save()
            for field, model in TAXONOMY_FIELDS.items():
                for name in change["after"].get(field, []):
                    model.objects.get_or_create(name=name)
                values = change["before"].get(field, record[field])
                getattr(asset, field).set([model.objects.get_or_create(name=n)[0] for n in values])

    def apply(self):
        out = StringIO()
        call_command(
            "apply_catalog_corrections", corrections=TEST_CAPABILITY_PROFILES_PATH, stdout=out
        )
        return out.getvalue()

    def test_applies_once_without_changing_review_status(self):
        self.assertIn("Applied 29", self.apply())
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                self.assertTrue(same_value(current_value(asset, field), value), (asset.name, field))
            self.assertEqual(asset.status, "source-backed")
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
            asset.full_clean()
        counts = Asset.history.count(), Source.objects.count()
        self.assertIn("Applied 0", self.apply())
        self.assertEqual(counts, (Asset.history.count(), Source.objects.count()))
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())

    def test_known_legacy_generated_profiles_can_update(self):
        for change in self.changes:
            if not change.get("accepted_baselines"):
                continue
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["accepted_baselines"][-1].items():
                if field in TAXONOMY_FIELDS:
                    model = TAXONOMY_FIELDS[field]
                    getattr(asset, field).set(
                        [model.objects.get_or_create(name=n)[0] for n in value]
                    )
                else:
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
            asset.save()
        self.assertIn("Applied 29", self.apply())

    def test_staff_private_and_conflicting_values_are_preserved(self):
        staff = Asset.objects.get(name="MITRE National Range")
        original = staff.overview
        staff._history_user = get_user_model().objects.create_user("range-editor")
        staff.save()
        private = Asset.objects.get(name="NASA Langley CERTAIN")
        private.visibility = "internal"
        private.save()
        conflict = Asset.objects.get(name="Torc Robotics")
        conflict.overview = "Locally maintained engineering profile."
        conflict.save()
        self.assertIn("Applied 26", self.apply())
        staff.refresh_from_db()
        private.refresh_from_db()
        conflict.refresh_from_db()
        self.assertEqual(staff.overview, original)
        self.assertEqual(private.visibility, "internal")
        self.assertEqual(conflict.overview, "Locally maintained engineering profile.")

    def test_hidden_source_decision_is_preserved(self):
        asset = Asset.objects.get(name="MITRE National Range")
        original = asset.overview
        Source.objects.create(
            asset=asset,
            title="Staff-hidden source",
            is_public=False,
            url="https://www.mitre.org/news-insights/fact-sheet/mitre-national-range",
        )
        self.assertIn("Applied 28", self.apply())
        asset.refresh_from_db()
        self.assertEqual(asset.overview, original)

    def test_profiles_are_visible_and_searchable_without_new_controls(self):
        self.apply()
        site = Asset.objects.get(name="ODU Maritime Autonomous Systems Test Site")
        response = self.client.get(site.get_absolute_url())
        self.assertContains(response, escape(site.overview))
        self.assertIn(
            site.pk, filter_public_assets(QueryDict("q=jib+crane")).values_list("pk", flat=True)
        )
        self.assertIn(
            Asset.objects.get(name="Blue Vigil").pk,
            filter_public_assets(QueryDict("q=AL1000")).values_list("pk", flat=True),
        )


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class NewTestEnvironmentDeploymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "seed_real_data",
            catalog=TEST_ENVIRONMENT_EXPANSION_PATH,
            add_missing=True,
            stdout=StringIO(),
        )

    def test_seed_is_additive_and_never_marks_new_records_verified(self):
        self.assertEqual(Asset.objects.count(), 5)
        self.assertEqual(Asset.public.count(), 5)
        for asset in Asset.objects.all():
            asset.full_clean()
            self.assertEqual(asset.status, "source-backed")
            self.assertIsNone(asset.reviewed_at)
        tunnel = Asset.objects.get(name="Virginia Tech Stability Wind Tunnel")
        tunnel.overview = "Staff-maintained wind-tunnel profile."
        tunnel.save()
        call_command(
            "seed_real_data",
            catalog=TEST_ENVIRONMENT_EXPANSION_PATH,
            add_missing=True,
            stdout=StringIO(),
        )
        tunnel.refresh_from_db()
        self.assertEqual(tunnel.overview, "Staff-maintained wind-tunnel profile.")
        self.assertEqual(Asset.objects.count(), 5)

    def test_new_profiles_can_be_found_and_have_no_invented_runways(self):
        for asset in Asset.public.all():
            self.assertContains(self.client.get(asset.get_absolute_url()), escape(asset.overview))
        self.assertEqual(filter_public_assets(QueryDict("purpose=testing")).count(), 5)
        self.assertFalse(filter_public_assets(QueryDict("purpose=testing&min_runway=1")).exists())
        results = filter_public_assets(QueryDict("q=crashworthiness"))
        self.assertEqual(
            list(results.values_list("name", flat=True)),
            ["NASA Langley Landing and Impact Research Facility"],
        )
        self.assertEqual(Asset.public.filter(latitude__isnull=True).count(), 2)
