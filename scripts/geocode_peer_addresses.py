#!/usr/bin/env python3
"""Geocode published peer-site addresses, retaining only exact address matches."""

import csv
import io
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
DOCUMENTATION = "https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html"


def build():
    records = []
    for path in sorted((ROOT / "data/multistate").glob("*_starter.json")):
        records.extend(json.loads(path.read_text())["records"])
    candidates = [
        record
        for record in records
        if record.get("address_line")
        and record.get("location_source_url")
        and re.match(r"^\d+\s", record["address_line"])
        and record.get("latitude") is None
        and record.get("location_precision") != "regional"
    ]
    stream = io.StringIO()
    writer = csv.writer(stream)
    for index, record in enumerate(candidates):
        writer.writerow(
            [
                index,
                record["address_line"],
                record["city"],
                record["state"],
                record.get("postal_code", ""),
            ]
        )
    if not candidates:
        print("No published physical addresses to geocode.")
        return
    response = requests.post(
        ENDPOINT,
        data={"benchmark": "Public_AR_Current"},
        files={"addressFile": ("peer-addresses.csv", stream.getvalue(), "text/csv")},
        timeout=240,
    )
    response.raise_for_status()
    matches = []
    held = []
    for row in csv.reader(io.StringIO(response.text)):
        if len(row) < 3 or not row[0].isdigit():
            raise ValueError("Unexpected Census geocoding response")
        record = candidates[int(row[0])]
        if (
            len(row) < 8
            or row[2] != "Match"
            or row[3] != "Exact"
            or not re.search(r",\s*" + record["state"] + r"\s*,", row[4])
        ):
            held.append({"state": record["state"], "name": record["name"], "result": row[2:5]})
            continue
        longitude, latitude = map(float, row[5].split(","))
        matches.append(
            {
                "state": record["state"],
                "name": record["name"],
                "address_line": record["address_line"],
                "city": record["city"],
                "postal_code": record.get("postal_code", ""),
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
                "matched_address": row[4],
                "match_type": row[3],
            }
        )
    output = {
        "retrieved": "2026-11-17",
        "source": DOCUMENTATION,
        "endpoint": ENDPOINT,
        "benchmark": "Public_AR_Current",
        "note": "Address-range interpolation, not surveyed facility coordinates. "
        "Exact denotes the address match, not positional accuracy.",
        "matches": matches,
        "held": held,
    }
    (ROOT / "data/multistate/address_geocodes.json").write_text(json.dumps(output, indent=2) + "\n")
    print(
        f"Accepted {len(matches)} address matches; held {len(held)} non-exact/unmatched addresses."
    )


if __name__ == "__main__":
    build()
