#!/usr/bin/env python3
"""Build the checked-in Virginia heliport reference layer from FAA data."""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "data" / "virginia-heliports.geojson"
FAA_LAYER = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/ArcGIS/rest/services/"
    "US_Airport/FeatureServer/0"
)
FAA_DATA_PAGE = "https://www.faa.gov/data/aero_data"


def fetch_heliports():
    params = urllib.parse.urlencode(
        {
            "where": (
                "STATE='VA' AND PRIVATEUSE=1 AND OPERSTATUS='OPERATIONAL' "
                "AND TYPE_CODE='HP'"
            ),
            "outFields": "IDENT,NAME,SERVCITY",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    request = urllib.request.Request(
        f"{FAA_LAYER}/query?{params}",
        headers={"User-Agent": "cosolve-uxs-map-heliports/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        payload = json.load(response)
    if payload.get("error") or payload.get("exceededTransferLimit"):
        raise ValueError("FAA heliport response is incomplete or contains an error")
    return payload["features"]


def normalized_feature(feature):
    longitude, latitude = feature["geometry"]["coordinates"][:2]
    properties = feature["properties"]
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [round(longitude, 6), round(latitude, 6)],
        },
        "properties": {
            "identifier": (properties.get("IDENT") or "").strip(),
            "name": (properties.get("NAME") or "Unnamed heliport").strip(),
            "service_city": (properties.get("SERVCITY") or "").strip().title(),
            "use": "Private use",
            "status": "Operational",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT.parent)
    args = parser.parse_args()
    features = [
        normalized_feature(feature)
        for feature in fetch_heliports()
        if feature.get("geometry")
    ]
    features.sort(key=lambda feature: feature["properties"]["name"].casefold())
    if not features:
        raise ValueError("Refusing to publish an empty heliport layer")
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "generated_at": datetime.now(UTC).date().isoformat(),
            "feature_count": len(features),
            "source": "FAA Airports Feature Service",
            "source_url": FAA_LAYER,
            "information_url": FAA_DATA_PAGE,
            "scope": "Operational private-use heliports recorded by the FAA in Virginia",
            "disclaimer": (
                "Reference only. Inclusion does not imply public access, landing permission, "
                "operational availability, or authorization for any flight."
            ),
        },
        "features": features,
    }
    output = args.output_dir / OUTPUT.name
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(features)} Virginia heliports to {output}")


if __name__ == "__main__":
    main()
