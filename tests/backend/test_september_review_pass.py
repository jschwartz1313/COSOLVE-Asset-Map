import copy
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.assets.management.commands.apply_catalog_corrections import ALLOWED_FIELDS
from apps.assets.models import Asset
from scripts.build_real_asset_catalog import (
    apply_interview_followup,
    apply_reviewed_corrections,
    validate,
)


class SeptemberReviewPassTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data = settings.BASE_DIR / "data"
        cls.records = json.loads((data / "virginia_real_assets.json").read_text())["records"]
        cls.by_name = {r["name"]: r for r in cls.records}
        cls.audit = json.loads((data / "asset_review_pass_2026_09_16.json").read_text())
        cls.reviews = json.loads((data / "asset_editorial_reviews_2026_09_16.json").read_text())
        cls.corrections = json.loads((data / "asset_corrections_2026_09_16.json").read_text())[
            "corrections"
        ]

    def test_every_requested_record_has_a_disposition(self):
        decisions = self.audit["pending_reviews"]
        reviewed = set(self.reviews["reviewed_assets"])
        pending = set(self.reviews["follow_up_assets"])
        self.assertEqual(len(decisions), 71)
        self.assertEqual(len(reviewed), 54)
        self.assertEqual(len(pending), 17)
        self.assertFalse(reviewed & pending)
        self.assertEqual({r["name"] for r in decisions}, reviewed | pending)
        self.assertEqual(len(self.audit["location_reviews"]), 42)
        self.assertEqual(len(self.audit["airport_website_reviews"]), 8)
        self.assertEqual(set(self.reviews["review_findings"]), reviewed)

    def test_selected_evidence_exists_and_is_not_a_geocoder(self):
        for name, urls in self.reviews["reviewed_assets"].items():
            with self.subTest(name=name):
                self.assertTrue(urls)
                self.assertTrue(set(urls) <= {s["url"] for s in self.by_name[name]["sources"]})
                self.assertTrue(all("geocod" not in url for url in urls))
                self.assertTrue(self.reviews["review_findings"][name])

    def test_location_changes_do_not_claim_surveyed_or_operational_precision(self):
        locations = self.audit["location_reviews"]
        upgraded = [r for r in locations if r["outcome"] == "public-contact-or-site-point"]
        regional = [r for r in locations if r["precision"] == "regional"]
        self.assertEqual(len(upgraded), 6)
        self.assertEqual(len(regional), 8)
        for item in upgraded:
            record = self.by_name[item["name"]]
            self.assertEqual(record["location_precision"], "site")
            self.assertEqual(record["location_method"], "geocoded")
            self.assertTrue(record["location_source_url"])
            self.assertTrue(record["location_notes"])
        for item in regional:
            record = self.by_name[item["name"]]
            self.assertIsNone(record["latitude"])
            self.assertIsNone(record["longitude"])
            self.assertEqual(record["location_method"], "unmapped")
        self.assertEqual(
            self.by_name["Heven AeroTech Winchester Innovation and Manufacturing Campus"]["city"],
            "Winchester",
        )
        self.assertIn(
            "not", self.by_name["TurbineOne Headquarters and T1 Edgeworks"]["current_activity"]
        )
        self.assertIn(
            "City of Manassas First Responder UAS Capability", self.reviews["follow_up_assets"]
        )

    def test_airport_fallbacks_and_faa_coordinates_are_not_replaced_by_sponsor_addresses(self):
        for item in self.audit["airport_website_reviews"]:
            record = self.by_name[item["name"]]
            self.assertEqual(record["website_url"], "https://doav.virginia.gov/airport-directory/")
            self.assertTrue(any("FAA airport record" in s["title"] for s in record["sources"]))
            for correction in self.corrections:
                if correction["name"] == record["name"]:
                    self.assertFalse(
                        {"latitude", "longitude", "address_line"} & correction["after"].keys()
                    )
            if item["identifier"] == "2G6":
                self.assertIn("Seaplane", record["display_name"])
            else:
                self.assertTrue(record["contact_phone"])
                self.assertTrue(record["contact_email"])

    def test_regeneration_keeps_reviewed_changes_and_does_not_duplicate_sources(self):
        records = copy.deepcopy(self.records)
        by_name = {r["name"]: r for r in records}
        for correction in reversed(self.corrections):
            self.assertEqual(set(correction["before"]), set(correction["after"]))
            self.assertTrue(set(correction["after"]) <= ALLOWED_FIELDS)
            by_name[correction["name"]].update(correction["before"])
        apply_reviewed_corrections(records, self.corrections)
        apply_reviewed_corrections(records, self.corrections)
        for name, record in by_name.items():
            self.assertEqual(record, self.by_name[name])
            urls = [s["url"] for s in record["sources"]]
            self.assertEqual(len(urls), len(set(urls)))

    def test_complete_update_sequence_preserves_latest_data_and_contact_sources(self):
        records = copy.deepcopy(self.records)
        apply_interview_followup(records)
        apply_reviewed_corrections(records)
        self.assertEqual(records, self.records)
        for record in records:
            urls = {s["url"] for s in record["sources"]}
            for field in ("website_url", "contact_url"):
                if record.get(field):
                    self.assertIn(record[field], urls, record["name"])

    def test_catalog_validation_accepts_documented_http_operator_site(self):
        catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        validate(catalog["records"], [
            (r["from"], r["type"], r["to"]) for r in catalog["relationships"]
        ])

    def test_contact_links_reject_non_web_schemes_and_missing_hosts(self):
        for url in ("javascript:alert(1)", "https:///missing-host"):
            record = copy.deepcopy(self.records[0])
            record["contact_url"] = url
            record["sources"].append({"title": "Invalid contact", "url": url})
            with self.assertRaisesRegex(ValueError, "Invalid public contact URL"):
                validate([record], [])

    def test_atomic_corrections_run_before_generic_profile_enrichment(self):
        build = (settings.BASE_DIR / "build.sh").read_text()
        self.assertLess(
            build.index("--corrections data/asset_corrections_2026_09_16.json"),
            build.index("python manage.py enrich_asset_profiles"),
        )


class SeptemberReviewDeploymentTests(TestCase):
    def test_fresh_install_replays_older_location_updates_without_false_conflicts(self):
        data = settings.BASE_DIR / "data"
        names = {
            "AUVSI Ridge and Valley Chapter",
            "Virginia Automated Corridors",
            "H2P Solution",
            "Magothy River Technologies",
            "MITRE National Range",
        }
        records = [
            r for r in json.loads((data / "virginia_real_assets.json").read_text())["records"]
            if r["name"] in names
        ]
        with TemporaryDirectory() as directory:
            fixture = Path(directory) / "catalog.json"
            fixture.write_text(json.dumps({"records": records, "relationships": []}))
            call_command("seed_real_data", catalog=fixture, stdout=StringIO())
            for _ in range(2):
                for filename in (
                    "profile_improvements_2026_09_06.json",
                    "asset_corrections_2026_09_16.json",
                ):
                    call_command(
                        "apply_catalog_corrections", corrections=data / filename,
                        stdout=StringIO(),
                    )
                for record in records:
                    asset = Asset.objects.get(name=record["name"])
                    self.assertEqual(
                        asset.location_last_verified_at.isoformat(), "2026-09-16"
                    )
                    self.assertFalse(asset.review_comments.filter(
                        body__startswith="Catalog correction conflict:"
                    ).exists())

    def test_old_catalog_migrates_and_fresh_catalog_validates(self):
        data = settings.BASE_DIR / "data"
        path = data / "asset_corrections_2026_09_16.json"
        corrections = json.loads(path.read_text())["corrections"]
        names = {c["name"] for c in corrections}
        catalog = json.loads((data / "virginia_real_assets.json").read_text())
        final_records = [r for r in catalog["records"] if r["name"] in names]
        old_records = copy.deepcopy(final_records)
        by_name = {r["name"]: r for r in old_records}
        for correction in reversed(corrections):
            by_name[correction["name"]].update(correction["before"])
        with TemporaryDirectory() as directory:
            fixture = Path(directory) / "catalog.json"
            fixture.write_text(json.dumps({"records": old_records, "relationships": []}))
            call_command("seed_real_data", catalog=fixture, stdout=StringIO())
            call_command("apply_catalog_corrections", corrections=path, stdout=StringIO())
            fixture.write_text(json.dumps({"records": final_records, "relationships": []}))
            call_command("enrich_asset_profiles", catalog=fixture, stdout=StringIO())
            output = StringIO()
            call_command("apply_catalog_corrections", corrections=path, stdout=output)
            self.assertIn("Applied 0 catalog corrections; preserved 0 conflicts", output.getvalue())
            for record in final_records:
                asset = Asset.objects.get(name=record["name"])
                asset.full_clean()
                self.assertEqual(asset.location_precision, record["location_precision"])
                self.assertEqual(asset.location_notes, record.get("location_notes") or "")
            fixture.write_text(json.dumps({"records": final_records, "relationships": []}))
            # The seed command also exercises new installations with the final fields.
            call_command("seed_real_data", catalog=fixture, stdout=StringIO())
            self.assertEqual(Asset.objects.count(), len(final_records))
