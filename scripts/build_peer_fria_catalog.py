#!/usr/bin/env python3
"""Import dated FAA-recognized flying areas without inferring operational permission."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlencode

import requests
from django.contrib.gis.geos import GEOSGeometry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.assets.geography import BY_CODE  # noqa: E402
from scripts.build_peer_supporting_catalog import (  # noqa: E402
    CACHE,
    DATE,
    TARGETS,
    base_record,
    identity,
)

LAYER = (
    "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services/"
    "FAA_Recognized_Identification_Areas/FeatureServer/0"
)
GUIDANCE = "https://www.faa.gov/uas/getting_started/remote_id/fria"
OUTPUT = ROOT / "data/multistate/fria_federal_2026_11_18_starter.json"


def calendar_date(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, timezone.utc).date()
    return date.fromisoformat(value[:10]) if value else None


def is_current(properties, as_of):
    start, end = (calendar_date(properties.get(key)) for key in ("startDate", "endDate"))
    return bool(start and end and start <= as_of < end)


def grouped_sites(features):
    """Keep adjacent/overlapping recognitions at the same named site as one asset."""
    groups = []
    for feature in features:
        row = feature["properties"]
        geometry = GEOSGeometry(json.dumps(feature["geometry"]))
        for group in groups:
            first = group[0]["properties"]
            if row["state"] != first["state"] or row.get("orgName") != first.get("orgName"):
                continue
            same_name = identity(row["title"]) == identity(first["title"])
            same_address = bool(row.get("address1")) and (
                identity(row["address1"]) == identity(first.get("address1") or "")
                and identity(row.get("city") or "") == identity(first.get("city") or "")
            )
            similar = SequenceMatcher(
                None, row["title"].casefold(), first["title"].casefold()
            ).ratio()
            if not same_name and not (same_address and similar >= 0.65):
                continue
            nearby = any(
                geometry.distance(GEOSGeometry(json.dumps(other["geometry"]))) <= 0.002
                for other in group
            )
            if nearby:
                group.append(feature)
                break
        else:
            groups.append([feature])
    return groups


def fetch(refresh=False):
    path = CACHE / "faa_frias.geojson"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    features = []
    offset = 0
    while True:
        response = requests.get(
            LAYER + "/query",
            params={
                "f": "geojson",
                "where": "state IN (" + ",".join(f"'{s}'" for s in TARGETS) + ")",
                "outFields": "*",
                "outSR": 4326,
                "orderByFields": "ObjectId",
                "resultOffset": offset,
                "resultRecordCount": 1000,
            },
            timeout=90,
        )
        response.raise_for_status()
        document = response.json()
        if "error" in document or "features" not in document:
            raise ValueError(f"FAA FRIA request failed: {document}")
        rows = document["features"]
        features.extend(rows)
        if len(rows) < 1000:
            break
        offset += len(rows)
    identifiers = [f["properties"]["refNumber"] for f in features]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("FAA FRIA query repeated identification numbers")
    document = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(document, indent=2) + "\n")
    return document


def build(refresh=False, output=OUTPUT):
    CACHE.mkdir(parents=True, exist_ok=True)
    document = fetch(refresh)
    as_of = date.fromisoformat(DATE)
    existing = []
    for path in (ROOT / "data/multistate").glob("*_starter.json"):
        if path != OUTPUT and "supporting_federal" not in path.name:
            existing.extend(json.loads(path.read_text())["records"])
    records, held = [], []
    boundaries = {}
    for state in TARGETS:
        state_slug = BY_CODE[state].slug
        geojson = json.loads(
            (ROOT / f"static/data/states/{state_slug}-boundary.geojson").read_text()
        )
        boundaries[state] = GEOSGeometry(json.dumps(geojson["features"][0]["geometry"]))
    valid = []
    for feature in document["features"]:
        row = feature["properties"]
        state, reference, title = row["state"], row["refNumber"], (row.get("title") or "").strip()
        if not title or not is_current(row, as_of) or not feature.get("geometry"):
            held.append(
                {
                    "state": state,
                    "name": title or reference,
                    "reason": "Missing geometry/name or outside the published recognition dates.",
                }
            )
            continue
        geometry = GEOSGeometry(json.dumps(feature["geometry"]))
        if not geometry.valid:
            held.append(
                {"state": state, "name": title, "reason": "Invalid published site geometry."}
            )
            continue
        valid.append(feature)
    groups = grouped_sites(valid)
    for group in groups:
        feature = min(
            group, key=lambda f: (len(f["properties"]["title"]), f["properties"]["title"])
        )
        row = feature["properties"]
        state, reference, title = row["state"], row["refNumber"], row["title"].strip()
        members = [f["properties"] for f in group]
        references = [member["refNumber"] for member in members]
        known = next(
            (
                r
                for r in existing
                if r["state"] == state
                and (
                    any(ref in json.dumps(r) for ref in references)
                    or identity(r["name"]) == identity(title)
                )
            ),
            None,
        )
        if known:
            held.append(
                {
                    "state": state,
                    "name": title,
                    "reason": f"Existing flying-area identity: {known['name']}",
                }
            )
            continue
        geometry = GEOSGeometry(json.dumps(feature["geometry"]))
        point = geometry.point_on_surface
        if not boundaries[state].buffer(0.005).covers(point):
            held.append(
                {
                    "state": state,
                    "name": title,
                    "reason": "Published geometry does not agree with the listed state.",
                }
            )
            continue
        name = f"{title} - FAA-recognized flying area"
        source = (
            LAYER
            + "/query?"
            + urlencode(
                {
                    "where": f"refNumber='{reference}'",
                    "outFields": "*",
                    "outSR": 4326,
                    "f": "geojson",
                }
            )
        )
        record = base_record(state, name, "operating-environment")
        city = (row.get("city") or "").strip()
        record.update(
            city=city,
            address_line=" ".join(filter(None, [row.get("address1"), row.get("address2")])),
            postal_code=str(row.get("zipcode") or "").zfill(5) if row.get("zipcode") else "",
            latitude=round(point.y, 6),
            longitude=round(point.x, 6),
            location_source_url=source,
            location_notes="Representative point inside the FAA-published FRIA polygon, not a "
            "surveyed launch point or entrance. The boundary defines the area, not this pin.",
            short_description=f"FAA-recognized drone flying area in {city or state}; "
            "a potential training resource subject to site access and applicable flight rules.",
            overview=f"The FAA lists {title} under recognition {reference}, with "
            f"{row.get('orgName') or 'the listed applicant'} as the sponsoring organization. "
            "This identifies a real flying area that may be useful for visual-line-of-sight "
            "drone/model-aircraft practice and education, where the operator permits the activity. "
            "It is not evidence of commercial testing services, available equipment, launch "
            "facilities, aircraft weight acceptance or counter-UAS capability. "
            "Check the current FAA polygon and contact the site operator before planning a visit.",
            unmanned_systems_relevance="A documented unmanned-aircraft operating area and possible "
            "training resource. FRIA recognition concerns Remote ID requirements within the "
            "designated boundary; it is not a general airspace authorization or BVLOS approval.",
            test_access="Physical access requires the landowner/site operator's permission. "
            "Both pilot and aircraft must remain inside the FRIA and within visual line of sight "
            "for operations relying on its Remote ID provision. Other applicable rules and "
            "airspace permissions still apply. Equipped aircraft must keep broadcasting Remote ID.",
            strategic_categories=[
                "Test and operational environments",
                "Supporting ecosystem asset",
            ],
            platform_domains=["Unmanned aircraft systems"],
            missions=["Training and experimentation"],
            sources=[
                *[
                    {
                        "title": f"FAA FRIA site record: {member['title']}",
                        "url": LAYER
                        + "/query?"
                        + urlencode(
                            {
                                "where": f"refNumber='{member['refNumber']}'",
                                "outFields": "*",
                                "outSR": 4326,
                                "f": "geojson",
                            }
                        ),
                        "supports": f"Published recognition {member['refNumber']}, site name, "
                        "sponsoring organization, address, boundary and recognition dates.",
                    }
                    for member in members
                ],
                {
                    "title": "FAA explanation of recognized identification areas",
                    "url": GUIDANCE,
                    "supports": "The limited purpose of FRIA recognition and the need to comply "
                    "with visual-line-of-sight, boundary, Remote ID and other flight requirements.",
                },
            ],
            external_identifiers={"faa_fria": references},
            search_aliases="; ".join(
                [*(member["title"] for member in members), *references, "FRIA"]
            ),
            research_notes="Internal public-source preview, not an editorial/operator review. "
            f"Recognition {row['startDate']} to {row['endDate']} includes {DATE}. "
            "The point is derived from the published polygon. No site visit, current access "
            "availability, commercial suitability or direct operator contact has been confirmed. "
            "No operator website is substituted with a generic FAA guidance page.",
        )
        if len(group) > 1:
            record["overview"] += (
                f" {len(group)} nearby FAA recognition polygons at this named location are "
                "represented together as one physical flying-area asset, not separate facilities."
            )
        records.append(record)
    repeated = Counter((r["state"], r["name"].casefold()) for r in records)
    for record in records:
        if repeated[(record["state"], record["name"].casefold())] > 1:
            record["name"] += f" ({record['external_identifiers']['faa_fria'][0]})"
    output.write_text(
        json.dumps(
            {
                "research_date": DATE,
                "states": list(TARGETS),
                "records": records,
                "held_candidates": held,
            },
            indent=2,
        )
        + "\n"
    )
    manifest = {
        "retrieved": DATE,
        "source": LAYER,
        "guidance": GUIDANCE,
        "raw_sha256": hashlib.sha256((CACHE / "faa_frias.geojson").read_bytes()).hexdigest(),
        "added": dict(Counter(r["state"] for r in records)),
        "held": len(held),
        "nearby_recognitions_consolidated": len(valid) - len(groups),
        "position_method": "Point on surface of published FAA polygon, not surveyed site entrance.",
    }
    output.with_name(output.stem + "_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    build(refresh=arguments.refresh, output=arguments.output)
