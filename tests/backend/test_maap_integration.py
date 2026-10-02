import json
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.assets.management.commands.apply_catalog_corrections import (
    TAXONOMY_FIELDS,
    current_value,
    same_value,
)
from apps.assets.models import Asset
from apps.catalog.models import Region
from apps.sources.models import Source
from scripts.build_maap_flight_areas import REFERENCE, build_layer, polygon_geometries
from scripts.build_real_asset_catalog import MAAP_CORRECTIONS_PATH, MAAP_EXPANSION_PATH, validate

CATALOG = settings.BASE_DIR / "data/virginia_real_assets.json"


class MaapGeometryTests(SimpleTestCase):
    def test_shipped_outlines_are_reproducible_and_keep_source_qualifications(self):
        reference = json.loads(REFERENCE.read_text())
        layer = build_layer(reference)
        shipped = settings.BASE_DIR / "static/data/maap-flight-areas.geojson"
        self.assertEqual(layer, json.loads(shipped.read_text()))
        self.assertEqual(len(layer["features"]), 3)
        by_id = {f["id"]: f for f in layer["features"]}
        self.assertTrue(by_id["central-virginia"]["properties"]["draft"])
        self.assertIn("COA DRAFT", by_id["central-virginia"]["properties"]["boundary_status"])
        self.assertNotIn("blackstone", by_id)
        self.assertIn("Blackstone", layer["metadata"]["unmapped_areas"][0])
        for feature in layer["features"]:
            self.assertTrue(GEOSGeometry(json.dumps(feature["geometry"])).valid)
            self.assertTrue(feature["properties"]["source_sha256"])
            self.assertTrue(feature["properties"]["geometry_sha256"])
            self.assertIn("not flight authorization", feature["properties"]["access"])

    def test_kml_parser_preserves_holes_ignores_waypoints_and_does_not_use_z_as_ceiling(self):
        xml = '''<kml xmlns="http://www.opengis.net/kml/2.2"><Document>
        <Placemark><Point><coordinates>-77,37,5000</coordinates></Point></Placemark>
        <Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
        -78,37,0 -77,37,0 -77,38,0 -78,38,0 -78,37,0
        </coordinates></LinearRing></outerBoundaryIs><innerBoundaryIs><LinearRing><coordinates>
        -77.8,37.2,0 -77.8,37.4,0 -77.6,37.4,0 -77.6,37.2,0 -77.8,37.2,0
        </coordinates></LinearRing></innerBoundaryIs></Polygon></Placemark></Document></kml>'''
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.kml"
            path.write_text(xml)
            polygons = polygon_geometries(path)
            kmz = Path(directory) / "source.kmz"
            with ZipFile(kmz, "w") as archive:
                archive.writestr("doc.kml", xml)
            self.assertEqual(polygons, polygon_geometries(kmz))
        self.assertEqual(len(polygons), 1)
        self.assertEqual(len(polygons[0]["coordinates"]), 2)
        self.assertTrue(all(len(c) == 2 for ring in polygons[0]["coordinates"] for c in ring))
        geometry = GEOSGeometry(json.dumps(polygons[0]))
        self.assertFalse(geometry.contains(Point(-77.7, 37.3)))

    def test_malformed_empty_unclosed_or_entity_documents_fail_without_silent_repair(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.kml"
            for xml in (
                '<!DOCTYPE kml [<!ENTITY x "value">]><kml/>',
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>',
                '<kml xmlns="http://www.opengis.net/kml/2.2"><Polygon><outerBoundaryIs>'
                '<LinearRing><coordinates>-77,37 -77,38 -78,38 -78,37</coordinates>'
                '</LinearRing></outerBoundaryIs></Polygon></kml>',
            ):
                path.write_text(xml)
                with self.assertRaises(ValueError):
                    polygon_geometries(path)

    def test_corrected_facility_points_identify_sites_not_the_main_campus_or_area_centroids(self):
        records = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        ctrc = records["Virginia Tech Counter UAS Research and Testing Center"]
        outline = build_layer(json.loads(REFERENCE.read_text()))["features"][0]["geometry"]
        self.assertTrue(GEOSGeometry(json.dumps(outline)).contains(
            Point(ctrc["longitude"], ctrc["latitude"])
        ))
        self.assertIn("not a surveyed", ctrc["location_notes"])
        vertiport = records["Virginia Tech VTTI Smart Airspace Vertiport"]
        self.assertIn("8VA2", vertiport["location_notes"])
        for record in json.loads(MAAP_EXPANSION_PATH.read_text())["records"]:
            self.assertIsNone(record["latitude"])
            self.assertIsNone(record["longitude"])
        validate(list(records.values()), [(r["from"], r["type"], r["to"])
                                         for r in json.loads(CATALOG.read_text())["relationships"]])


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class MaapDeploymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.changes = json.loads(MAAP_CORRECTIONS_PATH.read_text())["corrections"]
        records = {r["name"]: r for r in json.loads(CATALOG.read_text())["records"]}
        for change in cls.changes:
            record = deepcopy(records[change["name"]])
            record.update(change["before"])
            region, _ = Region.objects.get_or_create(name=record["region"])
            asset = Asset(
                name=record["name"], region=region, status="source-backed", visibility="public",
                internal_notes=f"Catalog provenance: {record['provenance']}.",
            )
            for field in Asset._meta.concrete_fields:
                if field.name in record and field.name != "region":
                    value = record[field.name]
                    if isinstance(value, float):
                        value = str(value)
                    setattr(asset, field.name, field.to_python(value))
            asset.save()
            for field, model in TAXONOMY_FIELDS.items():
                getattr(asset, field).set([
                    model.objects.get_or_create(name=n)[0] for n in record[field]
                ])

    def apply(self):
        out = StringIO()
        call_command("apply_catalog_corrections", corrections=MAAP_CORRECTIONS_PATH, stdout=out)
        return out.getvalue()

    def test_material_changes_are_pending_not_verified_and_idempotent(self):
        self.assertIn("Applied 7", self.apply())
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            for field, value in change["after"].items():
                self.assertTrue(same_value(current_value(asset, field), value), (asset.name, field))
            self.assertEqual(asset.status, "source-backed")
            self.assertIsNone(asset.last_verified_at)
            self.assertIsNone(asset.reviewed_at)
        counts = Asset.history.count(), Source.objects.count()
        self.apply()
        self.assertEqual(counts, (Asset.history.count(), Source.objects.count()))

    def test_staff_changes_and_coordinate_conflicts_are_not_overwritten(self):
        changed = Asset.objects.get(name="Virginia Tech VTTI Smart Airspace Vertiport")
        changed.latitude, changed.longitude = 37.2, -80.4
        changed.location_precision = "site"
        changed.address_line = "Staff-reviewed location"
        changed.save()
        protected = Asset.objects.get(name="Mid-Atlantic Aviation Partnership")
        user = get_user_model().objects.create_user("reviewer")
        protected.reviewed_by = user
        protected.overview = "Staff-reviewed description"
        protected.save()
        self.apply()
        changed.refresh_from_db()
        protected.refresh_from_db()
        self.assertEqual(float(changed.latitude), 37.2)
        self.assertEqual(float(changed.longitude), -80.4)
        self.assertEqual(changed.address_line, "Staff-reviewed location")
        self.assertEqual(protected.overview, "Staff-reviewed description")

    def test_older_editorial_reviews_do_not_verify_new_material_claims(self):
        manifest = json.loads((settings.BASE_DIR / "data/asset_editorial_reviews.json").read_text())
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            for url in manifest["reviewed_assets"].get(asset.name, []):
                asset.sources.get_or_create(url=url, defaults={"title": "Prior official evidence"})
        self.apply()
        call_command("apply_catalog_reviews", stdout=StringIO())
        for change in self.changes:
            asset = Asset.objects.get(name=change["name"])
            self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
            self.assertIsNone(asset.reviewed_at)
            self.assertIsNone(asset.last_verified_at)

    def test_additions_are_safe_to_seed_twice_and_reference_page_is_readable(self):
        out = StringIO()
        call_command("seed_real_data", catalog=MAAP_EXPANSION_PATH, add_missing=True, stdout=out)
        count = Asset.objects.count()
        call_command("seed_real_data", catalog=MAAP_EXPANSION_PATH, add_missing=True, stdout=out)
        self.assertEqual(count, Asset.objects.count())
        self.assertEqual(Asset.public.filter(name__startswith="MAAP ").count(), 4)
        response = self.client.get("/references/maap/")
        self.assertContains(response, "COA DRAFT")
        self.assertContains(response, "R-6602A")
        self.assertContains(response, "700 ft AGL")
        self.assertContains(response, "7,000 ft MSL")
        self.assertNotContains(response, "sharingv2")
        self.assertNotContains(response, "personal/tomboj")
        with override_settings(REQUIRE_SITE_LOGIN=True):
            self.assertEqual(self.client.get("/references/maap/").status_code, 302)
