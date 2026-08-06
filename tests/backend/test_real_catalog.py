import json
from datetime import date
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset, Relationship
from apps.sources.models import Source


class RealCatalogFileTests(TestCase):
    def load_catalog(self):
        path = settings.BASE_DIR / "data" / "virginia_real_assets.json"
        return json.loads(path.read_text())

    def test_region_boundary_layer_covers_all_virginia_localities(self):
        path = settings.BASE_DIR / "static" / "data" / "virginia-regions.geojson"
        regions = json.loads(path.read_text())
        features = regions["features"]

        self.assertEqual(len(features), 12)
        self.assertEqual(
            sum(feature["properties"]["locality_count"] for feature in features),
            133,
        )
        self.assertEqual(
            len({feature["properties"]["region_slug"] for feature in features}),
            12,
        )
        self.assertTrue(
            all(
                feature["properties"]["region_color"].startswith("#")
                and feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
                for feature in features
            )
        )

    def test_faa_heliport_reference_layer_is_scoped_and_labeled(self):
        path = settings.BASE_DIR / "static" / "data" / "virginia-heliports.geojson"
        layer = json.loads(path.read_text())

        self.assertEqual(layer["type"], "FeatureCollection")
        self.assertEqual(layer["metadata"]["feature_count"], len(layer["features"]))
        self.assertGreaterEqual(len(layer["features"]), 120)
        self.assertIn("private-use", layer["metadata"]["scope"])
        self.assertIn("does not imply public access", layer["metadata"]["disclaimer"])
        self.assertTrue(
            all(
                feature["geometry"]["type"] == "Point"
                and feature["properties"]["use"] == "Private use"
                and feature["properties"]["status"] == "Operational"
                for feature in layer["features"]
            )
        )

    def test_catalog_has_at_least_400_real_source_backed_records(self):
        catalog = self.load_catalog()
        records = catalog["records"]
        self.assertGreaterEqual(len(records), 400)
        self.assertEqual(catalog["record_count"], len(records))
        self.assertGreaterEqual(len(catalog["relationships"]), 90)
        self.assertFalse(any(record["name"].startswith("Demo ") for record in records))
        self.assertTrue(
            all(record["sources"] and record["unmanned_systems_relevance"] for record in records)
        )
        self.assertTrue(
            all(
                record["overview"]
                and record["contact_text"]
                and record["contact_url"]
                and any(source["url"] == record["contact_url"] for source in record["sources"])
                for record in records
            )
        )
        airport_regions = {
            record["name"]: record["region"]
            for record in records
            if record["provenance"] == "faa-public-airport"
        }
        self.assertEqual(airport_regions["Accomack County"], "Eastern Shore")
        self.assertEqual(airport_regions["Lynchburg Rgnl/Preston Glenn Fld"], "Lynchburg Region")
        self.assertEqual(airport_regions["Roanoke/Blacksburg Rgnl (Woodrum Fld)"], "Roanoke Valley")
        universities = [record for record in records if record["record_type"] == "university"]
        self.assertEqual(len(universities), 82)
        self.assertTrue(
            {
                "Blue Ridge Community College",
                "University of Mary Washington",
                "Washington and Lee University",
            }.issubset({record["name"] for record in universities})
        )
        self.assertTrue(
            all(
                record["location_precision"] == "site"
                and record.get("address_line")
                and record["latitude"] is not None
                and record["longitude"] is not None
                for record in universities
            )
        )
        self.assertTrue(
            all(
                any("nces.ed.gov/ipeds" in item["url"] for item in record["sources"])
                for record in universities
            )
        )
        self.assertTrue(all(record["contact_phone"] for record in universities))
        general_institutions = [
            record
            for record in universities
            if record["provenance"] == "nces-ipeds-higher-education"
        ]
        self.assertEqual(len(general_institutions), 63)
        self.assertTrue(
            all(
                "does not by itself indicate a documented unmanned-systems program"
                in record["unmanned_systems_relevance"]
                for record in general_institutions
            )
        )
        hampton_roads = [record for record in records if record["region"] == "Hampton Roads"]
        self.assertGreaterEqual(len(hampton_roads), 69)
        self.assertFalse(
            any(
                record["location_precision"] in {"approximate", "locality"}
                for record in hampton_roads
            )
        )
        self.assertTrue(
            all(
                record.get("address_line")
                for record in hampton_roads
                if record["location_precision"] == "site"
            )
        )
        regional = [
            record for record in hampton_roads if record["location_precision"] == "regional"
        ]
        self.assertEqual([record["name"] for record in regional], ["AUVSI Hampton Roads Chapter"])
        self.assertIsNone(regional[0]["latitude"])
        self.assertIsNone(regional[0]["longitude"])
        self.assertTrue(
            all(
                source.get("url", "").startswith("https://")
                for record in records
                for source in record["sources"]
            )
        )
        airports = [
            record for record in records if record["provenance"] == "faa-public-airport"
        ]
        self.assertEqual(len(airports), 64)
        self.assertGreaterEqual(sum(bool(record["contact_phone"]) for record in airports), 63)
        self.assertGreaterEqual(sum(bool(record["contact_email"]) for record in airports), 62)
        self.assertTrue(
            all(
                any("airport_sponsors" in source["url"] for source in record["sources"])
                for record in airports
            )
        )

    def test_catalog_seed_is_idempotent(self):
        catalog = self.load_catalog()
        call_command("seed_real_data", verbosity=0)
        first_record = catalog["records"][0]
        first_source = first_record["sources"][0]
        source = Source.objects.get(
            asset__name=first_record["name"],
            asset__city=first_record["city"],
            title=first_source["title"],
        )
        source.url = "https://example.test/obsolete"
        source.verification_status = "verified"
        source.last_verified_at = date(2026, 1, 1)
        source.http_status = 404
        source.check_error = "Old result"
        source.save()
        call_command("seed_real_data", verbosity=0)
        self.assertEqual(Asset.public.count(), catalog["record_count"])
        self.assertEqual(Relationship.objects.count(), len(catalog["relationships"]))
        self.assertGreaterEqual(Source.objects.count(), catalog["record_count"])
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())
        self.assertFalse(Source.objects.filter(last_verified_at__isnull=False).exists())
        source.refresh_from_db()
        self.assertEqual(source.url, first_source["url"])
        self.assertIsNone(source.http_status)
        self.assertEqual(source.check_error, "")
        self.assertFalse(Asset.objects.filter(name__startswith="Demo ").exists())
        self.assertGreaterEqual(
            Asset.public.filter(record_type=Asset.RecordType.UNIVERSITY).count(),
            82,
        )
        self.assertTrue(
            Relationship.objects.filter(
                from_asset__record_type=Asset.RecordType.UNIVERSITY,
                relationship_type=Relationship.RelationshipType.SUPPORTS,
            ).exists()
        )
        nasa = Asset.objects.get(name="NASA Langley Research Center")
        self.assertEqual(nasa.address_line, "2 Langley Boulevard")
        self.assertEqual(nasa.location_precision, Asset.LocationPrecision.SITE)
        self.assertEqual(str(nasa.latitude), "37.085639")
        self.assertTrue(nasa.overview)
        self.assertEqual(nasa.contact_url, "https://www.nasa.gov/contact/")
        northwest_annex = Asset.objects.get(name="Naval Support Activity Northwest Annex")
        self.assertEqual(northwest_annex.city, "Chesapeake")
        self.assertEqual(northwest_annex.postal_code, "23322")
        regional = Asset.objects.get(name="AUVSI Hampton Roads Chapter")
        self.assertIsNone(regional.latitude)
        self.assertEqual(regional.location_precision, Asset.LocationPrecision.REGIONAL)

    def test_august_2026_expansion_is_source_backed_and_located(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}
        expanded_assets = {
            "Bedford Fire Department UAS Program",
            "CACI International",
            "Charles City County Sheriff's Office Drone Operations Team",
            "DZYNE Technologies",
            "Eagle Aviation Technologies",
            "ENSCO",
            "Fairfax County Police Drone as First Responder Program",
            "Inertial Labs",
            "Leidos",
            "MAG Aerospace",
            "Marine Corps Counter-Drone Team",
            "NASA Langley ROAM UAS Operations Center",
            "NASA Langley UAS Test Range",
            "Navy TALSA East Small UAS Training Facility",
            "Newport News AirCommerce Park",
            "NSWC Dahlgren UAV Test Runway",
            "NSWCDD Dam Neck Activity",
            "Parsons",
            "Radford University First Responder UAS Capability",
            "Scout Space",
            "Universal Solutions International",
            "Wallops Research Park",
        }

        self.assertTrue(expanded_assets.issubset(records_by_name))
        for name in expanded_assets:
            record = records_by_name[name]
            self.assertIn(record["location_precision"], {"site", "exact"})
            self.assertTrue(record["address_line"])
            self.assertTrue(record["sources"])
            self.assertTrue(
                all(source["url"].startswith("https://") for source in record["sources"])
            )

        relationships = {
            (relationship["from"], relationship["type"], relationship["to"])
            for relationship in catalog["relationships"]
        }
        self.assertIn(
            (
                "NASA Langley Research Center",
                "operates",
                "NASA Langley ROAM UAS Operations Center",
            ),
            relationships,
        )
        self.assertIn(
            (
                "Joint Expeditionary Base Little Creek-Fort Story",
                "hosts",
                "Navy TALSA East Small UAS Training Facility",
            ),
            relationships,
        )

    def test_stakeholder_requested_assets_and_dynamic_fields_are_source_backed(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}
        requested_assets = {
            "GO Virginia",
            "Hampton Roads Alliance",
            "MITRE National Range",
            "Shenandoah Valley Aviation Technology Park",
            "Stafford Regional Airport AAM Integration Project Site",
            "Virginia Economic Development Partnership",
        }

        self.assertTrue(requested_assets.issubset(records_by_name))
        for name in requested_assets:
            record = records_by_name[name]
            self.assertTrue(record["activity_status"])
            self.assertTrue(record["current_activity"])
            self.assertTrue(record["partnership_opportunities"])
            self.assertTrue(record["activity_last_verified_at"])
            self.assertIn(
                record["activity_source_url"],
                {source["url"] for source in record["sources"]},
            )

        shd = records_by_name["Shenandoah Valley Aviation Technology Park"]
        self.assertEqual(shd["available_acreage"], 58)
        self.assertEqual(shd["development_status"], "in-development")
        self.assertIn(
            shd["development_source_url"],
            {source["url"] for source in shd["sources"]},
        )
        stafford = records_by_name["Stafford Regional Airport AAM Integration Project Site"]
        self.assertIn("Advanced Air Mobility", stafford["platform_domains"])
        self.assertEqual(stafford["location_precision"], "site")
        virginia_fix = records_by_name["Virginia Flight Information Exchange"]
        self.assertEqual(virginia_fix["location_precision"], "regional")
        self.assertIsNone(virginia_fix["latitude"])

    def test_only_if_empty_preserves_existing_database_edits(self):
        call_command("seed_real_data", verbosity=0)
        asset = Asset.objects.order_by("pk").first()
        asset.short_description = "Reviewed and corrected by a staff member."
        asset.save(update_fields=["short_description"])
        output = StringIO()

        call_command(
            "seed_real_data",
            prune=True,
            only_if_empty=True,
            stdout=output,
            verbosity=0,
        )

        asset.refresh_from_db()
        self.assertEqual(
            asset.short_description,
            "Reviewed and corrected by a staff member.",
        )
        self.assertIn("Skipped catalog initialization", output.getvalue())

    def test_only_if_empty_loads_a_new_database(self):
        catalog = self.load_catalog()

        call_command("seed_real_data", only_if_empty=True, verbosity=0)

        self.assertEqual(Asset.public.count(), catalog["record_count"])

    def test_profile_enrichment_fills_blanks_without_replacing_staff_contact(self):
        asset = Asset.objects.create(
            name="NASA Langley Research Center",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Staff-edited description.",
            unmanned_systems_relevance="Staff-reviewed relevance.",
            contact_text="Staff-maintained public affairs contact",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )

        call_command("enrich_asset_profiles", verbosity=0)

        asset.refresh_from_db()
        self.assertEqual(asset.short_description, "Staff-edited description.")
        self.assertEqual(asset.contact_text, "Staff-maintained public affairs contact")
        self.assertTrue(asset.overview)
        self.assertEqual(asset.contact_url, "https://www.nasa.gov/contact/")
        self.assertTrue(asset.sources.filter(url=asset.contact_url, is_public=True).exists())

    def test_add_missing_preserves_reviewed_records_and_restores_catalog_gaps(self):
        catalog = self.load_catalog()
        call_command("seed_real_data", verbosity=0)
        reviewed = Asset.objects.get(name="NASA Langley Research Center")
        reviewed.short_description = "Reviewed and corrected by a staff member."
        reviewed.save(update_fields=["short_description"])
        Asset.objects.get(name="Harrowgate Drone Park").delete()
        manual = Asset.objects.create(
            name="Staff-created research lead",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A manually entered lead awaiting staff review.",
            unmanned_systems_relevance="Potential ecosystem record pending source review.",
            status=Asset.Status.NEEDS_REVIEW,
            visibility=Asset.Visibility.INTERNAL,
        )

        call_command("seed_real_data", add_missing=True, verbosity=0)

        reviewed.refresh_from_db()
        self.assertEqual(
            reviewed.short_description,
            "Reviewed and corrected by a staff member.",
        )
        self.assertTrue(Asset.objects.filter(name="Harrowgate Drone Park").exists())
        self.assertTrue(Asset.objects.filter(pk=manual.pk).exists())
        self.assertEqual(Asset.public.count(), catalog["record_count"])
