#!/usr/bin/env python3
"""Check peer inventory source fields, stable identities and geographic consistency."""

import argparse
import ipaddress
import json
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit

from django.contrib.gis.geos import GEOSGeometry, Point
from django.utils.text import slugify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.assets.geography import BY_CODE  # noqa: E402


def public_url(value):
    if not value:
        return True
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").casefold().removeprefix("www.")
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password:
        return False
    if hostname in {"localhost", "example.com", "example.org", "example.net"}:
        return False
    if hostname.endswith((".localhost", ".invalid", ".test", ".example", ".local")):
        return False
    try:
        return ipaddress.ip_address(hostname).is_global
    except ValueError:
        return "." in hostname


def audit(paths):
    errors, records = [], []
    identities, external, slugs = {}, {}, {}
    bounds = {}
    for state in BY_CODE.values():
        if state.code == "VA":
            continue
        document = json.loads(
            (ROOT / f"static/data/states/{state.slug}-boundary.geojson").read_text()
        )
        bounds[state.code] = GEOSGeometry(json.dumps(document["features"][0]["geometry"])).buffer(
            0.005
        )
    for path in paths:
        document = json.loads(path.read_text())
        for record in document["records"]:
            name, state = record["name"], record["state"]
            label = f"{state}: {name}"
            key = (state, name.strip().casefold())
            if key in identities:
                errors.append(f"Repeated identity {label}: {identities[key]} and {path.name}")
            identities[key] = path.name
            slug = slugify(f"{state}-{name}")[:240]
            if slug in slugs:
                errors.append(f"Repeated URL slug: {slugs[slug]} and {label}")
            slugs[slug] = label
            if state not in bounds:
                errors.append(f"Unsupported geography: {label}")
            for field in ("website_url", "contact_url", "location_source_url"):
                if not public_url(record.get(field)):
                    errors.append(f"Invalid/nonpublic {field}: {label}")
            if not record.get("sources"):
                errors.append(f"Missing source evidence: {label}")
            for source in record.get("sources", []):
                if (
                    not source.get("supports")
                    or not source.get("url")
                    or not public_url(source["url"])
                ):
                    errors.append(f"Missing/invalid claim-level evidence: {label}")
            latitude, longitude = record.get("latitude"), record.get("longitude")
            if (latitude is None) != (longitude is None):
                errors.append(f"Incomplete coordinates: {label}")
            if latitude is not None and longitude is not None:
                if not record.get("location_source_url"):
                    errors.append(f"Point lacks location source: {label}")
                if not (-90 <= float(latitude) <= 90 and -180 <= float(longitude) <= 180):
                    errors.append(f"Out-of-range coordinates: {label}")
                elif state in bounds and not bounds[state].covers(
                    Point(float(longitude), float(latitude))
                ):
                    errors.append(f"Published point outside listed state: {label}")
            for kind, value in record.get("external_identifiers", {}).items():
                for item in value if isinstance(value, list) else [value]:
                    identity = (kind, str(item))
                    if identity in external:
                        errors.append(f"Repeated {kind} {item}: {external[identity]} and {label}")
                    external[identity] = label
            classification = {
                "Core unmanned-systems asset",
                "Supporting ecosystem asset",
            }.intersection(record.get("strategic_categories", []))
            if len(classification) != 1:
                errors.append(f"Missing or ambiguous core/supporting classification: {label}")
            records.append(record)
    nearby = []
    groups = defaultdict(list)
    for record in records:
        groups[(record["state"], record.get("city", "").strip().casefold())].append(record)
    for group in groups.values():
        for left, right in combinations(group, 2):
            ratio = SequenceMatcher(None, left["name"].casefold(), right["name"].casefold()).ratio()
            if ratio >= 0.87:
                nearby.append(
                    {
                        "state": left["state"],
                        "left": left["name"],
                        "right": right["name"],
                        "name_similarity": round(ratio, 3),
                    }
                )
    return {
        "records": len(records),
        "by_state": dict(Counter(r["state"] for r in records)),
        "source_references": sum(len(r.get("sources", [])) for r in records),
        "published_points": sum(r.get("latitude") is not None for r in records),
        "direct_websites": sum(bool(r.get("website_url")) for r in records),
        "errors": errors,
        "possible_similar_names": nearby,
        "scope": "Automated consistency checks; not editorial/operator verification.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extra", type=Path, action="append", default=[])
    parser.add_argument(
        "--output", type=Path, default=ROOT / "tmp/peer-expansion-20261118/catalog-audit.json"
    )
    args = parser.parse_args()
    paths = sorted((ROOT / "data/multistate").glob("*_starter.json")) + args.extra
    report = audit(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "possible_similar_names"},
            indent=2,
        )
    )
    print(f"Similar-name pairs for review: {len(report['possible_similar_names'])}")
    sys.exit(bool(report["errors"]))
