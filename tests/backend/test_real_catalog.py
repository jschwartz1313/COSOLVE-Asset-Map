import json
from datetime import date
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import SPECIALIZED_HIGHER_ED_EXCLUSIONS, Asset, Relationship
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

    def test_catalog_has_at_least_500_relevant_source_backed_records(self):
        catalog = self.load_catalog()
        records = catalog["records"]
        self.assertGreaterEqual(len(records), 500)
        self.assertEqual(catalog["record_count"], len(records))
        self.assertGreaterEqual(len(catalog["relationships"]), 90)
        self.assertFalse(any(record["name"].startswith("Demo ") for record in records))
        self.assertTrue(
            all(record["sources"] and record["unmanned_systems_relevance"] for record in records)
        )
        self.assertTrue(all(len(record["sources"]) >= 2 for record in records))
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
        self.assertEqual(len(universities), 69)
        self.assertTrue(
            {
                "Blue Ridge Community College",
                "Old Dominion University",
                "University of Virginia",
                "University of Mary Washington",
                "Virginia Tech",
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
        self.assertEqual(len(general_institutions), 50)
        self.assertTrue(
            all(
                "does not by itself indicate a documented unmanned-systems program"
                in record["unmanned_systems_relevance"]
                for record in general_institutions
            )
        )
        self.assertFalse(
            SPECIALIZED_HIGHER_ED_EXCLUSIONS.intersection(record["name"] for record in universities)
        )
        hampton_roads = [record for record in records if record["region"] == "Hampton Roads"]
        self.assertGreaterEqual(len(hampton_roads), 120)

        manufacturing = [
            record
            for record in records
            if "Manufacturing facilities" in record["strategic_categories"]
        ]
        self.assertEqual(len(manufacturing), 26)
        self.assertTrue(
            all(
                "Manufacturing, materials, and prototyping" in record["capabilities"]
                and record["location_precision"] not in {"regional", "hidden"}
                for record in manufacturing
            )
        )
        self.assertEqual(
            {
                record["name"]
                for record in manufacturing
                if record.get("activity_status") == "historical"
            },
            {"RapidFlight UAS Manufacturing Headquarters"},
        )
        records_by_name = {record["name"]: record for record in records}
        self.assertEqual(
            records_by_name["Fulcrum Concepts Newport News Machine Shop"]["address_line"],
            "737 Industrial Park Drive",
        )
        self.assertEqual(
            records_by_name["Micron Manassas Semiconductor Fabrication Plant"]["address_line"],
            "9600 Godwin Drive",
        )
        self.assertEqual(
            records_by_name["Wrap Technologies Norton Manufacturing Headquarters"][
                "address_line"
            ],
            "182 Progress Way NE",
        )
        self.assertEqual(
            records_by_name["Defense Maritime Solutions Chesapeake Manufacturing Facility"][
                "address_line"
            ],
            "3617 Koppens Way",
        )
        self.assertEqual(
            records_by_name["Radian Forge Portsmouth Manufacturing Facility"]["address_line"],
            "176 Lincoln Street",
        )
        self.assertEqual(
            records_by_name["L3Harris Orange County Propulsion Manufacturing Site"][
                "address_line"
            ],
            "7499 Pine Stake Road",
        )
        self.assertIn(
            "Manufacturing facilities",
            records_by_name["Inertial Labs"]["strategic_categories"],
        )
        locality_only = {
            record["name"]
            for record in hampton_roads
            if record["location_precision"] in {"approximate", "locality"}
        }
        # The Southampton award identifies a jurisdiction, not its operating department.
        self.assertEqual(locality_only, {"Southampton County First Responder UAS Capability"})
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
        self.assertEqual(
            [record["name"] for record in regional],
            [
                "AUVSI Hampton Roads Chapter",
                "Commonwealth STEM Industry Internship Program (CSIIP)",
                "STEM Takes Flight at Virginia's Community Colleges",
                "Virginia Capes Range Complex",
            ],
        )
        self.assertTrue(all(record["latitude"] is None for record in regional))
        self.assertTrue(all(record["longitude"] is None for record in regional))
        self.assertTrue(
            all(
                source.get("url", "").startswith("https://")
                for record in records
                for source in record["sources"]
            )
        )
        self.assertTrue(
            all(
                record["website_url"]
                and any(source["url"] == record["website_url"] for source in record["sources"])
                for record in records
            )
        )
        records_by_name = {record["name"]: record for record in records}
        orange = records_by_name["Orange County Sheriff's Office Drone Team"]
        self.assertEqual(orange["website_url"], "https://www.orangecountyva.gov/sheriff")
        self.assertFalse(any("louisacounty.gov" in source["url"] for source in orange["sources"]))
        rapidflight = records_by_name["RapidFlight UAS Manufacturing Headquarters"]
        self.assertEqual(rapidflight["activity_status"], "historical")
        self.assertIn("AEVEX", rapidflight["current_activity"])
        airports = [record for record in records if record["provenance"] == "faa-public-airport"]
        self.assertEqual(len(airports), 64)
        self.assertGreaterEqual(sum(bool(record["contact_phone"]) for record in airports), 63)
        self.assertGreaterEqual(sum(bool(record["contact_email"]) for record in airports), 62)
        self.assertTrue(
            all(
                any("airport_sponsors" in source["url"] for source in record["sources"])
                for record in airports
            )
        )
        for record in airports:
            identifier = record["short_description"].split("FAA identifier ", 1)[1][:-2]
            matching_sources = [
                source
                for source in record["sources"]
                if source["title"].startswith("FAA airport record for ")
            ]
            self.assertEqual(len(matching_sources), 1, record["name"])
            self.assertIn(f"IDENT%3D%27{identifier}%27", matching_sources[0]["url"])

    def test_direct_website_audit_replaces_broad_catalog_pages(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}
        broad_vedp_url = "https://www.vedp.org/industry/unmanned-systems"
        military_factbook_url = (
            "https://www.vada.virginia.gov/media/governorvirginiagov/"
            "secretary-of-veterans-and-defense-affairs/pdf/VA-FactBook_WEB_2020-10-19-CSG.pdf"
        )

        self.assertEqual(
            [
                record["name"]
                for record in catalog["records"]
                if record["website_url"] == broad_vedp_url
            ],
            ["Virginia Economic Development Partnership"],
        )
        self.assertFalse(
            any(record["website_url"] == military_factbook_url for record in catalog["records"])
        )
        self.assertTrue({"Fort Walker", "Fort Lee", "Fort Pickett"}.issubset(records_by_name))
        self.assertFalse(
            {"Fort A.P. Hill", "Fort Gregg-Adams", "Fort Barfoot"}.intersection(
                records_by_name
            )
        )
        for name in {
            "Center for Unmanned Aircraft Systems at Virginia Tech",
            "JMU Drone Challenge",
            "NASA Langley Autonomy Incubator",
            "Virginia Tech Autonomous Systems and Control Laboratory",
        }:
            self.assertEqual(records_by_name[name]["activity_status"], "historical")
            self.assertEqual(records_by_name[name]["activity_last_verified_at"], "2026-08-21")

        self.assertEqual(
            records_by_name["Accomack County Emergency Management Drone Program"]["website_url"],
            (
                "https://www.esva911.org/Communications%20Manual%20-%20Public%20Release%20"
                "Version-%20UPDATED%2011-26-24.pdf"
            ),
        )
        self.assertEqual(
            records_by_name["Dominion Energy UAS Program"]["activity_status"],
            "active",
        )
        self.assertEqual(
            records_by_name["Longbow Unmanned Systems Research and Test Center"]["website_url"],
            "https://www.sbir.gov/portfolio/1664155",
        )
        self.assertEqual(
            records_by_name["Hampden-Sydney College"]["contact_url"],
            "https://www.hsc.edu/admission-and-financial-aid/",
        )
        self.assertEqual(
            records_by_name["National Institute of Aerospace"]["contact_url"],
            "https://www.nianet.org/",
        )
        self.assertIn(
            "https://www.vmi.edu/about/our-location/",
            {source["url"] for source in records_by_name["Virginia Military Institute"]["sources"]},
        )

    def test_catalog_review_manifests_use_attached_official_sources(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}
        september = json.loads(
            (settings.BASE_DIR / "data" / "asset_expansion_2026_09_04.json").read_text()
        )
        september_names = {record["name"] for record in september["records"]}
        self.assertEqual(len(september_names), 25)
        self.assertEqual(set(september["evidence_reviews"]), september_names)
        corrections = json.loads(
            (settings.BASE_DIR / "data" / "asset_corrections_2026_09_04.json").read_text()
        )
        retired_urls = {}
        for correction in corrections["corrections"]:
            for replacement in correction.get("replace_sources", []):
                retired_urls.setdefault(correction["name"], set()).add(replacement["old_url"])
                self.assertIn(
                    replacement["source"]["url"],
                    {source["url"] for source in records_by_name[correction["name"]]["sources"]},
                )
        manifest = json.loads(
            (settings.BASE_DIR / "data" / "asset_editorial_reviews.json").read_text()
        )
        additions_manifest = json.loads(
            (settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24.json").read_text()
        )
        expansion_manifest = json.loads(
            (
                settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24_expansion.json"
            ).read_text()
        )
        hampton_roads_manifest = json.loads(
            (
                settings.BASE_DIR
                / "data"
                / "asset_editorial_reviews_2026_08_25_hampton_roads.json"
            ).read_text()
        )
        manufacturing_manifest = json.loads(
            (
                settings.BASE_DIR
                / "data"
                / "asset_editorial_reviews_2026_08_30_manufacturing.json"
            ).read_text()
        )
        location_manifest = json.loads(
            (
                settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24_locations.json"
            ).read_text()
        )

        self.assertEqual(len(manifest["reviewed_assets"]), 429)
        self.assertEqual(len(manifest["follow_up_assets"]), 11)
        self.assertEqual(len(additions_manifest["reviewed_assets"]), 13)
        self.assertFalse(additions_manifest["follow_up_assets"])
        self.assertEqual(len(expansion_manifest["reviewed_assets"]), 20)
        self.assertFalse(expansion_manifest["follow_up_assets"])
        self.assertEqual(len(hampton_roads_manifest["reviewed_assets"]), 21)
        self.assertFalse(hampton_roads_manifest["follow_up_assets"])
        self.assertEqual(len(manufacturing_manifest["reviewed_assets"]), 7)
        self.assertFalse(manufacturing_manifest["follow_up_assets"])
        self.assertEqual(len(location_manifest["reviewed_assets"]), 97)
        self.assertFalse(location_manifest["follow_up_assets"])

        reviewed_names = set(manifest["reviewed_assets"])
        follow_up_names = set(manifest["follow_up_assets"])
        addition_names = set(additions_manifest["reviewed_assets"])
        expansion_names = set(expansion_manifest["reviewed_assets"])
        hampton_roads_names = set(hampton_roads_manifest["reviewed_assets"])
        manufacturing_names = set(manufacturing_manifest["reviewed_assets"])
        historical_names = reviewed_names | follow_up_names | addition_names
        self.assertFalse((reviewed_names | follow_up_names).intersection(addition_names))
        self.assertFalse(historical_names.intersection(expansion_names))
        self.assertFalse((historical_names | expansion_names).intersection(hampton_roads_names))
        self.assertEqual(
            (historical_names | expansion_names | hampton_roads_names).intersection(
                manufacturing_names
            ),
            {"Inertial Labs"},
        )
        source_backed_additions = {
            record["name"] for record in json.loads(
                (settings.BASE_DIR / "data/asset_interview_followup_2026_09_06.json").read_text()
            )["records"]
        }
        reviewed_or_flagged = (
            historical_names | expansion_names | hampton_roads_names
            | manufacturing_names | september_names
        )
        self.assertFalse(reviewed_or_flagged.intersection(source_backed_additions))
        self.assertEqual(reviewed_or_flagged | source_backed_additions, set(records_by_name))

        reviewed_assets = {
            **manifest["reviewed_assets"],
            **additions_manifest["reviewed_assets"],
            **expansion_manifest["reviewed_assets"],
            **hampton_roads_manifest["reviewed_assets"],
            **manufacturing_manifest["reviewed_assets"],
        }
        for name, source_urls in reviewed_assets.items():
            self.assertIn(name, records_by_name)
            attached_urls = {source["url"] for source in records_by_name[name]["sources"]}
            self.assertTrue(
                set(source_urls).issubset(attached_urls | retired_urls.get(name, set())), name
            )
        for name, source_urls in location_manifest["reviewed_assets"].items():
            self.assertIn(name, records_by_name)
            attached_urls = {source["url"] for source in records_by_name[name]["sources"]}
            self.assertTrue(set(source_urls).issubset(attached_urls), name)
        self.assertTrue(set(manifest["follow_up_assets"]).issubset(records_by_name))

        resolved_names = {
            "Amherst County Fire and EMS Drone Program",
            "Ashland Police Department Drone Program",
            "Haymarket Police Department Drone Program",
            "Madison County Sheriff's Office UAS Program",
            "Occoquan Police Department Public Safety Drone Program",
            "Radford City Police Department Drone Program",
            "Staunton Police Department UAS Program",
            "Wise County Sheriff's Office Drone Program",
            "Wythe County Sheriff's Office Drone Program",
        }
        self.assertTrue(resolved_names.issubset(manifest["reviewed_assets"]))
        for name in resolved_names:
            record = records_by_name[name]
            haymarket = name == "Haymarket Police Department Drone Program"
            self.assertEqual(record["activity_status"], "" if haymarket else "active")
            self.assertTrue(record["current_activity"])
            self.assertTrue(record["contact_phone"])
            self.assertEqual(
                record["activity_last_verified_at"],
                "2026-09-04" if haymarket else "2026-08-21",
            )

    def test_august_21_catalog_audit_remains_a_complete_historical_snapshot(self):
        catalog = self.load_catalog()
        audit = json.loads(
            (settings.BASE_DIR / "data" / "asset_catalog_audit_2026_08_21.json").read_text()
        )
        audit_by_name = {record["name"]: record for record in audit["records"]}

        self.assertEqual(audit["record_count"], 440)
        current_names = {record["name"] for record in catalog["records"]}
        current_equivalents = {
            {"Fort Barfoot": "Fort Pickett", "Fort Gregg-Adams": "Fort Lee"}.get(name, name)
            for name in audit_by_name
        }
        self.assertTrue(current_equivalents.issubset(current_names))
        self.assertEqual(
            audit["outcomes"],
            {
                "confirmed": 423,
                "confirmed-historical": 6,
                "qualified-follow-up": 11,
            },
        )
        self.assertTrue(
            all(record["evidence_urls"] and record["review_basis"] for record in audit["records"])
        )

    def test_august_21_company_and_source_corrections_are_conservative(self):
        records = self.load_catalog()["records"]
        records_by_name = {record["name"]: record for record in records}

        autonomous_flight = records_by_name["Autonomous Flight Technologies"]
        self.assertEqual(autonomous_flight["city"], "Salem")
        self.assertEqual(autonomous_flight["address_line"], "172 East Main Street")
        self.assertEqual(autonomous_flight["location_precision"], "exact")

        self.assertNotIn("Dedrone Washington-Area Headquarters", records_by_name)
        dedrone = records_by_name["Former Dedrone Washington-Area Headquarters"]
        self.assertEqual(dedrone["activity_status"], "historical")
        self.assertIn("Axon", dedrone["current_activity"])

        droneup = records_by_name["DroneUp"]
        self.assertEqual(droneup["activity_status"], "active")
        self.assertEqual(droneup["location_precision"], "exact")
        self.assertEqual(droneup["address_line"], "160 Newtown Road, Suite 500")
        self.assertIn("airspace management", droneup["current_activity"])

        all_source_urls = {source["url"] for record in records for source in record["sources"]}
        self.assertNotIn(
            "https://www.townofhaymarket.org/sites/default/files/fileattachments/police/"
            "page/2971/haymarket_police_department_annual_report_2022.pdf",
            all_source_urls,
        )
        self.assertNotIn("https://www.navair.navy.mil/contact-us", all_source_urls)
        self.assertNotIn("https://www.yorkcounty.gov/99/Fire-Life-Safety", all_source_urls)

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
        self.assertEqual(
            Asset.public.filter(record_type=Asset.RecordType.UNIVERSITY).count(),
            sum(
                record["record_type"] == Asset.RecordType.UNIVERSITY
                for record in catalog["records"]
            ),
        )
        self.assertFalse(
            Asset.public.filter(
                record_type=Asset.RecordType.UNIVERSITY,
                name__in=SPECIALIZED_HIGHER_ED_EXCLUSIONS,
            ).exists()
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
        self.assertEqual(nasa.contact_url, "https://www.nasa.gov/langley/frontdoor/")
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

        dzyne = records_by_name["DZYNE Technologies"]
        self.assertEqual(dzyne["location_precision"], "exact")
        self.assertEqual(
            dzyne["address_line"], "8280 Willow Oaks Corporate Drive, Suite 200"
        )
        self.assertIn("Ondas Sentinel", dzyne["short_description"])

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

    def test_priority_asset_profiles_use_current_official_evidence(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}
        priority_assets = {
            "Advanced Aircraft Company",
            "AeroVironment Corporate Headquarters",
            "ANRA Technologies",
            "Aurora Flight Sciences",
            "HII Unmanned Systems Center of Excellence",
            "Longbow Unmanned Systems Research and Test Center",
            "Mid-Atlantic Aviation Partnership",
            "Newport News AirCommerce Park",
            "ODU Institute for Autonomous and Connected Systems",
            "ODU Maritime Autonomous Systems Test Site",
            "Virginia Tech Drone Park",
            "Virginia Unmanned Systems Center",
            "Wallops Research Park",
        }

        self.assertTrue(priority_assets.issubset(records_by_name))
        for name in priority_assets:
            record = records_by_name[name]
            source_urls = {source["url"] for source in record["sources"]}
            self.assertTrue(record["activity_status"], name)
            self.assertTrue(record["current_activity"], name)
            self.assertTrue(record["partnership_opportunities"], name)
            self.assertEqual(record["activity_last_verified_at"], "2026-08-21")
            self.assertIn(record["activity_source_url"], source_urls)
            self.assertIn(record["contact_url"], source_urls)

    def test_university_programs_use_documented_campus_or_facility_locations(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}

        campus_program = records_by_name["George Mason Autonomous Robotics Laboratory"]
        self.assertEqual(campus_program["address_line"], "4400 University Dr")
        self.assertEqual(campus_program["location_precision"], "site")
        self.assertTrue(
            any("nces.ed.gov/ipeds" in source["url"] for source in campus_program["sources"])
        )

        facility_locations = {
            "Amherst County Fire and EMS Drone Program": "119 Taylor Street",
            "Kentland Experimental Aerial Systems Laboratory": (
                "Kentland Farm, 5250 Whitethorne Road"
            ),
            "Mid-Atlantic Aviation Partnership": "1991 Kraft Drive, Building 19",
            "Mid-Atlantic Regional Spaceport": "7414 Atlantic Road",
            "NASA Wallops Flight Facility": "34200 Fulton Street",
            "Staunton Police Department UAS Program": "116 West Beverley Street",
            "UVA Link Lab": "Olsson Hall, 151 Engineer's Way",
            "Virginia Tech Transportation Institute": "3500 Transportation Research Plaza",
        }
        for name, address in facility_locations.items():
            record = records_by_name[name]
            self.assertEqual(record["address_line"], address, name)
            self.assertIn(record["location_precision"], {"site", "exact"}, name)
            self.assertIsNotNone(record["latitude"], name)
            self.assertIsNotNone(record["longitude"], name)

        # A multi-county test corridor must not inherit the Blacksburg campus point.
        self.assertEqual(
            records_by_name["Virginia Automated Corridors"]["location_precision"],
            "locality",
        )

        precise_assets = {
            "ANRA Technologies",
            "AeroVironment Corporate Headquarters",
            "Aurora Flight Sciences",
            "Virginia Tech Drone Park",
            "Virginia Unmanned Systems Center",
        }
        for name in precise_assets:
            record = records_by_name[name]
            self.assertEqual(record["location_precision"], "site", name)
            self.assertTrue(record["address_line"], name)
            self.assertIsNotNone(record["latitude"], name)
            self.assertIsNotNone(record["longitude"], name)

        self.assertEqual(
            records_by_name["Newport News AirCommerce Park"]["available_acreage"],
            280,
        )
        for name in {
            "HII Unmanned Systems Center of Excellence",
            "ODU Maritime Autonomous Systems Test Site",
            "Virginia Tech Drone Park",
            "Wallops Research Park",
        }:
            record = records_by_name[name]
            self.assertTrue(record["development_status"], name)
            self.assertIsNone(record.get("available_acreage"), name)
            self.assertIn(
                record["development_source_url"],
                {source["url"] for source in record["sources"]},
            )

    def test_location_enrichment_uses_attached_public_sources(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}
        enrichment = json.loads(
            (settings.BASE_DIR / "data" / "asset_location_enrichment.json").read_text()
        )["assets"]

        self.assertEqual(len(enrichment), 97)
        self.assertTrue(set(enrichment).issubset(records_by_name))
        for name, location in enrichment.items():
            record = records_by_name[name]
            self.assertEqual(record["address_line"], location["address_line"], name)
            self.assertEqual(record["city"], location["city"], name)
            self.assertEqual(record["postal_code"], location["postal_code"], name)
            self.assertEqual(record["latitude"], location["latitude"], name)
            self.assertEqual(record["longitude"], location["longitude"], name)
            self.assertEqual(record["location_precision"], location["location_precision"], name)
            self.assertIn(
                location["source"]["url"],
                {source["url"] for source in record["sources"]},
                name,
            )

        self.assertEqual(records_by_name["Dynamic Aviation"]["city"], "Bridgewater")
        self.assertEqual(
            records_by_name["UVA Coastal Research Center UAS Operations"]["city"],
            "Cape Charles",
        )
        self.assertEqual(
            records_by_name["Virginia Tech Eastern Shore AREC Drone Application Research"][
                "city"
            ],
            "Painter",
        )
        self.assertEqual(
            records_by_name["SubSea Craft Virginia Beach Operations"]["address_line"],
            "2517 Squadron Court",
        )

    def test_every_asset_has_one_documented_ecosystem_role(self):
        catalog = self.load_catalog()
        records_by_name = {record["name"]: record for record in catalog["records"]}
        role_categories = {
            "Core unmanned-systems asset",
            "Supporting ecosystem asset",
        }

        for record in catalog["records"]:
            self.assertEqual(
                len(role_categories.intersection(record["strategic_categories"])),
                1,
                record["name"],
            )

        for name in {
            "Mid-Atlantic Aviation Partnership",
            "ODU Maritime Autonomous Systems Test Site",
            "Virginia Tech Drone Park",
        }:
            self.assertIn(
                "Core unmanned-systems asset",
                records_by_name[name]["strategic_categories"],
            )
        for name in {
            "Accomack County",
            "Newport News AirCommerce Park",
            "University of Virginia",
        }:
            self.assertIn(
                "Supporting ecosystem asset",
                records_by_name[name]["strategic_categories"],
            )

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
        self.assertEqual(asset.contact_url, "https://www.nasa.gov/langley/frontdoor/")
        self.assertTrue(asset.sources.filter(url=asset.contact_url, is_public=True).exists())
        self.assertTrue(
            asset.strategic_categories.filter(name="Core unmanned-systems asset").exists()
        )

    def test_profile_enrichment_adds_manufacturing_taxonomy_and_sources(self):
        asset = Asset.objects.create(
            name="Aeroprobe",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Staff-maintained Aeroprobe description.",
            unmanned_systems_relevance="Staff-maintained component relevance.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: curated-public-source.",
        )

        call_command("enrich_asset_profiles", verbosity=0)

        asset.refresh_from_db()
        self.assertEqual(asset.short_description, "Staff-maintained Aeroprobe description.")
        self.assertTrue(
            asset.strategic_categories.filter(name="Manufacturing facilities").exists()
        )
        self.assertTrue(
            asset.capabilities.filter(
                name="Manufacturing, materials, and prototyping"
            ).exists()
        )
        self.assertTrue(
            asset.sources.filter(
                url="https://www.vedp.org/news/aeroprobe-sets-companies-speed"
            ).exists()
        )

    def test_profile_enrichment_upgrades_only_coarse_priority_locations(self):
        coarse = Asset.objects.create(
            name="Virginia Unmanned Systems Center",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Statewide UxS coordination.",
            unmanned_systems_relevance="Coordinates the Commonwealth's UxS ecosystem.",
            city="Richmond",
            latitude="37.541000",
            longitude="-77.436000",
            location_precision=Asset.LocationPrecision.LOCALITY,
            contact_text=(
                "Public information route; a direct asset contact is not published in the catalog"
            ),
            contact_url="https://vipc.org/initiatives/virginia-unmanned-systems-center/",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: curated-public-source.",
        )
        hii = Asset.objects.create(
            name="HII Unmanned Systems Center of Excellence",
            record_type=Asset.RecordType.FACILITY,
            short_description="HII unmanned-systems facility.",
            unmanned_systems_relevance="Supports unmanned-systems production and testing.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Source.objects.create(
            asset=hii,
            title="Obsolete catalog location source",
            url="https://www.hampton.gov/CivicAlerts.aspx?AID=4656&ARC=9365",
            notes="Catalog provenance: curated-public-source",
        )

        call_command("enrich_asset_profiles", verbosity=0)

        coarse.refresh_from_db()
        self.assertEqual(coarse.address_line, "313 East Broad Street")
        self.assertEqual(coarse.location_precision, Asset.LocationPrecision.SITE)
        self.assertEqual(str(coarse.latitude), "37.543832")
        self.assertTrue(coarse.current_activity)
        self.assertEqual(
            coarse.contact_text,
            "Virginia Unmanned Systems Center and VIPC program inquiries",
        )
        self.assertEqual(coarse.contact_url, "https://vipc.org/contact-us/")
        self.assertTrue(
            coarse.strategic_categories.filter(name="Core unmanned-systems asset").exists()
        )
        self.assertFalse(
            hii.sources.filter(
                url="https://www.hampton.gov/CivicAlerts.aspx?AID=4656&ARC=9365"
            ).exists()
        )
        self.assertTrue(
            hii.sources.filter(url="https://www.hii.com/news/first-quarter-2021-earnings").exists()
        )

    def test_catalog_review_command_records_reviews_and_preserves_later_unverify(self):
        manifest = json.loads(
            (settings.BASE_DIR / "data" / "asset_editorial_reviews.json").read_text()
        )
        call_command("seed_real_data", verbosity=0)

        call_command("apply_catalog_reviews", verbosity=0)

        reviewed = Asset.objects.filter(
            name__in=manifest["reviewed_assets"],
            status=Asset.Status.PUBLISHED,
            reviewed_at__isnull=False,
            last_verified_at=date(2026, 8, 21),
        )
        # Six old reviews cite retired links; Blue Ridge now explicitly requires fresh review.
        self.assertEqual(reviewed.count(), len(manifest["reviewed_assets"]) - 7)
        self.assertFalse(reviewed.filter(name="Blue Ridge Defense Works").exists())
        self.assertFalse(reviewed.filter(name="Haymarket Police Department Drone Program").exists())
        self.assertEqual(
            Asset.objects.filter(
                name__in=manifest["follow_up_assets"],
                review_priority=Asset.ReviewPriority.HIGH,
                reviewed_at__isnull=True,
            ).count(),
            len(manifest["follow_up_assets"]),
        )
        self.assertTrue(
            Source.objects.filter(
                asset__name="CNU Autonomous Systems and Drone Lab",
                verification_status="verified",
                last_verified_at=date(2026, 8, 21),
            ).exists()
        )

        asset = Asset.objects.get(name="CNU Autonomous Systems and Drone Lab")
        review_comment_count = asset.review_comments.count()
        asset.status = Asset.Status.SOURCE_BACKED
        asset.last_verified_at = None
        asset.reviewed_at = None
        asset.reviewed_by = None
        asset.published_at = None
        asset.save()

        call_command("apply_catalog_reviews", verbosity=0)

        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
        self.assertIsNone(asset.reviewed_at)
        self.assertEqual(asset.review_comments.count(), review_comment_count)

    def test_august_24_company_additions_are_published_from_their_review_manifest(self):
        review_path = settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24.json"
        manifest = json.loads(review_path.read_text())
        call_command("seed_real_data", verbosity=0)

        call_command("apply_catalog_reviews", reviews=review_path, verbosity=0)

        reviewed = Asset.objects.filter(
            name__in=manifest["reviewed_assets"],
            status=Asset.Status.PUBLISHED,
            reviewed_at__isnull=False,
            last_verified_at=date(2026, 8, 24),
        )
        self.assertEqual(reviewed.count(), 13)
        self.assertEqual(
            Source.objects.filter(
                asset__name__in=manifest["reviewed_assets"],
                verification_status="verified",
                last_verified_at=date(2026, 8, 24),
            ).count(),
            sum(len(urls) for urls in manifest["reviewed_assets"].values()),
        )
        self.assertEqual(
            Asset.objects.get(name="SubSea Craft Virginia Beach Operations").activity_status,
            Asset.ActivityStatus.PLANNED,
        )

    def test_august_24_second_expansion_is_published_from_its_review_manifest(self):
        review_path = (
            settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24_expansion.json"
        )
        manifest = json.loads(review_path.read_text())
        call_command("seed_real_data", verbosity=0)

        call_command("apply_catalog_reviews", reviews=review_path, verbosity=0)

        reviewed = Asset.objects.filter(
            name__in=manifest["reviewed_assets"],
            status=Asset.Status.PUBLISHED,
            reviewed_at__isnull=False,
            last_verified_at=date(2026, 8, 24),
        )
        self.assertEqual(reviewed.count(), 20)
        self.assertEqual(
            Source.objects.filter(
                asset__name__in=manifest["reviewed_assets"],
                verification_status="verified",
                last_verified_at=date(2026, 8, 24),
            ).count(),
            sum(len(urls) for urls in manifest["reviewed_assets"].values()),
        )
        self.assertEqual(
            Asset.objects.get(name="Hampton Roads Mobility Innovation Center").activity_status,
            Asset.ActivityStatus.PLANNED,
        )
        self.assertEqual(
            Asset.objects.get(name="TurbineOne Headquarters and T1 Edgeworks").activity_status,
            Asset.ActivityStatus.PLANNED,
        )
        self.assertEqual(
            Asset.objects.get(name="BZRD Systems").activity_status,
            Asset.ActivityStatus.DEVELOPING,
        )

    def test_august_25_hampton_roads_expansion_is_published_from_review_manifest(self):
        review_path = (
            settings.BASE_DIR
            / "data"
            / "asset_editorial_reviews_2026_08_25_hampton_roads.json"
        )
        manifest = json.loads(review_path.read_text())
        call_command("seed_real_data", verbosity=0)

        call_command("apply_catalog_reviews", reviews=review_path, verbosity=0)

        reviewed = Asset.objects.filter(
            name__in=manifest["reviewed_assets"],
            status=Asset.Status.PUBLISHED,
            reviewed_at__isnull=False,
            last_verified_at=date(2026, 8, 25),
        )
        self.assertEqual(reviewed.count(), 21)
        self.assertEqual(
            Source.objects.filter(
                asset__name__in=manifest["reviewed_assets"],
                verification_status="verified",
                last_verified_at=date(2026, 8, 25),
            ).count(),
            sum(len(urls) for urls in manifest["reviewed_assets"].values()),
        )
        self.assertEqual(
            Asset.objects.get(name="Tidal Flight Chesapeake Development Hangar").activity_status,
            Asset.ActivityStatus.DEVELOPING,
        )
        self.assertEqual(
            Asset.objects.get(name="ODU National Security Institute").activity_status,
            Asset.ActivityStatus.ACTIVE,
        )
        wing = Asset.objects.get(name="Commander, Helicopter Sea Combat Wing Atlantic")
        self.assertEqual(wing.activity_status, Asset.ActivityStatus.ACTIVE)
        self.assertEqual(wing.location_precision, Asset.LocationPrecision.SITE)
        range_complex = Asset.objects.get(name="Virginia Capes Range Complex")
        self.assertEqual(range_complex.location_precision, Asset.LocationPrecision.REGIONAL)
        self.assertIsNone(range_complex.latitude)
        self.assertIsNone(range_complex.longitude)

    def test_august_30_manufacturing_expansion_is_published_from_review_manifest(self):
        review_path = (
            settings.BASE_DIR
            / "data"
            / "asset_editorial_reviews_2026_08_30_manufacturing.json"
        )
        manifest = json.loads(review_path.read_text())
        call_command("seed_real_data", verbosity=0)

        call_command("apply_catalog_reviews", reviews=review_path, verbosity=0)

        reviewed = Asset.objects.filter(
            name__in=manifest["reviewed_assets"],
            status=Asset.Status.PUBLISHED,
            reviewed_at__isnull=False,
            last_verified_at=date(2026, 8, 30),
        )
        # Wrap's former PDF is retired; its historical review cannot verify a different URL.
        self.assertEqual(reviewed.count(), 6)
        self.assertFalse(
            reviewed.filter(name="Wrap Technologies Norton Manufacturing Headquarters").exists()
        )
        self.assertEqual(
            Source.objects.filter(
                asset__name__in=manifest["reviewed_assets"],
                verification_status="verified",
                last_verified_at=date(2026, 8, 30),
            ).count(),
            sum(
                len(urls) for name, urls in manifest["reviewed_assets"].items()
                if name != "Wrap Technologies Norton Manufacturing Headquarters"
            ),
        )
        self.assertEqual(
            Asset.objects.get(
                name="Micron Manassas Semiconductor Fabrication Plant"
            ).activity_status,
            Asset.ActivityStatus.ACTIVE,
        )
        wrap = Asset.objects.get(
            name="Wrap Technologies Norton Manufacturing Headquarters"
        )
        self.assertEqual(wrap.location_precision, Asset.LocationPrecision.EXACT)
        self.assertTrue(
            wrap.strategic_categories.filter(name="Manufacturing facilities").exists()
        )
        self.assertTrue(
            Asset.objects.get(name="Inertial Labs")
            .strategic_categories.filter(name="Manufacturing facilities")
            .exists()
        )
        self.assertEqual(
            set(manifest["excluded_candidates"]),
            {
                "Avio USA Hurt solid rocket motor facility",
                "StewTech Virginia manufacturing facility",
            },
        )

    def test_location_review_batch_supplements_existing_catalog_reviews(self):
        review_paths = [
            settings.BASE_DIR / "data" / "asset_editorial_reviews.json",
            settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24.json",
            settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24_expansion.json",
        ]
        location_path = (
            settings.BASE_DIR / "data" / "asset_editorial_reviews_2026_08_24_locations.json"
        )
        location_manifest = json.loads(location_path.read_text())
        call_command("seed_real_data", verbosity=0)
        call_command("enrich_asset_profiles", verbosity=0)

        for review_path in review_paths:
            call_command("apply_catalog_reviews", reviews=review_path, verbosity=0)
        call_command("apply_catalog_reviews", reviews=location_path, verbosity=0)

        for name, source_urls in location_manifest["reviewed_assets"].items():
            asset = Asset.objects.get(name=name)
            self.assertIsNotNone(asset.reviewed_at, name)
            self.assertEqual(
                set(
                    asset.sources.filter(
                        url__in=source_urls,
                        verification_status="verified",
                        last_verified_at=date(2026, 8, 24),
                    ).values_list("url", flat=True)
                ),
                set(source_urls),
                name,
            )

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

    def test_deployment_enrichment_renames_legacy_catalog_assets_and_updates_broad_websites(self):
        factbook_url = (
            "https://www.vada.virginia.gov/media/governorvirginiagov/"
            "secretary-of-veterans-and-defense-affairs/pdf/VA-FactBook_WEB_2020-10-19-CSG.pdf"
        )
        legacy = Asset.objects.create(
            name="Fort A.P. Hill",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Legacy catalog record.",
            unmanned_systems_relevance="Federal and defense ecosystem presence.",
            website_url=factbook_url,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: virginia-military-factbook.",
        )
        legacy_fort_lee = Asset.objects.create(
            name="Fort Gregg-Adams",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Legacy catalog record.",
            unmanned_systems_relevance="Federal and defense ecosystem presence.",
            website_url=factbook_url,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: virginia-military-factbook.",
        )
        legacy_fort_pickett = Asset.objects.create(
            name="Fort Barfoot",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Legacy catalog record.",
            unmanned_systems_relevance="Federal and defense ecosystem presence.",
            website_url=factbook_url,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: virginia-military-factbook.",
        )
        dominion = Asset.objects.create(
            name="Dominion Energy UAS Program",
            record_type=Asset.RecordType.PROGRAM,
            short_description="Legacy catalog record.",
            unmanned_systems_relevance="Utility unmanned-aircraft operations.",
            website_url="https://www.dominionenergy.com/our-stories/unmanned-aerial-inspections",
            contact_url="https://www.dominionenergy.com/our-stories/unmanned-aerial-inspections",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: curated-public-source.",
        )
        Source.objects.create(
            asset=dominion,
            title="Obsolete Dominion catalog source",
            url="https://www.dominionenergy.com/our-stories/unmanned-aerial-inspections",
            notes="Catalog provenance: curated-public-source",
        )

        call_command("seed_real_data", add_missing=True, verbosity=0)
        call_command("enrich_asset_profiles", verbosity=0)

        legacy.refresh_from_db()
        legacy_fort_lee.refresh_from_db()
        legacy_fort_pickett.refresh_from_db()
        self.assertEqual(legacy.name, "Fort Walker")
        self.assertEqual(legacy.website_url, "https://home.army.mil/aphill/")
        self.assertEqual(legacy_fort_lee.name, "Fort Lee")
        self.assertEqual(legacy_fort_pickett.name, "Fort Pickett")
        self.assertFalse(Asset.objects.filter(name="Fort A.P. Hill").exists())
        self.assertFalse(Asset.objects.filter(name="Fort Gregg-Adams").exists())
        self.assertFalse(Asset.objects.filter(name="Fort Barfoot").exists())
        self.assertEqual(Asset.objects.filter(name="Fort Walker").count(), 1)
        self.assertEqual(Asset.objects.filter(name="Fort Lee").count(), 1)
        self.assertEqual(Asset.objects.filter(name="Fort Pickett").count(), 1)
        dominion.refresh_from_db()
        self.assertEqual(
            dominion.website_url,
            "https://www.dominionenergy.com/about/delivering-energy/electric-projects",
        )
        self.assertFalse(
            dominion.sources.filter(
                url="https://www.dominionenergy.com/our-stories/unmanned-aerial-inspections"
            ).exists()
        )

    def test_deployment_enrichment_applies_documented_location_upgrade(self):
        dynamic = Asset.objects.create(
            name="Dynamic Aviation",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Legacy catalog record.",
            unmanned_systems_relevance="Aviation and unmanned-systems support.",
            city="Harrisonburg",
            latitude="38.449000",
            longitude="-78.869000",
            location_precision=Asset.LocationPrecision.LOCALITY,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: curated-public-source.",
        )

        call_command("seed_real_data", add_missing=True, verbosity=0)
        call_command("enrich_asset_profiles", verbosity=0)

        dynamic.refresh_from_db()
        self.assertEqual(dynamic.address_line, "1402 Airport Road")
        self.assertEqual(dynamic.city, "Bridgewater")
        self.assertEqual(dynamic.postal_code, "22812-0007")
        self.assertEqual(dynamic.location_precision, Asset.LocationPrecision.EXACT)
        self.assertTrue(
            dynamic.sources.filter(
                url="https://www.dynamicaviation.com/contact-us/"
            ).exists()
        )

    def test_deployment_enrichment_resolves_named_first_responder_operator(self):
        legacy = Asset.objects.create(
            name="City of Radford First Responder UAS Capability",
            record_type=Asset.RecordType.PROGRAM,
            short_description=(
                "A CY 2026 Virginia DCJS award documents an unmanned aircraft already in use "
                "by an eligible local first responder agency in City of Radford; the public "
                "award record does not identify the operating department."
            ),
            overview="Legacy generic jurisdiction-level profile.",
            unmanned_systems_relevance="Public-safety UAS capability.",
            website_url=(
                "https://www.vaco.org/wp-content/uploads/2025/12/DCJS-Meeting-UAB-Chart.pdf"
            ),
            contact_text="Site operator or program information",
            contact_url=(
                "https://www.dcjs.virginia.gov/grants/programs/"
                "cy-26-unmanned-aircraft-trade-and-replace-program"
            ),
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: curated-public-source.",
        )

        call_command("seed_real_data", add_missing=True, verbosity=0)
        call_command("enrich_asset_profiles", verbosity=0)

        legacy.refresh_from_db()
        self.assertEqual(legacy.name, "Radford City Police Department Drone Program")
        self.assertIn("Skydio X10", legacy.short_description)
        self.assertEqual(legacy.contact_phone, "540-731-3624")
        self.assertEqual(legacy.activity_status, Asset.ActivityStatus.ACTIVE)
        self.assertEqual(
            legacy.website_url,
            "https://www.radfordva.gov/AgendaCenter/ViewFile/Minutes/_01272026-805",
        )

    def test_deployment_enrichment_applies_audited_company_corrections(self):
        autonomous_flight = Asset.objects.create(
            name="Autonomous Flight Technologies",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description=(
                "Roanoke-based developer of unmanned aircraft, avionics, and "
                "autonomous-flight technologies."
            ),
            unmanned_systems_relevance="UAS technology company.",
            city="Roanoke",
            latitude="37.271000",
            longitude="-79.941000",
            location_precision=Asset.LocationPrecision.LOCALITY,
            website_url="https://www.autonomousflight.us/company",
            contact_url="https://www.autonomousflight.us/contact-offices",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: curated-public-source.",
        )
        dedrone = Asset.objects.create(
            name="Dedrone Washington-Area Headquarters",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description=(
                "Sterling headquarters for counter-drone sensing, identification, tracking, "
                "and airspace-security technology."
            ),
            unmanned_systems_relevance="Counter-UAS company.",
            city="Sterling",
            latitude="39.006000",
            longitude="-77.428000",
            location_precision=Asset.LocationPrecision.LOCALITY,
            website_url="https://www.dedrone.com/about/contact-us",
            contact_url="https://www.dedrone.com/contact",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            internal_notes="Catalog provenance: curated-public-source.",
        )

        call_command("seed_real_data", add_missing=True, verbosity=0)
        call_command("enrich_asset_profiles", verbosity=0)

        autonomous_flight.refresh_from_db()
        self.assertEqual(autonomous_flight.city, "Salem")
        self.assertEqual(autonomous_flight.address_line, "172 East Main Street")
        self.assertEqual(
            autonomous_flight.location_precision,
            Asset.LocationPrecision.EXACT,
        )
        dedrone.refresh_from_db()
        self.assertEqual(dedrone.name, "Former Dedrone Washington-Area Headquarters")
        self.assertEqual(dedrone.activity_status, Asset.ActivityStatus.HISTORICAL)
        self.assertIn("Axon", dedrone.current_activity)

    def test_deployment_enrichment_preserves_staff_website_edits(self):
        call_command("seed_real_data", verbosity=0)
        nasa = Asset.objects.get(name="NASA Langley Research Center")
        nasa.website_url = "https://example.org/staff-reviewed-nasa-page"
        nasa.save(update_fields=["website_url", "updated_at"])

        call_command("enrich_asset_profiles", verbosity=0)

        nasa.refresh_from_db()
        self.assertEqual(
            nasa.website_url,
            "https://example.org/staff-reviewed-nasa-page",
        )
