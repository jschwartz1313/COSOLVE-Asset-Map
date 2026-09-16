import copy
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from apps.core.map_layers import layer_freshness, snapshot_date
from scripts import build_drone_airspace_layers as builder
from scripts.review_reference_refresh import FILES, validate_layer


class LayerFreshnessTests(SimpleTestCase):
    def test_actual_snapshot_dates_and_individual_review_intervals(self):
        with patch("apps.core.map_layers.snapshot_date", return_value=date(2026, 9, 1)):
            result = layer_freshness(today=date(2026, 9, 8))
        self.assertTrue(result["controlled_airspace"]["review_due"])
        self.assertFalse(result["heliports"]["review_due"])
        self.assertEqual(result["heliports"]["due_date"], date(2026, 9, 29))
        self.assertEqual(result["uas_test_sites"]["due_date"], date(2026, 11, 30))
        self.assertEqual(result["uas_facility_map"]["version"], "2026-09-01")

    def test_unavailable_or_future_dates_are_not_presented_as_fresh(self):
        for value in (None, date(2030, 1, 1)):
            with patch("apps.core.map_layers.snapshot_date", return_value=value):
                result = layer_freshness(today=date(2026, 9, 15))
            for layer in result.values():
                self.assertTrue(layer["review_due"])
                self.assertIsNone(layer["snapshot_date"])
                self.assertEqual(layer["version"], "unknown")

    def test_malformed_and_missing_metadata_do_not_break_the_map(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "layer.json"
            for index, content in enumerate(("invalid", "{}", '{"metadata":null}')):
                path.write_text(content)
                self.assertIsNone(snapshot_date(str(path), index))
            self.assertIsNone(snapshot_date(str(Path(directory) / "missing.json"), 0))

    def test_dates_are_visible_next_to_the_layer_controls(self):
        result = layer_freshness(today=date(2026, 9, 15))
        html = render_to_string("map/viewer.html", {
            "layer_freshness": result, "request": RequestFactory().get("/map/"),
        })
        self.assertEqual(html.count('class="layer-freshness'), 5)
        self.assertIn("Snapshot", html)
        self.assertIn("not live flight permissions", html)
        self.assertNotIn("retrieved August 12, 2026", html)
        self.assertIn(f'?v={result["uas_facility_map"]["version"]}', html)

    def test_curated_specs_are_not_redated_by_automated_builds(self):
        with TemporaryDirectory() as directory, patch.object(builder, "DATA_DIR", Path(directory)):
            builder.build_test_sites()
            payload = json.loads((Path(directory) / "virginia-uas-test-sites.geojson").read_text())
        self.assertEqual(payload["metadata"]["generated_at"], builder.TEST_SITES_REVIEWED_AT)

    def test_all_shipped_faa_snapshots_pass_validation(self):
        for filename in FILES:
            with self.subTest(filename=filename):
                payload = json.loads((settings.BASE_DIR / "static" / "data" / filename).read_text())
                retrieved = date.fromisoformat(payload["metadata"]["generated_at"])
                validate_layer(payload, payload, retrieved)

    def test_refresh_rejects_empty_incomplete_or_duplicate_data(self):
        previous = json.loads(
            (settings.BASE_DIR / "static/data/virginia-heliports.geojson").read_text()
        )
        today = date.fromisoformat(previous["metadata"]["generated_at"])
        for kind in ("empty", "count", "duplicate", "date", "fields", "source", "geometry"):
            with self.subTest(kind=kind):
                candidate = copy.deepcopy(previous)
                if kind == "empty":
                    candidate["features"] = []
                elif kind == "count":
                    candidate["metadata"]["feature_count"] += 1
                elif kind == "duplicate":
                    candidate["features"][1] = candidate["features"][0]
                elif kind == "date":
                    candidate["metadata"]["generated_at"] = "2000-01-01"
                elif kind == "fields":
                    del candidate["features"][0]["properties"]["name"]
                elif kind == "source":
                    candidate["metadata"]["source_url"] = "https://example.com"
                else:
                    candidate["features"][0]["geometry"] = {"type": "Point", "coordinates": []}
                with self.assertRaises(ValueError):
                    validate_layer(candidate, previous, today)
