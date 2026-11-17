#!/usr/bin/env python3
"""Retrieve Census display boundaries and locality reference points for benchmark states."""

import csv
import io
import json
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.assets.geography import STATES  # noqa: E402

FIPS = {
    "AZ": "04",
    "CA": "06",
    "CO": "08",
    "FL": "12",
    "MI": "26",
    "NY": "36",
    "NC": "37",
    "ND": "38",
    "OH": "39",
    "OK": "40",
    "PA": "42",
    "TX": "48",
    "UT": "49",
}
SERVICE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer"
GAZETTEER = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2026_Gazetteer/2026_Gaz_place_national.zip"
)


def get(url):
    with urllib.request.urlopen(url, timeout=180) as response:
        return response.read()


def build():
    output = ROOT / "static/data/states"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "retrieved": "2026-11-17",
        "source": SERVICE,
        "note": "Simplified display boundaries only; not survey or operational geometry.",
        "states": {},
    }
    for state in STATES[1:]:
        stats = {}
        for kind, layer in (("boundary", 0), ("counties", 1)):
            params = urllib.parse.urlencode(
                {
                    "where": f"STATE='{FIPS[state.code]}'",
                    "outFields": "STATE,NAME,GEOID",
                    "outSR": "4326",
                    "f": "geojson",
                    "returnGeometry": "true",
                    "maxAllowableOffset": "0.005",
                    "geometryPrecision": "5",
                }
            )
            url = f"{SERVICE}/{layer}/query?{params}"
            collection = json.loads(get(url))
            if (
                collection.get("type") != "FeatureCollection"
                or not collection.get("features")
                or collection.get("exceededTransferLimit")
            ):
                raise ValueError(f"Incomplete Census geometry for {state.code}")
            if any(f["properties"]["STATE"] != FIPS[state.code] for f in collection["features"]):
                raise ValueError(f"Wrong state geometry: {state.code}")
            (output / f"{state.slug}-{kind}.geojson").write_text(
                json.dumps(collection, separators=(",", ":")) + "\n"
            )
            stats[kind] = {"features": len(collection["features"]), "url": url}
        manifest["states"][state.code] = stats
        print(state.code, stats["counties"]["features"], flush=True)
    with zipfile.ZipFile(io.BytesIO(get(GAZETTEER))) as archive:
        raw = archive.read(next(name for name in archive.namelist() if name.endswith(".txt")))
    text = raw.decode("utf-8-sig")
    delimiter = "|" if "|" in text.splitlines()[0] else "\t"
    rows = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    places = []
    for original in rows:
        row = {key.strip(): value.strip() for key, value in original.items()}
        if row.get("USPS") not in FIPS:
            continue
        places.append(
            {
                "state": row["USPS"],
                "name": row["NAME"],
                "geoid": row["GEOID"],
                "latitude": float(row["INTPTLAT"]),
                "longitude": float(row["INTPTLONG"]),
            }
        )
    (ROOT / "data/multistate").mkdir(parents=True, exist_ok=True)
    (ROOT / "data/multistate/locality_references.json").write_text(
        json.dumps(
            {
                "source": GAZETTEER,
                "retrieved": "2026-11-17",
                "note": "Census representative locality points, never facility coordinates.",
                "places": places,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    (ROOT / "data/multistate/geography_sources.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    build()
