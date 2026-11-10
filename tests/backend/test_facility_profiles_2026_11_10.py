import json
from copy import deepcopy
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.assets.management.commands.apply_catalog_corrections import current_value, same_value
from apps.assets.models import Asset
from apps.catalog.models import Region
from apps.sources.models import Source
from scripts.build_real_asset_catalog import (
    FACILITY_DETAIL_PROFILES_PATH,
    FACILITY_PROFILES_PATH,
    apply_reviewed_corrections,
)


def manifest():
    return json.loads(FACILITY_DETAIL_PROFILES_PATH.read_text())


def records():
    return {
        record["name"]: record
        for record in json.loads(
            (settings.BASE_DIR / "data/virginia_real_assets.json").read_text()
        )["records"]
    }


class FacilityDetailEvidenceTests(SimpleTestCase):
    def test_all_36_profiles_match_evidence_and_rebuild_repeatably(self):
        payload = manifest()
        changes = payload["corrections"]
        catalog = records()
        self.assertEqual(len(changes), 36)
        self.assertEqual(len({c["name"] for c in changes}), 36)
        self.assertEqual(len(payload["groups"]["manufacturing-and-integration"]), 15)
        self.assertEqual(len(payload["groups"]["testing-and-research"]), 21)
        previous = json.loads(FACILITY_PROFILES_PATH.read_text())["corrections"]
        self.assertFalse({c["name"] for c in changes} & {c["name"] for c in previous})
        allowed = {
            "overview", "short_description", "contact_text", "contact_url",
            "contact_email", "contact_phone", "website_url",
        }
        for change in changes:
            with self.subTest(asset=change["name"]):
                self.assertEqual(set(change["before"]), set(change["after"]))
                self.assertTrue(change["after"].keys() <= allowed)
                for baseline in change.get("accepted_baselines", []):
                    self.assertEqual(set(baseline), set(change["before"]))
                record = catalog[change["name"]]
                self.assertGreaterEqual(len(record["overview"].split()), 100)
                self.assertNotIn("Public sources support its classification", record["overview"])
                self.assertEqual(len(record["overview"].split("\n\n")), 2)
                for field, value in change["after"].items():
                    self.assertEqual(record[field], value, field)
                urls = {source["url"] for source in record["sources"]}
                self.assertTrue(change["add_sources"])
                for source in change["add_sources"]:
                    self.assertIn(source["url"], urls)
                if record.get("contact_url"):
                    self.assertIn(record["contact_url"], urls)
        rebuilt = deepcopy(list(catalog.values()))
        apply_reviewed_corrections(rebuilt)
        self.assertEqual(rebuilt, list(catalog.values()))
        release = (settings.BASE_DIR / "release.sh").read_text()
        self.assertLess(release.index("data/facility_profiles_2026_11_06.json"),
                        release.index("data/facility_profiles_2026_11_10.json"))
        self.assertLess(release.index("data/facility_profiles_2026_11_10.json"),
                        release.index("python manage.py enrich_asset_profiles"))

    def test_specific_uses_do_not_invent_open_access_or_acceptance_limits(self):
        catalog = records()
        self.assertEqual(catalog["HII Unmanned Systems Center of Excellence"]["contact_phone"], "")
        self.assertIn("historical Virginia manufacturing footprint",
                      catalog["RapidFlight UAS Manufacturing Headquarters"]["overview"])
        self.assertIn("September 2025",
                      catalog["RapidFlight UAS Manufacturing Headquarters"]["overview"])
        self.assertIn("excludes design and development",
                      catalog["Analytical Mechanics Associates"]["overview"])
        self.assertIn("safety", catalog["NOVA Fab Lab Manassas"]["overview"])
        self.assertIn("20-foot", catalog["Phoenix International Chesapeake Operations"]["overview"])
        self.assertEqual(catalog["HDT Robotics BLADE Fredericksburg Facility"]["contact_phone"],
                         "540-479-8100")
        for name in ("Virginia Tech Advanced Control Systems Lab", "NOVA Fab Lab Manassas"):
            self.assertIsNone(catalog[name].get("test_max_weight_lb"))
            self.assertIsNone(catalog[name].get("test_max_span_ft"))


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class FacilityDetailCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        catalog = records()
        for change in manifest()["corrections"]:
            record = catalog[change["name"]]
            asset = Asset(
                status="source-backed", visibility="public",
                internal_notes=f"Catalog provenance: {change['provenance']}.",
                region=Region.objects.get_or_create(name=record["region"])[0],
            )
            for field in Asset._meta.concrete_fields:
                if field.name in record and field.name != "region":
                    value = record[field.name]
                    setattr(asset, field.name,
                            field.to_python(str(value) if isinstance(value, float) else value))
            for name, value in change["before"].items():
                setattr(asset, name, Asset._meta.get_field(name).to_python(value))
            asset.save()
            for source in record["sources"]:
                Source.objects.create(asset=asset, title=source["title"],
                                      url=source["url"], is_public=True)

    def apply(self):
        output = StringIO()
        call_command("apply_catalog_corrections", corrections=FACILITY_DETAIL_PROFILES_PATH,
                     stdout=output)
        return output.getvalue()

    def test_updates_valid_profiles_once_without_relocating_or_verifying(self):
        positions = {a.name: (a.latitude, a.longitude) for a in Asset.objects.all()}
        self.assertIn("Applied 36 catalog corrections; preserved 0 conflicts", self.apply())
        for change in manifest()["corrections"]:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                self.assertTrue(same_value(current_value(asset, field), value), (asset.name, field))
            asset.full_clean()
            self.assertEqual((asset.latitude, asset.longitude), positions[asset.name])
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
            self.assertEqual(asset.status, "source-backed")
            self.assertNotContains(self.client.get(asset.get_absolute_url()), "Catalog updated")
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())
        before = Asset.history.count(), Source.history.count()
        self.assertIn("Applied 0 catalog corrections; preserved 0 conflicts", self.apply())
        self.assertEqual(before, (Asset.history.count(), Source.history.count()))

    def test_staff_edits_and_hidden_source_decisions_are_preserved(self):
        staff = Asset.objects.get(name="Agricision")
        staff._history_user = get_user_model().objects.create_user("facility-detail-editor")
        staff.overview = "Staff-maintained project information."
        staff.save()
        conflict = Asset.objects.get(name="Aurora Flight Sciences")
        conflict.overview = "A newer independent profile."
        conflict.save()
        source = Source.objects.get(asset__name="Ryzing Technologies",
                                    url="https://ryzingtech.com/manufacturing/")
        source.is_public = False
        source.save()
        self.assertIn("Applied 33 catalog corrections; preserved 3 conflicts", self.apply())
        staff.refresh_from_db()
        conflict.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(staff.overview, "Staff-maintained project information.")
        self.assertEqual(conflict.overview, "A newer independent profile.")
        self.assertFalse(source.is_public)

    def test_only_exact_known_generated_variants_are_accepted(self):
        legacy_names = set()
        for change in manifest()["corrections"]:
            for baseline in change.get("accepted_baselines", []):
                asset = Asset.objects.get(name=change["name"])
                for field, value in baseline.items():
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
                asset.save()
                legacy_names.add(asset.name)
        self.assertEqual(len(legacy_names), 6)
        self.assertIn("Applied 36 catalog corrections; preserved 0 conflicts", self.apply())
