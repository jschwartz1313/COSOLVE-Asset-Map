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
from apps.assets.testing import compare_site
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source
from scripts.build_real_asset_catalog import DECISION_PROFILES_PATH, apply_reviewed_corrections


def manifest():
    return json.loads(DECISION_PROFILES_PATH.read_text())


def records():
    return {
        record["name"]: record
        for record in json.loads(
            (settings.BASE_DIR / "data/virginia_real_assets.json").read_text()
        )["records"]
    }


class DecisionProfileEvidenceTests(SimpleTestCase):
    def test_review_is_scoped_reproducible_and_does_not_publish_editorial_verification(self):
        changes = manifest()["corrections"]
        catalog = records()
        self.assertEqual(len(changes), 25)
        self.assertEqual(len({change["name"] for change in changes}), 25)
        for change in changes:
            with self.subTest(asset=change["name"]):
                self.assertEqual(set(change["before"]), set(change["after"]))
                for baseline in change.get("accepted_baselines", []):
                    self.assertEqual(set(baseline), set(change["before"]))
                self.assertTrue(set(change["after"]) <= ALLOWED_FIELDS)
                self.assertFalse(
                    {"status", "reviewed_at", "last_verified_at"} & change["after"].keys()
                )
                record = catalog[change["name"]]
                self.assertGreaterEqual(len(record["overview"].split()), 70)
                self.assertTrue(record["contact_url"])
                urls = {source["url"] for source in record["sources"]}
                self.assertIn(record["contact_url"], urls)
                for field, value in change["after"].items():
                    self.assertEqual(record[field], value, field)
                for source in change["add_sources"]:
                    self.assertIn(source["url"], urls)
        rebuilt = deepcopy(list(catalog.values()))
        apply_reviewed_corrections(rebuilt)
        self.assertEqual(rebuilt, list(catalog.values()))

    def test_enclosure_and_tunnel_dimensions_are_not_aircraft_limits(self):
        catalog = records()
        park = catalog["Virginia Tech Drone Park"]
        self.assertEqual(park["test_activities"], ["enclosed"])
        self.assertIn("300 x 120", park["test_dimensions"])
        for name in (
            "Virginia Tech Drone Park",
            "Kentland Experimental Aerial Systems Laboratory",
            "Virginia Tech Counter UAS Research and Testing Center",
            "Virginia Tech Stability Wind Tunnel",
            "NASA Langley CERTAIN",
            "MAAP Kentland Farm Flight Area",
            "MAAP Central Virginia Flight Area",
            "MAAP Blackstone Class D Flight Area",
            "MAAP Eastern Shore Offshore Flight Area",
            "Advanced Aircraft Company",
        ):
            with self.subTest(asset=name):
                self.assertIsNone(catalog[name].get("test_max_weight_lb"))
                self.assertIsNone(catalog[name].get("test_max_span_ft"))

    def test_site_identity_and_uncertain_availability_remain_explicit(self):
        catalog = records()
        liquid = catalog["Liquid Robotics Herndon Headquarters and Production"]
        self.assertEqual(liquid["activity_status"], "")
        self.assertIn("unconfirmed", liquid["short_description"])
        self.assertIn("whether all Herndon production has ceased", liquid["overview"])
        self.assertEqual(liquid["city"], "Herndon")
        self.assertIn("Jessup", liquid["overview"])
        self.assertIsNone(catalog["MAAP Central Virginia Flight Area"]["latitude"])
        self.assertIn("DRAFT", catalog["MAAP Central Virginia Flight Area"]["overview"])
        self.assertEqual(
            catalog["Virginia Tech Center for Marine Autonomy and Robotics"]["address_line"], ""
        )
        vidarr = catalog["ViDARR Virginia Beach Manufacturing Facility"]
        self.assertIn("19,000", vidarr["overview"])
        self.assertIn("16,410", vidarr["overview"])
        self.assertIn("by appointment", vidarr["overview"])


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class DecisionProfileCorrectionTests(TestCase):
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
                field = Asset._meta.get_field(name)
                setattr(asset, name, field.to_python(value))
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
        call_command("apply_catalog_corrections", corrections=DECISION_PROFILES_PATH, stdout=output)
        return output.getvalue()

    def test_applies_once_with_valid_fields_and_usable_evidence(self):
        self.assertIn("Applied 25", self.apply())
        for change in manifest()["corrections"]:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                self.assertTrue(same_value(current_value(asset, field), value), (asset.name, field))
            asset.full_clean()
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
        park = Asset.objects.get(name="Virginia Tech Drone Park")
        self.assertEqual(compare_site(park, {"activity": "enclosed"})["state"], "match")
        self.assertEqual(compare_site(park, {"span": 8})["state"], "unknown")
        before = Asset.history.count(), Source.history.count()
        self.assertIn("Applied 0", self.apply())
        self.assertEqual(before, (Asset.history.count(), Source.history.count()))

    def test_staff_changes_and_source_decisions_are_preserved(self):
        staff = Asset.objects.get(name="Commonwealth Center for Advanced Manufacturing")
        staff._history_user = get_user_model().objects.create_user("profile-reviewer")
        staff.overview = "Staff-maintained manufacturing profile."
        staff.save()
        conflict = Asset.objects.get(name="Marine Sonic Technology")
        conflict.overview = "A newer independently maintained profile."
        conflict.save()
        Source.objects.filter(
            asset__name="Virginia Tech Counter UAS Research and Testing Center",
            url="https://nationalsecurity.vt.edu/about/centers-facilities.html",
        ).update(is_public=False)
        self.assertIn("Applied 22", self.apply())
        staff.refresh_from_db()
        conflict.refresh_from_db()
        self.assertEqual(staff.overview, "Staff-maintained manufacturing profile.")
        self.assertEqual(conflict.overview, "A newer independently maintained profile.")
        ctrc = Asset.objects.get(name="Virginia Tech Counter UAS Research and Testing Center")
        self.assertEqual(ctrc.test_access_types, [])
        self.assertFalse(
            ctrc.sources.get(
                url="https://nationalsecurity.vt.edu/about/centers-facilities.html"
            ).is_public
        )

    def test_two_known_generated_legacy_variants_update_without_relaxing_guards(self):
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
                "Heven AeroTech Headquarters",
                "Commonwealth Center for Advanced Manufacturing",
            },
        )
        self.assertIn("Applied 25 catalog corrections; preserved 0 conflicts", self.apply())
        self.assertFalse(
            Asset.objects.filter(
                review_comments__body__startswith="Catalog correction conflict:"
            ).exists()
        )
