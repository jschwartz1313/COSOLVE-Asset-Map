#!/usr/bin/env python3
"""Validate staged FAA snapshots and optionally publish the reviewed files."""

import argparse
import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

from django.contrib.gis.gdal import GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "static" / "data"
FILES = (
    "virginia-uas-facility-map.geojson",
    "virginia-surface-controlled-airspace.geojson",
    "virginia-flight-constraints.geojson",
    "virginia-heliports.geojson",
)


def validate_layer(candidate, previous, today=None):
    today = today or datetime.now(UTC).date()
    if candidate.get("type") != "FeatureCollection":
        raise ValueError("Expected a FeatureCollection")
    features = candidate["features"]
    metadata = candidate["metadata"]
    if date.fromisoformat(metadata["generated_at"]) != today:
        raise ValueError("Candidate must record today's actual retrieval date")
    if not features or len(features) != metadata["feature_count"]:
        raise ValueError("Empty layer or inconsistent feature count")
    old_count = len(previous["features"])
    if old_count and abs(len(features) - old_count) / old_count > 0.25:
        raise ValueError("Feature count changed by more than 25%; investigate before publishing")
    if metadata["source_url"] != previous["metadata"]["source_url"]:
        raise ValueError("Source changed; manual source review required")
    required_properties = set.intersection(*(set(f["properties"]) for f in previous["features"]))
    identifiers = []
    for feature in features:
        if required_properties - feature["properties"].keys():
            raise ValueError("Required popup fields are missing")
        try:
            geometry = GEOSGeometry(json.dumps(feature["geometry"]), srid=4326)
        except (GDALException, GEOSException, KeyError, TypeError) as exc:
            raise ValueError("Unparseable geometry") from exc
        if geometry.empty or not geometry.valid:
            raise ValueError("Empty or invalid geometry")
        identifiers.append(feature.get("id", feature["properties"].get("identifier")))
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate feature identifiers")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    for filename in FILES:
        candidate = json.loads((args.candidate_dir / filename).read_text())
        previous = json.loads((DATA_DIR / filename).read_text())
        validate_layer(candidate, previous)
        print(f"{filename}: {len(previous['features'])} -> {len(candidate['features'])} features")
    # Do not replace any shipped file until every candidate passes validation.
    if args.publish:
        for filename in FILES:
            shutil.copyfile(args.candidate_dir / filename, DATA_DIR / filename)
        print("Published validated snapshots. Facility specifications were not re-dated.")


if __name__ == "__main__":
    main()
