#!/usr/bin/env python3
"""Build checked-in Virginia drone-airspace and test-facility reference layers."""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "static" / "data"
STATE_BOUNDARY = DATA_DIR / "virginia-state-boundary.geojson"
GENERATED_AT = "2026-08-12"
VIRGINIA_ENVELOPE = "-83.7,36.5,-75.1,39.6"

FAA_ROOT = "https://services6.arcgis.com/ssFJjBXIUyZDrSYZ/arcgis/rest/services"
UASFM_LAYER = f"{FAA_ROOT}/FAA_UAS_FacilityMap_Data/FeatureServer/0"
CLASS_AIRSPACE_LAYER = f"{FAA_ROOT}/Class_Airspace/FeatureServer/0"
SPECIAL_USE_LAYER = f"{FAA_ROOT}/Special_Use_Airspace/FeatureServer/0"
NATIONAL_SECURITY_LAYER = f"{FAA_ROOT}/DoD_Mar_13/FeatureServer/0"

FAA_UASFM_INFO = "https://www.faa.gov/uas/getting_started/laanc"
FAA_AIRSPACE_INFO = (
    "https://www.faa.gov/uas/getting_started/where_can_i_fly/"
    "airspace_restrictions/flying_near_airports"
)
FAA_DATA_INFO = "https://udds-faa.opendata.arcgis.com/"
FAA_SECURITY_INFO = (
    "https://faa.maps.arcgis.com/apps/webappviewer/index.html?"
    "id=9c2e4406710048e19806ebf6a06754ad"
)


TEST_SITES = (
    {
        "name": "MARS UAS Airfield",
        "city": "Wallops Island",
        "longitude": -75.467,
        "latitude": 37.94,
        "location_precision": "Approximate site location",
        "site_type": "Dedicated UAS airfield",
        "published_size": "Direct access to 75 square nautical miles of restricted airspace",
        "launch_recovery": "3,000 ft by 75 ft runway and a vertical takeoff and landing pad",
        "support_infrastructure": (
            "90 ft by 50 ft hangar and UAS integration and airfield management support"
        ),
        "aircraft_scope": (
            "Government and commercial unmanned-aircraft training, testing, "
            "demonstrations, and exercises"
        ),
        "flight_constraints": (
            "Secure federal facility; operations use the NASA Wallops range environment "
            "and require coordination through MARS."
        ),
        "access": "Coordinated customer access; not a public-use airfield",
        "source_title": "Virginia Spaceport Authority facilities",
        "source_url": "https://www.vaspace.org/our-facilities",
    },
    {
        "name": "NASA Langley UAS Test Range and CERTAIN",
        "city": "Hampton",
        "longitude": -76.380667,
        "latitude": 37.085639,
        "location_precision": "NASA Langley campus reference point",
        "site_type": "Open-air research range and urban test environment",
        "published_size": (
            "100-acre designated UAS test range; CERTAIN provides a city-like "
            "research environment"
        ),
        "launch_recovery": "Official sources do not publish runway or launch-pad dimensions",
        "support_infrastructure": (
            "Live small-UAS flight range connected to NASA remote-operations "
            "and autonomy research"
        ),
        "aircraft_scope": "NASA-approved small UAS research operations",
        "flight_constraints": (
            "Flight time is scheduled through NASA's UAS Operations Office; the Air Force "
            "requires advance notification, NASA security is notified, and a NASA range "
            "safety officer must be present."
        ),
        "access": "Coordinated research access; not an open public flying site",
        "source_title": "NASA Langley drone flying site",
        "source_url": "https://www.nasa.gov/centers-and-facilities/langley/nasa-langley-drone-flying-site-open-for-testing/",
        "secondary_source_title": "NASA ROAM and CERTAIN operations",
        "secondary_source_url": "https://csaob.larc.nasa.gov/roam/",
    },
    {
        "name": "Virginia Tech Drone Park",
        "city": "Blacksburg",
        "longitude": -80.4286,
        "latitude": 37.2241,
        "location_precision": "Published facility address",
        "site_type": "Netted flight-test and teaching facility",
        "published_size": "3 million cubic feet in a 300 ft by 120 ft by 85 ft netted enclosure",
        "launch_recovery": (
            "Netted enclosure; the official facility page does not describe a runway"
        ),
        "support_infrastructure": "Adjacent laboratory, classroom, work, and observation space",
        "aircraft_scope": "Drone research, instruction, and controlled flight work",
        "flight_constraints": (
            "The enclosure is not considered part of the National Airspace System. "
            "Orientation and scheduling are required; commercial and third-party "
            "operations have additional requirements."
        ),
        "access": "Scheduled access through Virginia Tech",
        "source_title": "Virginia Tech Drone Park",
        "source_url": "https://ictas.vt.edu/Facilities/ictas-drone-park.html",
    },
)


def request_geojson(layer_url, *, where, out_fields, geometry=None, page_size=2000):
    features = []
    offset = 0
    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "geometryPrecision": "6",
            "resultOffset": str(offset),
            "resultRecordCount": str(page_size),
            "f": "geojson",
        }
        if geometry:
            params.update(
                {
                    "geometry": geometry,
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": "4326",
                    "spatialRel": "esriSpatialRelIntersects",
                }
            )
        request = urllib.request.Request(
            f"{layer_url}/query?{urllib.parse.urlencode(params)}",
            headers={"User-Agent": "cosolve-uxs-map-airspace/1.0"},
        )
        for attempt in range(3):
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                payload = json.load(response)
            error = payload.get("error")
            if not error:
                break
            if error.get("code") == 429 and attempt < 2:
                print("FAA feature service rate limit reached; waiting 65 seconds...")
                time.sleep(65)
                continue
            raise RuntimeError(error)
        page = payload.get("features", [])
        features.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    return features


def state_geometry():
    payload = json.loads(STATE_BOUNDARY.read_text())
    geometry = payload["features"][0]["geometry"]
    return GEOSGeometry(json.dumps(geometry), srid=4326)


def intersects_state(feature, virginia):
    geometry = feature.get("geometry")
    if not geometry:
        return False
    return GEOSGeometry(json.dumps(geometry), srid=4326).intersects(virginia)


def write_layer(
    filename,
    *,
    name,
    description,
    source,
    source_url,
    information_url,
    features,
    disclaimer,
):
    payload = {
        "type": "FeatureCollection",
        "metadata": {
            "name": name,
            "description": description,
            "generated_at": GENERATED_AT,
            "feature_count": len(features),
            "source": source,
            "source_url": source_url,
            "information_url": information_url,
            "disclaimer": disclaimer,
        },
        "features": features,
    }
    output = DATA_DIR / filename
    output.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"Wrote {len(features)} features to {output}")


def build_uas_facility_map():
    virginia = state_geometry()
    raw = request_geojson(
        UASFM_LAYER,
        where="1=1",
        geometry=VIRGINIA_ENVELOPE,
        out_fields=(
            "OBJECTID,CEILING,UNIT,MAP_EFF,LAST_EDIT,LATITUDE,LONGITUDE,"
            "ARPT_COUNT,APT1_FAAID,APT1_ICAO,APT1_NAME,APT1_LAANC,"
            "APT2_FAAID,APT2_ICAO,APT2_NAME,APT2_LAANC,AIRS_COUNT,"
            "AIRSPACE_1,AIRSPACE_2"
        ),
    )
    features = []
    for feature in raw:
        properties = feature["properties"]
        if not intersects_state(feature, virginia):
            continue
        airports = []
        for index in (1, 2):
            name = properties.get(f"APT{index}_NAME")
            if name:
                airports.append(
                    {
                        "name": name,
                        "faa_id": properties.get(f"APT{index}_FAAID") or "",
                        "icao_id": properties.get(f"APT{index}_ICAO") or "",
                        "laanc_enabled": properties.get(f"APT{index}_LAANC") == 1,
                    }
                )
        features.append(
            {
                "type": "Feature",
                "id": properties["OBJECTID"],
                "geometry": feature["geometry"],
                "properties": {
                    "ceiling_agl_ft": properties.get("CEILING"),
                    "map_effective": properties.get("MAP_EFF") or "",
                    "last_edit": properties.get("LAST_EDIT") or "",
                    "airspace_classes": [
                        value
                        for value in (properties.get("AIRSPACE_1"), properties.get("AIRSPACE_2"))
                        if value
                    ],
                    "airports": airports,
                },
            }
        )
    features.sort(key=lambda feature: feature["id"])
    write_layer(
        "virginia-uas-facility-map.geojson",
        name="Virginia FAA UAS Facility Map authorization ceilings",
        description=(
            "FAA grid values used to evaluate Part 107 controlled-airspace "
            "authorization requests."
        ),
        source="FAA UAS Facility Map Data",
        source_url=UASFM_LAYER,
        information_url=FAA_UASFM_INFO,
        features=features,
        disclaimer=(
            "A grid value is not flight authorization and is not a general legal altitude limit. "
            "Operators must obtain required FAA authorization and check current restrictions."
        ),
    )


def build_surface_controlled_airspace():
    virginia = state_geometry()
    raw = request_geojson(
        CLASS_AIRSPACE_LAYER,
        where="LOWER_VAL=0 AND CLASS IN ('B','C','D','E')",
        geometry=VIRGINIA_ENVELOPE,
        out_fields=(
            "OBJECTID,IDENT,ICAO_ID,NAME,CLASS,LOWER_VAL,LOWER_UOM,LOWER_CODE,"
            "UPPER_VAL,UPPER_UOM,UPPER_CODE,TYPE_CODE,LOCAL_TYPE,WKHR_RMK"
        ),
    )
    features = []
    for feature in raw:
        if not intersects_state(feature, virginia):
            continue
        properties = feature["properties"]
        features.append(
            {
                "type": "Feature",
                "id": properties["OBJECTID"],
                "geometry": feature["geometry"],
                "properties": {
                    "name": properties.get("NAME") or "Controlled airspace",
                    "class": properties.get("CLASS") or "",
                    "identifier": properties.get("ICAO_ID") or properties.get("IDENT") or "",
                    "lower_limit": "Surface",
                    "upper_limit": " ".join(
                        str(value)
                        for value in (
                            properties.get("UPPER_VAL"),
                            properties.get("UPPER_UOM"),
                            properties.get("UPPER_CODE"),
                        )
                        if value not in (None, "")
                    ),
                    "hours_note": properties.get("WKHR_RMK") or "",
                },
            }
        )
    features.sort(key=lambda feature: (feature["properties"]["name"], feature["id"]))
    write_layer(
        "virginia-surface-controlled-airspace.geojson",
        name="Virginia surface controlled airspace",
        description=(
            "FAA Class B, C, D, and surface Class E airspace recorded with a surface floor."
        ),
        source="FAA Class Airspace",
        source_url=CLASS_AIRSPACE_LAYER,
        information_url=FAA_AIRSPACE_INFO,
        features=features,
        disclaimer=(
            "Drone pilots generally need FAA authorization before operating in "
            "controlled airspace. "
            "This static reference does not show current authorization, NOTAM, or TFR status."
        ),
    )


def special_use_category(type_code):
    return {
        "P": "Prohibited area",
        "R": "Restricted area",
        "MOA": "Military operations area",
        "W": "Warning area",
    }.get(type_code, "Special-use airspace")


def vertical_limit(properties, prefix):
    code = properties.get(f"{prefix}_CODE") or ""
    if code == "SFC":
        return "Surface"
    if code == "UNLTD":
        return "Unlimited"
    description = properties.get(f"{prefix}_DESC")
    if description:
        return description
    return " ".join(
        str(value)
        for value in (
            properties.get(f"{prefix}_VAL"),
            properties.get(f"{prefix}_UOM"),
            code,
        )
        if value not in (None, "")
    )


def build_flight_constraints():
    virginia = state_geometry()
    special_use = request_geojson(
        SPECIAL_USE_LAYER,
        where="TYPE_CODE IN ('P','R','MOA','W')",
        geometry=VIRGINIA_ENVELOPE,
        out_fields=(
            "OBJECTID,NAME,TYPE_CODE,CLASS,UPPER_DESC,UPPER_VAL,UPPER_UOM,"
            "UPPER_CODE,LOWER_DESC,LOWER_VAL,LOWER_UOM,LOWER_CODE,TIMESOFUSE,REMARKS"
        ),
    )
    security = request_geojson(
        NATIONAL_SECURITY_LAYER,
        where="State='VA'",
        out_fields=(
            "OBJECTID,Proponent,Branch,Base,Facility,Airspace,Reason,State,FAA_ID,"
            "Floor,Ceiling,County"
        ),
    )
    features = []
    for feature in special_use:
        if not intersects_state(feature, virginia):
            continue
        properties = feature["properties"]
        type_code = properties.get("TYPE_CODE") or ""
        features.append(
            {
                "type": "Feature",
                "id": f"sua-{properties['OBJECTID']}",
                "geometry": feature["geometry"],
                "properties": {
                    "constraint_type": "special-use",
                    "category": special_use_category(type_code),
                    "type_code": type_code,
                    "name": properties.get("NAME") or special_use_category(type_code),
                    "floor": vertical_limit(properties, "LOWER")
                    or "See current FAA data",
                    "ceiling": vertical_limit(properties, "UPPER")
                    or "See current FAA data",
                    "times_of_use": properties.get("TIMESOFUSE")
                    or "See current FAA data and NOTAMs",
                    "remarks": properties.get("REMARKS") or "",
                },
            }
        )
    for feature in security:
        properties = feature["properties"]
        name = properties.get("Facility") or properties.get("Base") or "Protected facility"
        features.append(
            {
                "type": "Feature",
                "id": f"security-{properties['OBJECTID']}",
                "geometry": feature["geometry"],
                "properties": {
                    "constraint_type": "national-security-uas",
                    "category": "National-security UAS flight restriction",
                    "type_code": "UAS NSFR",
                    "name": name.strip(),
                    "base": (properties.get("Base") or "").strip(),
                    "branch": (properties.get("Branch") or "").strip(),
                    "county": (properties.get("County") or "").strip(),
                    "floor": properties.get("Floor") or "Surface",
                    "ceiling": properties.get("Ceiling") or "400 ft AGL",
                    "times_of_use": "Continuous unless the controlling FAA notice states otherwise",
                    "remarks": (
                        "FAA restrictions apply to all UAS purposes unless an authorized "
                        "exception applies."
                    ),
                },
            }
        )
    features.sort(
        key=lambda feature: (
            feature["properties"]["constraint_type"],
            feature["properties"]["name"],
            feature["id"],
        )
    )
    write_layer(
        "virginia-flight-constraints.geojson",
        name="Virginia FAA UAS and special-use flight constraints",
        description=(
            "FAA national-security UAS restrictions and selected special-use airspace "
            "intersecting Virginia."
        ),
        source="FAA Aeronautical Information Services",
        source_url=SPECIAL_USE_LAYER,
        information_url=FAA_SECURITY_INFO,
        features=features,
        disclaimer=(
            "Constraint types have different legal effects and schedules. This layer is "
            "not real-time; "
            "operators must consult current FAA notices, NOTAMs, and authorizations before flight."
        ),
    )


def build_test_sites():
    features = []
    for index, site in enumerate(TEST_SITES, start=1):
        properties = dict(site)
        longitude = properties.pop("longitude")
        latitude = properties.pop("latitude")
        features.append(
            {
                "type": "Feature",
                "id": f"test-site-{index}",
                "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                "properties": properties,
            }
        )
    write_layer(
        "virginia-uas-test-sites.geojson",
        name="Virginia UAS test facilities with published specifications",
        description=(
            "Selected Virginia flight facilities with official public dimensions, "
            "infrastructure, or operating constraints."
        ),
        source="Official facility operators",
        source_url=TEST_SITES[0]["source_url"],
        information_url=TEST_SITES[0]["source_url"],
        features=features,
        disclaimer=(
            "Inclusion does not imply availability, access, scheduling approval, "
            "airworthiness approval, "
            "or authorization for a particular aircraft or operation."
        ),
    )


def main():
    build_uas_facility_map()
    build_surface_controlled_airspace()
    build_flight_constraints()
    build_test_sites()


if __name__ == "__main__":
    main()
