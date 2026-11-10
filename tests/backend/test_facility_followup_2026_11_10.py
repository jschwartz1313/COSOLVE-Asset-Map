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
    FACILITY_FOLLOWUP_PROFILES_PATH,
    FACILITY_PROFILES_PATH,
    apply_reviewed_corrections,
)


def manifest():
    return json.loads(FACILITY_FOLLOWUP_PROFILES_PATH.read_text())


def records():
    return {r["name"]: r for r in json.loads(
        (settings.BASE_DIR / "data/virginia_real_assets.json").read_text()
    )["records"]}


class RemainingFacilityEvidenceTests(SimpleTestCase):
    def test_30_profiles_have_evidence_and_rebuild_without_other_field_changes(self):
        payload = manifest()
        catalog = records()
        changes = payload["corrections"]
        self.assertEqual(len(changes), 30)
        self.assertEqual(len({c["name"] for c in changes}), 30)
        self.assertEqual(len(payload["groups"]["manufacturing-and-integration"]), 12)
        self.assertEqual(len(payload["groups"]["testing-and-research"]), 18)
        for path in (FACILITY_PROFILES_PATH, FACILITY_DETAIL_PROFILES_PATH):
            previous = json.loads(path.read_text())["corrections"]
            self.assertFalse({c["name"] for c in previous} & {c["name"] for c in changes})
        allowed = {"overview", "short_description", "website_url", "contact_url",
                   "contact_text", "contact_phone", "contact_email"}
        for change in changes:
            with self.subTest(asset=change["name"]):
                self.assertEqual(set(change["before"]), set(change["after"]))
                self.assertTrue(change["after"].keys() <= allowed)
                for baseline in change.get("accepted_baselines", []):
                    self.assertEqual(set(baseline), set(change["before"]))
                record = catalog[change["name"]]
                self.assertGreaterEqual(len(record["overview"].split()), 100)
                self.assertEqual(len(record["overview"].split("\n\n")), 2)
                self.assertNotIn("Public sources support its classification", record["overview"])
                for field, value in change["after"].items():
                    self.assertEqual(record[field], value, field)
                urls = {s["url"] for s in record["sources"]}
                self.assertTrue(change["add_sources"])
                self.assertIn(record["contact_url"], urls)
                for source in change["add_sources"]:
                    self.assertIn(source["url"], urls)
        rebuilt = deepcopy(list(catalog.values()))
        apply_reviewed_corrections(rebuilt)
        self.assertEqual(rebuilt, list(catalog.values()))
        release = (settings.BASE_DIR / "release.sh").read_text()
        self.assertLess(release.index("data/facility_profiles_2026_11_10.json"),
                        release.index("data/facility_profiles_2026_11_10_followup.json"))
        self.assertLess(release.index("data/facility_profiles_2026_11_10_followup.json"),
                        release.index("python manage.py enrich_asset_profiles"))

    def test_real_access_rules_and_maturity_are_not_replaced_by_guessed_availability(self):
        catalog = records()
        self.assertIn("final assembly and testing take place in Virginia",
                      catalog["Allocortech"]["overview"])
        self.assertIn("registration and export approval",
                      catalog["Curtiss-Wright Defense Solutions Ashburn"]["overview"])
        self.assertIn("lab-manager supervision", catalog["JMU X-Labs"]["overview"])
        self.assertIn("not a water tank", catalog["JMU X-Labs"]["overview"])
        self.assertIn("government sponsorship",
                      catalog["NSWC Dahlgren Outdoor Autonomy Laboratory"]["overview"])
        self.assertEqual(catalog["Center for Unmanned Aircraft Systems at Virginia Tech"][
            "activity_status"], "historical")
        self.assertEqual(catalog["JMU Drone Challenge"]["activity_status"], "historical")
        self.assertEqual(catalog["Hampton Roads Mobility Innovation Center"]["activity_status"],
                         "developing")
        self.assertIn("not evidence of a Virginia wafer foundry",
                      catalog["Polaris Semiconductor"]["overview"])
        self.assertEqual(catalog["Newport News Park Radio Control Club Flying Field"][
            "contact_email"], "nnprcc@gmail.com")
        for change in manifest()["corrections"]:
            self.assertFalse(any(key.startswith("test_") for key in change["after"]))


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class RemainingFacilityCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        catalog = records()
        for change in manifest()["corrections"]:
            record = catalog[change["name"]]
            asset = Asset(
                status="source-backed", visibility="public",
                region=Region.objects.get_or_create(name=record["region"])[0],
                internal_notes=f"Catalog provenance: {change['provenance']}.",
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
        call_command("apply_catalog_corrections", corrections=FACILITY_FOLLOWUP_PROFILES_PATH,
                     stdout=output)
        return output.getvalue()

    def test_changes_apply_once_and_preserve_locations_review_state_and_status(self):
        before = {a.name: (a.latitude, a.longitude, a.status) for a in Asset.objects.all()}
        self.assertIn("Applied 30 catalog corrections; preserved 0 conflicts", self.apply())
        for change in manifest()["corrections"]:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                self.assertTrue(same_value(current_value(asset, field), value), (asset.name, field))
            asset.full_clean()
            self.assertEqual((asset.latitude, asset.longitude, asset.status), before[asset.name])
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
            self.assertNotContains(self.client.get(asset.get_absolute_url()), "Catalog updated")
        history = Asset.history.count(), Source.history.count()
        self.assertIn("Applied 0 catalog corrections; preserved 0 conflicts", self.apply())
        self.assertEqual(history, (Asset.history.count(), Source.history.count()))
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())

    def test_conflicts_human_edits_and_hidden_sources_are_preserved(self):
        staff = Asset.objects.get(name="Allocortech")
        staff._history_user = get_user_model().objects.create_user("remaining-facility-editor")
        staff.overview = "Staff-maintained profile."
        staff.save()
        conflict = Asset.objects.get(name="Linebird")
        conflict.contact_text = "Newer contact routing."
        conflict.save()
        source = Source.objects.get(asset__name="JMU X-Labs",
                                    url="https://www.jmu.edu/jmuxlabs/about/spaces.shtml")
        source.is_public = False
        source.save()
        self.assertIn("Applied 27 catalog corrections; preserved 3 conflicts", self.apply())
        staff.refresh_from_db()
        conflict.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(staff.overview, "Staff-maintained profile.")
        self.assertEqual(conflict.contact_text, "Newer contact routing.")
        self.assertFalse(source.is_public)

    def test_exact_generated_legacy_variants_can_update(self):
        names = set()
        for change in manifest()["corrections"]:
            for baseline in change.get("accepted_baselines", []):
                asset = Asset.objects.get(name=change["name"])
                for field, value in baseline.items():
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
                asset.save()
                names.add(asset.name)
        self.assertEqual(names, {"Institute for Advanced Learning and Research",
                                 "VCU ARVL Robotic Drone System",
                                 "Navy TALSA East Small UAS Training Facility"})
        self.assertIn("Applied 30 catalog corrections; preserved 0 conflicts", self.apply())
