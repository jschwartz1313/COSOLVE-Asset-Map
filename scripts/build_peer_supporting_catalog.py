#!/usr/bin/env python3
"""Build bounded supporting inventories from traceable federal facility/program records."""

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "tmp/peer-expansion-20261118"
OUTPUT = ROOT / "data/multistate/supporting_federal_2026_11_18_starter.json"
DATE = "2026-11-18"
TARGETS = {
    "AZ": 350,
    "CA": 500,
    "CO": 350,
    "FL": 450,
    "MI": 400,
    "NY": 450,
    "NC": 350,
    "ND": 300,
    "OH": 400,
    "OK": 300,
    "PA": 400,
    "TX": 500,
    "UT": 300,
}
AIRPORT_LAYER = (
    "https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/"
    "NTAD_Aviation_Facilities/FeatureServer/0"
)
NCES_DIRECTORY = "https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip"
NCES_PROGRAMS = "https://nces.ed.gov/ipeds/datacenter/data/C2024_A.zip"
NCES_CHARACTERISTICS = "https://nces.ed.gov/ipeds/datacenter/data/IC2024.zip"
NCES_DATA_PAGE = "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year=2024"
AIRPORT_FIELDS = (
    "OBJECTID,EFF_DATE,SITE_NO,STATE_CODE,ARPT_ID,CITY,ARPT_NAME,OWNERSHIP_TYPE_CODE,"
    "FACILITY_USE_CODE,LAT_DECIMAL,LONG_DECIMAL,ACREAGE,NASP_CODE,ARPT_STATUS,"
    "TWR_TYPE_CODE,FUEL_TYPES,JOINT_USE_FLAG,LNDG_FEE_FLAG,ICAO_ID,ARPT_PSN_SOURCE"
)


def identity(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"\b(main campus|the)\b", " ", value, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def host(url):
    return (urlsplit(url if "://" in url else "https://" + url).hostname or "").removeprefix("www.")


def official_url(value):
    value = value.strip()
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlsplit(value)
    return (
        value
        if (
            parsed.hostname
            and "." in parsed.hostname
            and " " not in value
            and not parsed.username
            and not parsed.password
        )
        else ""
    )


def existing_records():
    records = []
    for path in sorted((ROOT / "data/multistate").glob("*_starter.json")):
        if path != OUTPUT:
            records.extend(json.loads(path.read_text())["records"])
    return records


def airport_data(refresh=False):
    path = CACHE / "faa_public_airports.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    where = (
        "STATE_CODE IN (" + ",".join(f"'{s}'" for s in TARGETS) + ") "
        "AND FACILITY_USE_CODE='PU' AND SITE_TYPE_CODE='A' AND ARPT_STATUS='O'"
    )
    records = []
    offset = 0
    while True:
        response = requests.get(
            AIRPORT_LAYER + "/query",
            params={
                "f": "json",
                "where": where,
                "outFields": AIRPORT_FIELDS,
                "returnGeometry": "false",
                "orderByFields": "OBJECTID ASC",
                "resultOffset": offset,
                "resultRecordCount": 1000,
            },
            timeout=90,
        )
        response.raise_for_status()
        document = response.json()
        if "error" in document or "features" not in document:
            raise ValueError(f"FAA query failed: {document}")
        rows = [feature["attributes"] for feature in document["features"]]
        records.extend(rows)
        if not document.get("exceededTransferLimit"):
            break
        if not rows:
            raise ValueError("FAA pagination returned an empty incomplete page")
        offset += len(rows)
    ids = [r["SITE_NO"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("FAA dataset repeats facility identities")
    path.write_text(json.dumps(records, indent=2) + "\n")
    return records


def base_record(state, name, kind):
    return {
        "state": state,
        "name": name,
        "record_type": kind,
        "city": "",
        "address_line": "",
        "postal_code": "",
        "latitude": None,
        "longitude": None,
        "location_precision": "site",
        "location_role": "",
        "location_source_url": "",
        "website_url": "",
        "contact_url": "",
        "contact_email": "",
        "contact_phone": "",
        "test_access": "",
        "strategic_categories": ["Supporting ecosystem asset"],
        "platform_domains": [],
        "capabilities": [],
        "missions": [],
        "sources": [],
    }


def airport_records(existing, held, refresh=False):
    existing_airports = [r for r in existing if r.get("record_type") == "infrastructure"]
    websites_path = ROOT / "data/multistate/airport_websites_2026_11_18.json"
    websites = {
        (r["state"], r["faa_id"]): r
        for r in (
            json.loads(websites_path.read_text())["records"] if websites_path.exists() else []
        )
    }
    records = []
    for row in airport_data(refresh):
        state, code = row["STATE_CODE"], row["ARPT_ID"]
        raw_name = row["ARPT_NAME"].strip()
        city = row["CITY"].strip().title()
        known = next(
            (
                r
                for r in existing_airports
                if r["state"] == state
                and (
                    identity(r["name"]).removesuffix("airport")
                    == identity(raw_name).removesuffix("airport")
                    or (
                        re.search(r"\b" + re.escape(code) + r"\b", json.dumps(r), flags=re.I)
                        and "airport" in r["name"].casefold()
                    )
                )
            ),
            None,
        )
        if known:
            held.append(
                {
                    "state": state,
                    "name": raw_name,
                    "reason": f"Existing airport identity: {known['name']} ({code})",
                }
            )
            continue
        name = raw_name.title()
        for abbreviation, expanded in {
            "Intl": "International",
            "Muni": "Municipal",
            "Rgnl": "Regional",
            "Meml": "Memorial",
            "Arpt": "Airport",
        }.items():
            name = re.sub(r"\b" + abbreviation + r"\b", expanded, name)
        if not re.search(r"\b(airport|airfield|aerodrome|airpark|air park)\b", name, flags=re.I):
            name += " Airport"
        source_url = (
            AIRPORT_LAYER
            + "/query?"
            + urlencode(
                {
                    "where": f"SITE_NO='{row['SITE_NO']}'",
                    "outFields": AIRPORT_FIELDS,
                    "returnGeometry": "false",
                    "f": "pjson",
                }
            )
        )
        record = base_record(state, name, "infrastructure")
        record.update(
            city=city,
            latitude=round(row["LAT_DECIMAL"], 6),
            longitude=round(row["LONG_DECIMAL"], 6),
            location_role="airport",
            location_source_url=source_url,
            location_notes="Published FAA airport reference point, not a runway threshold, "
            "entrance or approved drone operating area.",
            short_description=f"Operational public-use airport serving {city}, {state} "
            f"(FAA {code}); supporting aviation infrastructure, not a "
            "confirmed UAS test site.",
            overview=f"FAA/BTS lists {name} as an operational public-use airport serving "
            f"{city}, {state}, under identifier {code}. "
            + (
                f"The listed total airport area is {row['ACREAGE']:,} acres; this is "
                "not available testing or development acreage. "
                if row.get("ACREAGE")
                else ""
            )
            + (
                f"Listed fuels: {row['FUEL_TYPES'].strip()}; confirm availability "
                "with the operator. "
                if row.get("FUEL_TYPES", "").strip()
                else ""
            )
            + "Use this record to locate aviation infrastructure and prepare an "
            "operator inquiry. Runway suitability, charging, UAS acceptance and "
            "current availability have not been established by this inventory.",
            unmanned_systems_relevance="Supporting aviation infrastructure for ecosystem and "
            "logistics planning. Public-use airport status is not permission to conduct "
            "UAS or AAM operations and does not establish an available test range.",
            test_access="Public-use classification only. UAS activity requires airport/operator "
            "coordination and applicable FAA authorization; do not assume site acceptance.",
            strategic_categories=[
                "Physical infrastructure and logistics",
                "Supporting ecosystem asset",
            ],
            platform_domains=["Unmanned aircraft systems"],
            sources=[
                {
                    "title": f"FAA/BTS public-use airport record: {raw_name} ({code})",
                    "url": source_url,
                    "supports": "Facility identity, public-use and "
                    "operational status, served city, airport reference position and any "
                    "listed acreage/fuels in the 2026-10-29 NASR snapshot.",
                }
            ],
            research_notes="Internal research preview. FAA/BTS snapshot effective "
            f"{row['EFF_DATE']}; reviewed as a federal dataset, not an operator/site review. "
            "No flight approval, UAS operating boundary or current fuel availability implied. "
            "A direct airport website/contact is blank unless independently sourced.",
            external_identifiers={"faa_site_no": row["SITE_NO"], "faa_lid": code},
            search_aliases="; ".join(filter(None, [f"FAA {code}", row.get("ICAO_ID", "")])),
            selection_priority=(100 if row.get("NASP_CODE") else 0)
            + (30 if row.get("OWNERSHIP_TYPE_CODE") == "PU" else 0)
            + min(int(row.get("ACREAGE") or 0), 5000) / 1000,
        )
        direct = websites.get((state, code))
        if direct:
            record["website_url"] = direct["website_url"]
            record["contact_url"] = direct["website_url"]
            record["sources"].append(
                {
                    "title": f"Official airport information: {name}",
                    "url": direct["source_url"],
                    "supports": direct["validation_note"],
                }
            )
        records.append(record)
    repeated = Counter((r["state"], r["name"].casefold()) for r in records)
    for record in records:
        if repeated[(record["state"], record["name"].casefold())] > 1:
            record["name"] += f" ({record['external_identifiers']['faa_lid']})"
    return records


def csv_rows(path):
    archive = zipfile.ZipFile(path)
    member = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
    return csv.DictReader(io.TextIOWrapper(archive.open(member), encoding="utf-8-sig"))


def ensure_nces_sources(refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    for filename, url in (
        ("hd2024.zip", NCES_DIRECTORY),
        ("c2024_a.zip", NCES_PROGRAMS),
        ("ic2024.zip", NCES_CHARACTERISTICS),
    ):
        path = CACHE / filename
        if path.exists() and not refresh:
            continue
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        member = next(name for name in archive.namelist() if name.casefold().endswith(".csv"))
        with archive.open(member) as stream:
            if "UNITID" not in stream.readline().decode("utf-8-sig"):
                raise ValueError(f"Unexpected NCES directory schema: {filename}")
        path.write_bytes(response.content)


def program_group(code):
    if code.endswith(".0000"):
        return ""
    if code.startswith(("11.01", "11.07")):
        return "computing"
    if code.startswith("14."):
        return "engineering"
    if code.startswith("15."):
        return "engineering technologies"
    if code.startswith("48.05"):
        return "precision metalworking"
    if code in {"47.0607", "47.0608", "47.0609"}:
        return "aviation maintenance"
    if code.startswith("49.01") and code not in {"49.0106"}:
        return "aviation"
    return ""


def institution_records(existing, held):
    programs = defaultdict(Counter)
    codes = defaultdict(set)
    for row in csv_rows(CACHE / "c2024_a.zip"):
        group = program_group(row["CIPCODE"])
        awards = int(row["CTOTALT"] or 0)
        if group and awards > 0 and row["MAJORNUM"] == "1":
            programs[row["UNITID"]][group] += awards
            codes[row["UNITID"]].add(row["CIPCODE"])
    records = []
    online_only = {
        row["UNITID"] for row in csv_rows(CACHE / "ic2024.zip") if row["DISTNCED"] == "1"
    }
    existing_universities = [r for r in existing if r.get("record_type") == "university"]
    overrides = json.loads(
        (ROOT / "data/multistate/institution_source_overrides_2026_11_18.json").read_text()
    )["institutions"]
    directory = list(csv_rows(CACHE / "hd2024.zip"))
    directory.sort(key=lambda r: -sum(programs[r["UNITID"]].values()))
    represented = set()
    name_counts = Counter(
        (r["STABBR"], r["INSTNM"].strip()) for r in directory if r["UNITID"] in programs
    )
    for row in directory:
        state, unitid = row["STABBR"], row["UNITID"]
        if state not in TARGETS or unitid not in programs:
            continue
        if row["ACT"] != "A" or row["CYACTIVE"] != "1" or sum(programs[unitid].values()) < 10:
            continue
        name, city = row["INSTNM"].strip(), row["CITY"].strip()
        if unitid in online_only:
            held.append(
                {
                    "state": state,
                    "name": name,
                    "reason": "NCES identifies exclusively distance education; "
                    "do not depict as an on-site technical campus.",
                }
            )
            continue
        override = overrides.get(unitid, {})
        if override.get("hold"):
            held.append(
                {
                    "state": state,
                    "name": name,
                    "reason": override["reason"],
                    "source_url": override["source_url"],
                }
            )
            continue
        website = override.get("website_url") or official_url(row["WEBADDR"])
        aliases = [name, *re.split(r"[|;]", row.get("IALIAS", ""))]
        known = next(
            (
                r
                for r in existing_universities
                if r["state"] == state
                and (
                    identity(r["name"]) in {identity(alias) for alias in aliases if alias.strip()}
                    or (
                        host(r.get("website_url", "")) == host(website)
                        and website
                        and identity(r.get("city", "")) == identity(city)
                    )
                )
            ),
            None,
        )
        if known:
            held.append(
                {
                    "state": state,
                    "name": name,
                    "reason": f"Existing institution: {known['name']} (NCES {unitid})",
                }
            )
            continue
        if not website:
            held.append({"state": state, "name": name, "reason": "No valid direct institution URL"})
            continue
        campus = (state, host(website), identity(city))
        if campus in represented:
            held.append(
                {
                    "state": state,
                    "name": name,
                    "reason": "An NCES reporting campus with the same institution website "
                    "and city is already represented; avoid duplicate pins.",
                }
            )
            continue
        represented.add(campus)
        if name_counts[(state, name)] > 1:
            name += f" - {city} campus"
        groups = sorted(programs[unitid])
        group_text = ", ".join(groups)
        source_url = f"https://nces.ed.gov/collegenavigator/?q=&id={unitid}"
        record = base_record(state, name, "university")
        record.update(
            city=city,
            address_line=row["ADDR"].strip(),
            postal_code=row["ZIP"].strip(),
            latitude=round(float(row["LATITUDE"]), 6),
            longitude=round(float(row["LONGITUD"]), 6),
            location_role="campus",
            location_source_url=NCES_DIRECTORY,
            website_url=website,
            contact_url=website,
            contact_phone=row.get("GENTELE", "").strip(),
            location_notes="NCES institutional campus reference point and directory address; "
            "not a specific robotics laboratory, entrance or test area.",
            short_description=f"{city} education provider with NCES-reported qualifications in "
            f"{group_text}; a supporting technical-workforce resource.",
            overview=f"NCES IPEDS identifies {name} in {city}, {state} (institution {unitid}). "
            f"The 2023-24 file reports degree/certificate completions in {group_text}. "
            "This supports a documented technical-education pipeline; it does not "
            "establish a dedicated autonomy program, laboratory equipment or available "
            "testing capacity. Ask the institution about current courses, graduate "
            "skills and employer partnerships before making workforce decisions.",
            unmanned_systems_relevance="Supporting workforce resource based on documented "
            f"{group_text} education. UxS-specific programs, equipment, capacity and "
            "industry access have not been confirmed for this institution-level record.",
            strategic_categories=["Workforce and talent", "Supporting ecosystem asset"],
            sources=[
                {
                    "title": f"NCES institution record: {name}",
                    "url": source_url,
                    "supports": f"Institution identity and UNITID {unitid}; institution-specific "
                    "federal directory reference, not the school's own website.",
                },
                {
                    "title": "NCES IPEDS 2024 institutional directory",
                    "url": NCES_DIRECTORY,
                    "supports": f"UNITID {unitid}: institution name, directory status, address, "
                    "campus reference coordinates, website and general phone.",
                },
                {
                    "title": "NCES IPEDS 2023-24 program completions",
                    "url": NCES_PROGRAMS,
                    "supports": f"UNITID {unitid}: positive first-major completions in CIP codes "
                    + ", ".join(sorted(codes[unitid]))
                    + ". Education evidence is dated "
                    "2023-24, not confirmation of current UxS program availability.",
                },
            ],
            research_notes="Internal preview, not editorially reviewed. Directory vintage2024; "
            "reported program activity July2023-June2024. These are qualifications, not a count "
            "of current students, jobs or available graduates. Whole-institution record; "
            "no UxS laboratory or test access is inferred. "
            "Current website screening is separate.",
            external_identifiers={"nces_unitid": unitid},
            search_aliases="; ".join(alias.strip() for alias in aliases[1:] if alias.strip()),
            selection_priority=len(groups) * 100 + min(sum(programs[unitid].values()), 10000) / 100,
        )
        if len(record["short_description"]) > 320:
            record["short_description"] = (
                f"{city} technical-workforce education provider with NCES-reported "
                "engineering, computing, manufacturing or aviation-related qualifications."
            )
        if override.get("source_url"):
            record["sources"].append(
                {
                    "title": "Current official institution information",
                    "url": override["source_url"],
                    "supports": override["supports"],
                }
            )
        records.append(record)
    return records


def build(refresh=False, output=OUTPUT):
    CACHE.mkdir(parents=True, exist_ok=True)
    ensure_nces_sources(refresh)
    existing = existing_records()
    held = []
    airports = airport_records(existing, held, refresh)
    institutions = institution_records(existing, held)
    screen = CACHE / "institution_website_checks.json"
    checks = json.loads(screen.read_text()) if screen.exists() else {}
    selected = []
    counts = Counter(r["state"] for r in existing)
    for state, target in TARGETS.items():
        airport_pool = sorted(
            (r for r in airports if r["state"] == state),
            key=lambda r: (-r["selection_priority"], r["name"]),
        )
        school_pool = []
        for record in institutions:
            if record["state"] != state:
                continue
            check = checks.get(record["website_url"], {})
            if check.get("hold"):
                held.append(
                    {
                        "state": state,
                        "name": record["name"],
                        "reason": check["reason"],
                        "url": record["website_url"],
                    }
                )
            else:
                if check:
                    record["research_notes"] += (
                        f" Published homepage screening {check.get('checked')}: "
                        f"{check.get('result')}; HTTP {check.get('http_status', 'unknown')}. "
                        "HTTP availability is not editorial verification."
                    )
                school_pool.append(record)
        school_pool.sort(key=lambda r: (-r["selection_priority"], r["name"]))
        pools = [airport_pool, school_pool]
        position = 0
        while counts[state] < target and any(pools):
            pool = pools[position % 2]
            position += 1
            if not pool:
                continue
            record = pool.pop(0)
            record.pop("selection_priority", None)
            selected.append(record)
            counts[state] += 1
    document = {
        "research_date": DATE,
        "states": list(TARGETS),
        "records": selected,
        "held_candidates": held,
    }
    output.write_text(json.dumps(document, indent=2) + "\n")
    combined = [*existing, *selected]
    provenance = {
        "retrieved": DATE,
        "targets_not_rankings": TARGETS,
        "dataset_note": "Supporting infrastructure/workforce only; no UAS activity inferred.",
        "airport_source": AIRPORT_LAYER,
        "ipeds_directory": NCES_DIRECTORY,
        "ipeds_programs": NCES_PROGRAMS,
        "ipeds_characteristics": NCES_CHARACTERISTICS,
        "ipeds_documentation": NCES_DATA_PAGE,
        "source_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                CACHE / "hd2024.zip",
                CACHE / "c2024_a.zip",
                CACHE / "ic2024.zip",
                CACHE / "faa_public_airports.json",
            )
        },
        "supporting_added": dict(Counter(r["state"] for r in selected)),
        "combined_inventory": dict(counts),
        "combined_types": dict(Counter(r["record_type"] for r in combined)),
        "core_records": sum(
            "Core unmanned-systems asset" in r.get("strategic_categories", []) for r in combined
        ),
        "supporting_records": sum(
            "Supporting ecosystem asset" in r.get("strategic_categories", []) for r in combined
        ),
        "claim_level_source_references": sum(len(r.get("sources", [])) for r in combined),
        "visibility": "Staff preview only; no editorial verification or public release implied.",
        "held_count": len(held),
    }
    output.with_name(output.stem + "_manifest.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )
    print(json.dumps(provenance["combined_inventory"], sort_keys=True))
    print(f"Built {len(selected)} supporting records; held {len(held)} uncertain/existing entries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    build(refresh=arguments.refresh, output=arguments.output)
