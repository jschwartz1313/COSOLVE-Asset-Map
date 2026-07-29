#!/usr/bin/env python3
"""Build planning-candidate MPZ tracts from documented Virginia maritime facilities."""

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "static" / "data" / "virginia-maritime-prosperity-candidates.geojson"
TRACT_QUERY_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/"
    "Census2020/Tracts_Blocks/MapServer/0/query"
)

SOURCES = {
    "marad": {
        "label": "MARAD 2025 Shipbuilding and Repair Facilities Survey",
        "url": "https://www.maritime.dot.gov/US_Shipbuilding_Facilities_2025",
    },
    "navy": {
        "label": "U.S. Navy Norfolk Naval Shipyard",
        "url": "https://www.navsea.navy.mil/Home/Shipyards/Norfolk/",
    },
    "port": {
        "label": "Port of Virginia terminal information",
        "url": "https://operations.portofvirginia.com/terminal-directions/",
    },
}

FACILITIES = (
    {
        "name": "BAE Systems Norfolk Ship Repair",
        "type": "Shipyard",
        "longitude": -76.285603,
        "latitude": 36.833310,
        "source": "marad",
    },
    {
        "name": "Colonna's Shipyard",
        "type": "Shipyard",
        "longitude": -76.276656,
        "latitude": 36.834317,
        "source": "marad",
    },
    {
        "name": "Craney Island Marine Terminal Project",
        "type": "Marine terminal project",
        "longitude": -76.359388,
        "latitude": 36.892370,
        "source": "port",
    },
    {
        "name": "East Coast Repair & Fabrication",
        "type": "Ship repair facility",
        "longitude": -76.297959,
        "latitude": 36.836142,
        "source": "marad",
    },
    {
        "name": "General Dynamics NASSCO-Norfolk, Harper Avenue Yard",
        "type": "Shipyard",
        "longitude": -76.316275,
        "latitude": 36.852594,
        "source": "marad",
    },
    {
        "name": "General Dynamics NASSCO-Norfolk, Ligon Street Yard",
        "type": "Shipyard",
        "longitude": -76.290181,
        "latitude": 36.835669,
        "source": "marad",
    },
    {
        "name": "Lyon Shipyard",
        "type": "Shipyard",
        "longitude": -76.271895,
        "latitude": 36.842471,
        "source": "marad",
    },
    {
        "name": "MHI Ship Repair and Services",
        "type": "Ship repair facility",
        "longitude": -76.234532,
        "latitude": 36.867400,
        "source": "marad",
    },
    {
        "name": "Newport News Marine Terminal",
        "type": "Marine terminal",
        "longitude": -76.434700,
        "latitude": 36.985800,
        "source": "port",
    },
    {
        "name": "Newport News Shipbuilding",
        "type": "Shipyard",
        "longitude": -76.435738,
        "latitude": 36.986329,
        "source": "marad",
    },
    {
        "name": "Norfolk International Terminals",
        "type": "Marine terminal",
        "longitude": -76.308572,
        "latitude": 36.915927,
        "source": "port",
    },
    {
        "name": "Norfolk Naval Shipyard",
        "type": "Naval shipyard",
        "longitude": -76.297312,
        "latitude": 36.819272,
        "source": "navy",
    },
    {
        "name": "Portsmouth Marine Terminal",
        "type": "Marine terminal",
        "longitude": -76.324844,
        "latitude": 36.854497,
        "source": "port",
    },
    {
        "name": "Richmond Marine Terminal",
        "type": "Marine terminal",
        "longitude": -77.423308,
        "latitude": 37.457840,
        "source": "port",
    },
    {
        "name": "Virginia International Gateway",
        "type": "Marine terminal",
        "longitude": -76.358894,
        "latitude": 36.872573,
        "source": "port",
    },
)


def request_json(params):
    request = Request(
        f"{TRACT_QUERY_URL}?{urlencode(params)}",
        headers={"Accept": "application/json", "User-Agent": "COSOLVE-Asset-Map/1.0"},
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310
        return json.load(response)


def tract_for_facility(facility):
    data = request_json(
        {
            "geometry": f"{facility['longitude']},{facility['latitude']}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "GEOID,NAME",
            "returnGeometry": "false",
            "f": "json",
        }
    )
    features = data.get("features", [])
    if len(features) != 1:
        raise ValueError(f"Expected one Census tract for {facility['name']}; found {len(features)}")
    return features[0]["attributes"]["GEOID"]


def build():
    facilities_by_tract = {}
    for facility in FACILITIES:
        geoid = tract_for_facility(facility)
        facilities_by_tract.setdefault(geoid, []).append(facility)

    geoids = sorted(facilities_by_tract)
    where = "GEOID IN (" + ",".join(f"'{geoid}'" for geoid in geoids) + ")"
    tracts = request_json(
        {
            "where": where,
            "outFields": "GEOID,NAME,BASENAME,STATE,COUNTY,TRACT",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
    )
    if len(tracts.get("features", [])) != len(geoids):
        raise ValueError("Census tract geometry response did not match the requested candidates")

    for feature in tracts["features"]:
        geoid = feature["properties"]["GEOID"]
        facilities = sorted(facilities_by_tract[geoid], key=lambda item: item["name"])
        source_ids = sorted({facility["source"] for facility in facilities})
        feature["properties"] = {
            "geoid": geoid,
            "tract_name": feature["properties"]["NAME"],
            "designation_status": "Planning candidate only; not federally designated",
            "candidate_basis": (
                "Contains a documented shipyard, ship-repair facility, marine terminal, "
                "or terminal project matching proposed Maritime Prosperity Zone screening concepts."
            ),
            "facility_count": len(facilities),
            "facilities": [
                {"name": facility["name"], "type": facility["type"]} for facility in facilities
            ],
            "sources": [SOURCES[source_id] for source_id in source_ids],
        }

    tracts["name"] = "Virginia potential Maritime Prosperity Zone tracts"
    tracts["description"] = (
        "Illustrative planning candidates based on documented maritime facilities and 2020 Census "
        "tracts. No Virginia tract in this file is represented as federally designated."
    )
    tracts["methodology"] = (
        "Candidate screening follows the tract-based shipyard, port, and harbor-facility concept "
        "in proposed federal Maritime Prosperity Zone policy. It is not an eligibility finding."
    )
    tracts["boundary_source"] = {
        "label": "U.S. Census Bureau TIGERweb, 2020 Census tracts",
        "url": (
            "https://tigerweb.geo.census.gov/arcgis/rest/services/"
            "Census2020/Tracts_Blocks/MapServer"
        ),
    }
    tracts["policy_sources"] = [
        {
            "label": "America's Maritime Action Plan (2026)",
            "url": (
                "https://www.whitehouse.gov/wp-content/uploads/2026/02/"
                "Restoring-Americas-Maritime-Dominance.pdf"
            ),
        },
        {
            "label": "SHIPS for America Act of 2025, Section 710 (introduced legislation)",
            "url": "https://www.congress.gov/bill/119th-congress/house-bill/3151/text",
        },
    ]
    tracts["features"].sort(key=lambda feature: feature["properties"]["geoid"])
    OUTPUT_PATH.write_text(json.dumps(tracts, separators=(",", ":")) + "\n")
    print(f"Wrote {len(tracts['features'])} candidate tracts to {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
