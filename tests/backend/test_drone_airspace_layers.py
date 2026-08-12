import json
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "static" / "data"


def load_layer(filename):
    return json.loads((DATA_DIR / filename).read_text())


class DroneAirspaceLayerTests(SimpleTestCase):
    def test_faa_uas_facility_map_has_documented_virginia_cells(self):
        layer = load_layer("virginia-uas-facility-map.geojson")

        self.assertEqual(layer["metadata"]["feature_count"], len(layer["features"]))
        self.assertGreater(len(layer["features"]), 6_000)
        self.assertEqual(
            {feature["properties"]["ceiling_agl_ft"] for feature in layer["features"]},
            {0, 50, 100, 150, 200, 250, 300, 350, 400},
        )
        self.assertIn("not flight authorization", layer["metadata"]["disclaimer"])
        self.assertTrue(all(feature["properties"]["airports"] for feature in layer["features"]))

    def test_surface_controlled_airspace_only_contains_surface_b_c_d_or_e(self):
        layer = load_layer("virginia-surface-controlled-airspace.geojson")

        self.assertEqual(layer["metadata"]["feature_count"], 33)
        self.assertEqual(len(layer["features"]), 33)
        self.assertLessEqual(
            {feature["properties"]["class"] for feature in layer["features"]},
            {"B", "C", "D", "E"},
        )
        self.assertTrue(
            all(feature["properties"]["lower_limit"] == "Surface" for feature in layer["features"])
        )
        self.assertIn(
            "WASHINGTON-TRI AREA CLASS B",
            {feature["properties"]["name"] for feature in layer["features"]},
        )

    def test_constraint_layer_distinguishes_security_and_special_use(self):
        layer = load_layer("virginia-flight-constraints.geojson")
        types = {
            feature["properties"]["constraint_type"] for feature in layer["features"]
        }

        self.assertEqual(layer["metadata"]["feature_count"], 139)
        self.assertEqual(types, {"national-security-uas", "special-use"})
        self.assertIn("not real-time", layer["metadata"]["disclaimer"])
        self.assertTrue(
            all(feature["properties"]["floor"] for feature in layer["features"])
        )

    def test_test_facilities_have_published_specs_constraints_and_sources(self):
        layer = load_layer("virginia-uas-test-sites.geojson")
        required = {
            "name",
            "site_type",
            "published_size",
            "launch_recovery",
            "support_infrastructure",
            "aircraft_scope",
            "flight_constraints",
            "access",
            "source_title",
            "source_url",
        }

        self.assertEqual(layer["metadata"]["feature_count"], 3)
        self.assertEqual(
            {feature["properties"]["name"] for feature in layer["features"]},
            {
                "MARS UAS Airfield",
                "NASA Langley UAS Test Range and CERTAIN",
                "Virginia Tech Drone Park",
            },
        )
        for feature in layer["features"]:
            properties = feature["properties"]
            self.assertFalse(required - properties.keys())
            self.assertTrue(properties["source_url"].startswith("https://"))
