import json
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils.html import escape

from apps.assets.management.commands.apply_catalog_corrections import TAXONOMY_FIELDS
from apps.assets.models import Asset
from apps.catalog.models import Capability
from apps.sources.models import Source
from scripts.build_real_asset_catalog import apply_reviewed_corrections

MANIFEST = settings.BASE_DIR / "data/capability_profiles_2026_09_07.json"
CATALOG = settings.BASE_DIR / "data/virginia_real_assets.json"


class CapabilityManifestTests(SimpleTestCase):
    def test_all_profiles_have_evidence_and_preserve_identity_and_location(self):
        records = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        changes = json.loads(MANIFEST.read_text())["corrections"]
        self.assertEqual(len(changes), 18)
        self.assertEqual(len({c["name"] for c in changes}), 18)
        allowed = {
            "overview",
            "short_description",
            "unmanned_systems_relevance",
            "website_url",
            "contact_text",
            "contact_url",
            "contact_email",
            "contact_phone",
            "capabilities",
            "current_activity",
            "activity_status",
            "activity_source_url",
            "activity_last_verified_at",
            "partnership_opportunities",
            "test_aircraft",
            "test_dimensions",
            "test_access",
            "test_source_url",
            "test_last_verified_at",
            "test_runway_length_ft",
        }
        for change in changes:
            with self.subTest(name=change["name"]):
                after = change["after"]
                self.assertEqual(set(change["before"]), set(after))
                self.assertTrue(set(after) <= allowed)
                self.assertGreater(len(after["overview"]), 150)
                self.assertNotIn("Public sources support its classification", after["overview"])
                urls = {s["url"] for s in change["add_sources"]}
                self.assertIn(after["activity_source_url"], urls)
                self.assertIn(
                    after["contact_url"],
                    {source["url"] for source in records[change["name"]]["sources"]},
                )
                self.assertEqual(after["activity_last_verified_at"], "2026-09-07")
                if "test_source_url" in after:
                    self.assertIn(after["test_source_url"], urls)
                    self.assertIsNone(after["test_runway_length_ft"])
                for field, value in after.items():
                    self.assertEqual(records[change["name"]][field], value)

    def test_scope_and_maturity_caveats_are_retained(self):
        records = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        self.assertEqual(records["Agricision"]["activity_status"], "developing")
        self.assertEqual(
            records["HII Unmanned Systems Center of Excellence"]["activity_status"], ""
        )
        self.assertIn("2021", records["HII Unmanned Systems Center of Excellence"]["overview"])
        self.assertIn("Maryland", records["Magothy River Technologies"]["overview"])
        self.assertIn("West Virginia", records["Aurora Flight Sciences"]["overview"])
        self.assertIn("under development", records["Psionic"]["current_activity"])
        self.assertIn("historical", records["P1 Technologies Keltech Division"]["current_activity"])
        for name in ("DroneUp", "ANRA Technologies"):
            self.assertNotIn(
                "Manufacturing, materials, and prototyping", records[name]["capabilities"]
            )

    def test_regeneration_is_repeatable(self):
        records = json.loads(CATALOG.read_text())["records"]
        original = json.dumps(records, sort_keys=True)
        apply_reviewed_corrections(records)
        self.assertEqual(original, json.dumps(records, sort_keys=True))
        apply_reviewed_corrections(records)
        self.assertEqual(original, json.dumps(records, sort_keys=True))


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class CapabilityDeploymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changes = json.loads(MANIFEST.read_text())["corrections"]
        cls.catalog = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        for change in cls.changes:
            before = change["before"]
            record = cls.catalog[change["name"]]
            asset = Asset(
                name=change["name"],
                record_type=record["record_type"],
                short_description=record["short_description"],
                unmanned_systems_relevance=record["unmanned_systems_relevance"],
                status="source-backed",
                visibility="public",
                internal_notes=f"Catalog provenance: {change['provenance']}.",
            )
            for field, value in before.items():
                if field not in TAXONOMY_FIELDS:
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
            asset.save()
            for name in set(before.get("capabilities", [])) | set(
                change["after"].get("capabilities", [])
            ):
                Capability.objects.get_or_create(name=name)
            asset.capabilities.set(
                Capability.objects.filter(name__in=before.get("capabilities", []))
            )

    def apply(self):
        out = StringIO()
        call_command("apply_catalog_corrections", corrections=MANIFEST, stdout=out)
        return out.getvalue()

    def test_applies_once_without_verifying_or_publishing_records(self):
        self.assertIn("Applied 18", self.apply())
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            self.assertEqual(asset.overview, change["after"]["overview"])
            self.assertEqual(
                asset.partnership_opportunities, change["after"]["partnership_opportunities"]
            )
            self.assertEqual(asset.activity_last_verified_at, date(2026, 9, 7))
            self.assertEqual(asset.status, "source-backed")
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)
            asset.full_clean()
        count = Asset.history.count()
        sources = Source.objects.count()
        self.assertIn("Applied 0", self.apply())
        self.assertEqual(Asset.history.count(), count)
        self.assertEqual(Source.objects.count(), sources)
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())

    def test_reviewed_legacy_generated_profiles_can_update(self):
        for change in self.changes:
            if not change.get("accepted_baselines"):
                continue
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["accepted_baselines"][0].items():
                if field in TAXONOMY_FIELDS:
                    asset.capabilities.set(Capability.objects.filter(name__in=value))
                else:
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
            asset.save()
        self.assertIn("Applied 18", self.apply())

    def test_latest_seeded_values_are_not_treated_as_conflicts(self):
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                if field in TAXONOMY_FIELDS:
                    asset.capabilities.set(Capability.objects.filter(name__in=value))
                else:
                    setattr(asset, field, Asset._meta.get_field(field).to_python(value))
            asset.save()
        self.assertIn("preserved 0 conflicts", self.apply())

    def test_staff_edits_and_private_records_are_preserved(self):
        asset = Asset.objects.get(name="ANRA Technologies")
        original = asset.overview
        asset._history_user = get_user_model().objects.create_user("capability-editor")
        asset.save()
        private = Asset.objects.get(name="DroneUp")
        private.visibility = "internal"
        private.save()
        self.apply()
        asset.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(asset.overview, original)
        self.assertEqual(private.visibility, "internal")
        self.assertIn(
            "Manufacturing, materials, and prototyping",
            private.capabilities.values_list(
                "name",
                flat=True,
            ),
        )

    def test_conflicting_staff_value_preserves_entire_profile(self):
        asset = Asset.objects.get(name="Agricision")
        original = asset.overview
        asset.partnership_opportunities = "Staff-confirmed project route"
        asset.activity_source_url = "https://example.org/staff"
        asset.activity_last_verified_at = date(2026, 9, 5)
        asset.save()
        self.apply()
        asset.refresh_from_db()
        self.assertEqual(asset.overview, original)
        self.assertEqual(asset.partnership_opportunities, "Staff-confirmed project route")
        self.assertTrue(
            asset.review_comments.filter(
                body__startswith="Catalog correction conflict:",
            ).exists()
        )

    def test_hidden_evidence_prevents_claims_from_being_republished(self):
        asset = Asset.objects.get(name="Mid-Atlantic Aviation Partnership")
        Source.objects.create(
            asset=asset,
            title="Staff-hidden source",
            is_public=False,
            url="https://maap.ictas.vt.edu/capabilities/facilities.html",
        )
        self.apply()
        asset.refresh_from_db()
        self.assertEqual(asset.test_aircraft, "")
        self.assertFalse(asset.sources.get(title="Staff-hidden source").is_public)

    def test_detail_pages_show_practical_profiles_and_evidence(self):
        self.apply()
        for name in ("Agricision", "Aurora Flight Sciences", "Mid-Atlantic Aviation Partnership"):
            asset = Asset.objects.get(name=name)
            response = self.client.get(asset.get_absolute_url())
            self.assertContains(response, escape(asset.overview))
            self.assertContains(response, escape(asset.partnership_opportunities))
            self.assertContains(response, asset.activity_source_url)
            self.assertContains(response, "Sep 7, 2026")
