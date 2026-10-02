#!/usr/bin/env python3
"""Convert the supplied MAAP outlines without inventing operational boundaries."""

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

from django.contrib.gis.geos import GEOSGeometry

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "maap_reference_2026_10_02.json"
INPUT_DIR = ROOT / "data" / "references" / "maap"
OUTPUT = ROOT / "static" / "data" / "maap-flight-areas.geojson"
NAMESPACE = {"k": "http://www.opengis.net/kml/2.2"}
MAX_SOURCE_BYTES = 5_000_000


def polygon_geometries(path):
    """Ignore placemark points, camera positions, styling and ground-level Z values."""
    if path.suffix.lower() == ".kmz":
        with ZipFile(path) as archive:
            documents = [entry for entry in archive.infolist() if entry.filename.endswith(".kml")]
            if len(documents) != 1 or documents[0].file_size > MAX_SOURCE_BYTES:
                raise ValueError("Expected one bounded KML document in the KMZ")
            data = archive.read(documents[0])
    else:
        data = path.read_bytes()
    if len(data) > MAX_SOURCE_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsupported KML size or entity declaration")
    root = ET.fromstring(data)
    geometries = []
    for polygon in root.findall(".//k:Polygon", NAMESPACE):
        rings = []
        outer = polygon.find("k:outerBoundaryIs/k:LinearRing/k:coordinates", NAMESPACE)
        if outer is None:
            raise ValueError("Polygon is missing its outer ring")
        coordinates = [outer, *polygon.findall(
            "k:innerBoundaryIs/k:LinearRing/k:coordinates", NAMESPACE
        )]
        for element in coordinates:
            ring = []
            for token in (element.text or "").split():
                values = token.split(",")
                if len(values) not in (2, 3):
                    raise ValueError("Invalid KML coordinate")
                longitude, latitude = map(float, values[:2])
                if not (math.isfinite(longitude) and math.isfinite(latitude)
                        and -180 <= longitude <= 180 and -90 <= latitude <= 90):
                    raise ValueError("KML coordinate is out of range")
                ring.append([longitude, latitude])
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("KML polygon ring must be explicitly closed")
            rings.append(ring)
        geometry = {"type": "Polygon", "coordinates": rings}
        parsed = GEOSGeometry(json.dumps(geometry), srid=4326)
        if parsed.empty or not parsed.valid:
            raise ValueError("Invalid source polygon; manual source review required")
        geometries.append(geometry)
    if not geometries:
        raise ValueError("No polygons in supplied KML")
    return geometries


def build_layer(reference, input_dir=INPUT_DIR):
    features = []
    for area in reference["areas"]:
        filename = area["geometry_file"]
        if not filename:
            continue
        path = input_dir / filename
        polygons = polygon_geometries(path)
        geometry = polygons[0] if len(polygons) == 1 else {
            "type": "MultiPolygon", "coordinates": [p["coordinates"] for p in polygons]
        }
        properties = {
            **area,
            "geometry_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "imported_at": reference["imported_at"],
            "source_title": "MAAP supplied flight-area and capability references",
            "source_url": "/references/maap/",
            "asset_url": f"/assets/{area['asset_slug']}/",
            "access": "Coordinate a project with MAAP; map display is not flight authorization",
        }
        features.append({"type": "Feature", "id": area["id"],
                         "geometry": geometry, "properties": properties})
    return {
        "type": "FeatureCollection",
        "metadata": {
            "generated_at": reference["imported_at"],
            "feature_count": len(features),
            "source": reference["source"],
            "information_url": "/references/maap/",
            "source_url": "https://maap.ictas.vt.edu/capabilities/facilities.html",
            "disclaimer": reference["source_note"],
            "geometry_note": (
                "Original supplied outlines, including over-water areas; no clipping, invented "
                "Blackstone circle, inferred vertical limits or waypoint import. "
                "Central Virginia is labeled draft in its source KML."
            ),
            "unmapped_areas": [a["name"] for a in reference["areas"] if not a["source_file"]],
        },
        "features": features,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    payload = build_layer(json.loads(REFERENCE.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {len(payload['features'])} supplied MAAP outlines to {args.output}")


if __name__ == "__main__":
    main()
