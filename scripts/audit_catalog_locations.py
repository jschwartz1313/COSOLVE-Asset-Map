#!/usr/bin/env python3
"""Compare public catalog addresses with Census results without moving points automatically."""

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def record_key(record):
    identity = [
        record["name"],
        record.get("address_line", ""),
        record.get("city", ""),
        record.get("postal_code", ""),
    ]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:16]


def prepare(records, path):
    with path.open("w", newline="") as destination:
        writer = csv.writer(destination)
        for record in records:
            if record.get("address_line") and record["location_precision"] in {"exact", "site"}:
                writer.writerow(
                    [
                        record_key(record),
                        record["address_line"],
                        record["city"],
                        "VA",
                        record.get("postal_code", ""),
                    ]
                )


def audit(records, path, checked_at):
    with path.open(newline="") as source:
        rows = {row[0]: row for row in csv.reader(source) if row}
    results = []
    for record in records:
        item = {
            "name": record["name"],
            "precision": record["location_precision"],
            "address": record.get("address_line", ""),
            "city": record.get("city", ""),
            "latitude": record["latitude"],
            "longitude": record["longitude"],
        }
        row = rows.get(record_key(record))
        if row and len(row) >= 6 and row[2] == "Match":
            lon, lat = map(float, row[5].split(","))
            delta = 111.2 * math.hypot(
                lat - record["latitude"], (lon - record["longitude"]) * math.cos(math.radians(lat))
            )
            item.update(
                {
                    "matched_address": row[4],
                    "census_match_type": row[3],
                    "census_latitude": lat,
                    "census_longitude": lon,
                    "distance_km": round(delta, 3),
                }
            )
            item["outcome"] = "address-match" if delta <= 1 else "reference-point-difference"
            if delta > 1:
                item["note"] = (
                    "Review the campus/site or FAA reference point against the street-address "
                    "interpolation. A difference does not establish that the catalog is wrong; "
                    "Census can choose a similarly named street. No automatic relocation."
                )
        elif row:
            item["outcome"] = "no-census-match"
            item["note"] = "Published address retained; Census non-match does not disprove a site."
        elif record["location_precision"] == "regional":
            item["outcome"] = "regional-no-single-site"
            item["note"] = (
                "A regional program or operating area is not represented by a single point."
            )
        elif record["provenance"] == "faa-public-airport":
            item["outcome"] = "faa-reference-coordinate"
            item["note"] = "Published FAA airport reference point retained."
        elif record["location_precision"] == "locality":
            item["outcome"] = "locality-follow-up"
            item["note"] = (
                "Retain locality precision until an official public street/site address is "
                "corroborated. Generalized defense locations stay generalized under catalog policy."
            )
        else:
            item["outcome"] = "not-geocoded"
        results.append(item)
    return {
        "checked_at": checked_at,
        "record_count": len(records),
        "counts": dict(Counter(item["outcome"] for item in results)),
        "precision_counts": dict(Counter(item["precision"] for item in results)),
        "methodology": (
            "Every current catalog record has a location-review disposition. Published public "
            "addresses were submitted to the U.S. Census Public_AR_Current address-batch "
            "geocoder. Matches are address-range estimates, not rooftop surveys, property "
            "access instructions, or proof that the organization occupies the address. "
            "Unmatched addresses, campus points, FAA coordinates, regional areas, and "
            "generalized records are retained and explicitly identified. New public-address "
            "evidence and geographic qualifications are in the expansion and correction files."
        ),
        "geocoder": "https://geocoding.geo.census.gov/geocoder/locations/addressbatch",
        "records": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/virginia_real_assets.json")
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checked-at", default="2026-09-04")
    options = parser.parse_args()
    records = json.loads(options.catalog.read_text())["records"]
    if options.prepare:
        prepare(records, options.prepare)
    if options.results and options.output:
        report = audit(records, options.results, options.checked_at)
        options.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps(report["counts"], sort_keys=True))
    if not options.prepare and not (options.results and options.output):
        parser.error("Use --prepare CSV or --results CSV --output JSON.")


if __name__ == "__main__":
    main()
