import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from scripts.audit_peer_catalog import public_url
from scripts.build_peer_fria_catalog import grouped_sites, is_current
from scripts.build_peer_supporting_catalog import institution_records, official_url, program_group


class PeerSupportingEvidenceTests(SimpleTestCase):
    def test_only_relevant_program_families_are_eligible(self):
        for code in ("11.0101", "11.0701", "14.1901", "15.0405", "48.0508", "47.0607", "49.0102"):
            self.assertTrue(program_group(code), code)
        for code in ("14.0000", "51.1202", "39.0602", "12.0401", "49.0106", "52.0201"):
            self.assertFalse(program_group(code), code)

    def test_source_url_does_not_turn_email_or_credentials_into_a_website(self):
        self.assertEqual(official_url("college.edu"), "https://college.edu")
        self.assertEqual(official_url("person@college.edu"), "")
        self.assertEqual(official_url("https://user:secret@college.edu"), "")
        for value in (
            "https://localhost/",
            "http://127.0.0.1/x",
            "https://example.com/",
            "https://college.invalid",
            "file:///tmp/test",
        ):
            self.assertFalse(public_url(value), value)
        self.assertTrue(public_url("https://nces.ed.gov/collegenavigator/?id=123"))

    def test_online_only_and_irrelevant_institutions_are_not_physical_campus_assets(self):
        def rows(path):
            if path.name == "c2024_a.zip":
                return iter(
                    [
                        {"UNITID": "1", "CIPCODE": "14.1901", "CTOTALT": "20", "MAJORNUM": "1"},
                        {"UNITID": "2", "CIPCODE": "14.1901", "CTOTALT": "20", "MAJORNUM": "1"},
                        {"UNITID": "3", "CIPCODE": "51.1202", "CTOTALT": "20", "MAJORNUM": "1"},
                    ]
                )
            if path.name == "ic2024.zip":
                return iter([{"UNITID": "1", "DISTNCED": "1"}, {"UNITID": "2", "DISTNCED": "2"}])
            return iter(
                [
                    {
                        "UNITID": code,
                        "STABBR": "AZ",
                        "ACT": "A",
                        "CYACTIVE": "1",
                        "INSTNM": name,
                        "CITY": "Phoenix",
                        "WEBADDR": f"https://school{code}.edu",
                        "IALIAS": "",
                        "ADDR": "1 College Way",
                        "ZIP": "85001",
                        "LATITUDE": "33.4",
                        "LONGITUD": "-112.1",
                    }
                    for code, name in (
                        ("1", "Online School"),
                        ("2", "Technical School"),
                        ("3", "Medical School"),
                    )
                ]
            )

        held = []
        with patch("scripts.build_peer_supporting_catalog.csv_rows", side_effect=rows):
            records = institution_records([], held)
        self.assertEqual([record["name"] for record in records], ["Technical School"])
        self.assertEqual(records[0]["platform_domains"], [])
        self.assertIn("not been confirmed", records[0]["unmanned_systems_relevance"])
        self.assertIn("distance education", held[0]["reason"])

    def test_fria_future_expired_and_missing_dates_are_excluded(self):
        today = date(2026, 11, 18)
        self.assertTrue(is_current({"startDate": "2026-01-01", "endDate": "2027-01-01"}, today))
        self.assertFalse(is_current({"startDate": "2026-12-01", "endDate": "2027-01-01"}, today))
        self.assertFalse(is_current({"startDate": "2025-01-01", "endDate": "2026-11-18"}, today))
        self.assertFalse(is_current({"startDate": None, "endDate": None}, today))

    def test_nearby_fria_polygons_at_one_school_do_not_inflate_facility_counts(self):
        def feature(name, x):
            return {
                "properties": {
                    "state": "UT",
                    "orgName": "School",
                    "city": "Logan",
                    "address1": "1 School Way",
                    "title": name,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[x, 41], [x + 0.001, 41], [x + 0.001, 41.001], [x, 41.001], [x, 41]]
                    ],
                },
            }

        groups = grouped_sites(
            [
                feature("School flying field", -111.8),
                feature("School flying field 2", -111.799),
                feature("School flying field distant", -111.5),
            ]
        )
        self.assertEqual([len(group) for group in groups], [2, 1])

    def test_shipped_catalogs_have_claim_sources_and_no_editorial_stamps(self):
        root = Path(settings.BASE_DIR) / "data/multistate"
        identities = set()
        for path in root.glob("*_starter.json"):
            document = json.loads(path.read_text())
            for record in document["records"]:
                with self.subTest(file=path.name, name=record["name"]):
                    identity = record["state"], record["name"].strip().casefold()
                    self.assertNotIn(identity, identities)
                    identities.add(identity)
                    self.assertNotIn("status", record)
                    self.assertNotIn("last_verified_at", record)
                    self.assertTrue(record["sources"])
                    for source in record["sources"]:
                        self.assertTrue(source["supports"])
                        self.assertTrue(public_url(source["url"]))
                    self.assertTrue(public_url(record.get("website_url")))


class CompletePeerImportTests(TestCase):
    def test_complete_shipped_inventory_imports_with_history_and_remains_internal(self):
        import io

        from apps.assets.management.commands.seed_demo_data import (
            CAPABILITIES,
            CATEGORIES,
            DOMAINS,
            MISSIONS,
        )
        from apps.assets.management.commands.seed_peer_states import TAXONOMIES, load_records
        from apps.assets.models import Asset
        from apps.sources.models import Source

        vocabulary = {
            "strategic_categories": [
                *CATEGORIES,
                "Manufacturing facilities",
                "Core unmanned-systems asset",
                "Supporting ecosystem asset",
            ],
            "platform_domains": [*DOMAINS, "Advanced Air Mobility"],
            "capabilities": CAPABILITIES,
            "missions": MISSIONS,
        }
        virginia = json.loads(
            (Path(settings.BASE_DIR) / "data/virginia_real_assets.json").read_text()
        )
        for record in virginia["records"]:
            for field in vocabulary:
                vocabulary[field] = [*vocabulary[field], *record.get(field, [])]
        for field, names in vocabulary.items():
            for name in set(names):
                TAXONOMIES[field].objects.get_or_create(name=name)
        records = load_records(
            sorted((Path(settings.BASE_DIR) / "data/multistate").glob("*_starter.json"))
        )
        expected_sources = sum(len(record["sources"]) for record, _date in records)
        call_command("seed_peer_states", apply=True, stdout=io.StringIO())
        self.assertEqual(Asset.objects.count(), len(records))
        self.assertEqual(Asset.history.count(), len(records))
        self.assertEqual(Source.objects.count(), expected_sources)
        self.assertEqual(Source.history.count(), expected_sources)
        self.assertFalse(
            Asset.objects.exclude(visibility="internal", status="source-backed").exists()
        )
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())
        call_command("seed_peer_states", apply=True, stdout=io.StringIO())
        self.assertEqual(Asset.history.count(), len(records))
        self.assertEqual(Source.history.count(), expected_sources)
