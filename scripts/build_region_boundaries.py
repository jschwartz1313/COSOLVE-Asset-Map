#!/usr/bin/env python3
"""Build display-only ecosystem region polygons from Virginia locality boundaries."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTIES_PATH = ROOT / "static" / "data" / "virginia-counties.geojson"
OUTPUT_PATH = ROOT / "static" / "data" / "virginia-regions.geojson"

REGIONS = (
    {
        "name": "Central Virginia",
        "slug": "central-virginia",
        "color": "#748A35",
        "localities": (
            "Albemarle County",
            "Buckingham County",
            "Charlottesville city",
            "Culpeper County",
            "Cumberland County",
            "Fluvanna County",
            "Greene County",
            "Louisa County",
            "Madison County",
            "Nelson County",
            "Orange County",
            "Prince Edward County",
            "Rappahannock County",
        ),
    },
    {
        "name": "Eastern Shore",
        "slug": "eastern-shore",
        "color": "#3C8F91",
        "localities": ("Accomack County", "Northampton County"),
    },
    {
        "name": "Fredericksburg Region",
        "slug": "fredericksburg-region",
        "color": "#BD713C",
        "localities": (
            "Caroline County",
            "Essex County",
            "Fredericksburg city",
            "King George County",
            "Lancaster County",
            "Northumberland County",
            "Richmond County",
            "Spotsylvania County",
            "Stafford County",
            "Westmoreland County",
        ),
    },
    {
        "name": "Greater Richmond",
        "slug": "greater-richmond",
        "color": "#806682",
        "localities": (
            "Amelia County",
            "Charles City County",
            "Chesterfield County",
            "Colonial Heights city",
            "Dinwiddie County",
            "Goochland County",
            "Hanover County",
            "Henrico County",
            "Hopewell city",
            "King William County",
            "King and Queen County",
            "New Kent County",
            "Petersburg city",
            "Powhatan County",
            "Prince George County",
            "Richmond city",
        ),
    },
    {
        "name": "Hampton Roads",
        "slug": "hampton-roads",
        "color": "#3978A8",
        "localities": (
            "Chesapeake city",
            "Franklin city",
            "Gloucester County",
            "Hampton city",
            "Isle of Wight County",
            "James City County",
            "Mathews County",
            "Middlesex County",
            "Newport News city",
            "Norfolk city",
            "Poquoson city",
            "Portsmouth city",
            "Southampton County",
            "Suffolk city",
            "Surry County",
            "Virginia Beach city",
            "Williamsburg city",
            "York County",
        ),
    },
    {
        "name": "Lynchburg Region",
        "slug": "lynchburg-region",
        "color": "#AE9140",
        "localities": (
            "Amherst County",
            "Appomattox County",
            "Bedford County",
            "Campbell County",
            "Lynchburg city",
        ),
    },
    {
        "name": "New River Valley",
        "slug": "new-river-valley",
        "color": "#6267A2",
        "localities": (
            "Floyd County",
            "Giles County",
            "Montgomery County",
            "Pulaski County",
            "Radford city",
        ),
    },
    {
        "name": "Northern Virginia",
        "slug": "northern-virginia",
        "color": "#A45C55",
        "localities": (
            "Alexandria city",
            "Arlington County",
            "Fairfax County",
            "Fairfax city",
            "Falls Church city",
            "Fauquier County",
            "Loudoun County",
            "Manassas Park city",
            "Manassas city",
            "Prince William County",
        ),
    },
    {
        "name": "Roanoke Valley",
        "slug": "roanoke-valley",
        "color": "#477D5B",
        "localities": (
            "Alleghany County",
            "Botetourt County",
            "Covington city",
            "Craig County",
            "Franklin County",
            "Roanoke County",
            "Roanoke city",
            "Salem city",
        ),
    },
    {
        "name": "Shenandoah Valley",
        "slug": "shenandoah-valley",
        "color": "#746493",
        "localities": (
            "Augusta County",
            "Bath County",
            "Buena Vista city",
            "Clarke County",
            "Frederick County",
            "Harrisonburg city",
            "Highland County",
            "Lexington city",
            "Page County",
            "Rockbridge County",
            "Rockingham County",
            "Shenandoah County",
            "Staunton city",
            "Warren County",
            "Waynesboro city",
            "Winchester city",
        ),
    },
    {
        "name": "Southside Virginia",
        "slug": "southside-virginia",
        "color": "#AA607D",
        "localities": (
            "Brunswick County",
            "Charlotte County",
            "Danville city",
            "Emporia city",
            "Greensville County",
            "Halifax County",
            "Henry County",
            "Lunenburg County",
            "Martinsville city",
            "Mecklenburg County",
            "Nottoway County",
            "Patrick County",
            "Pittsylvania County",
            "Sussex County",
        ),
    },
    {
        "name": "Southwest Virginia",
        "slug": "southwest-virginia",
        "color": "#765B50",
        "localities": (
            "Bland County",
            "Bristol city",
            "Buchanan County",
            "Carroll County",
            "Dickenson County",
            "Galax city",
            "Grayson County",
            "Lee County",
            "Norton city",
            "Russell County",
            "Scott County",
            "Smyth County",
            "Tazewell County",
            "Washington County",
            "Wise County",
            "Wythe County",
        ),
    },
)


def region_lookup():
    lookup = {}
    for region in REGIONS:
        for locality in region["localities"]:
            if locality in lookup:
                raise ValueError(f"{locality} is assigned to more than one region")
            lookup[locality] = region
    return lookup


def build():
    counties = json.loads(COUNTIES_PATH.read_text())
    lookup = region_lookup()
    county_names = {feature["properties"]["NAME"] for feature in counties["features"]}
    missing = sorted(county_names - lookup.keys())
    unknown = sorted(lookup.keys() - county_names)
    if missing or unknown:
        raise ValueError(
            f"Locality assignments do not match the boundary file. Missing: {missing}; "
            f"unknown: {unknown}"
        )

    enriched_features = []
    for feature in counties["features"]:
        locality = feature["properties"]["NAME"]
        region = lookup[locality]
        enriched_features.append(
            {
                "type": "Feature",
                "properties": {
                    "region_name": region["name"],
                    "region_slug": region["slug"],
                    "region_color": region["color"],
                    "locality_name": locality,
                },
                "geometry": feature["geometry"],
            }
        )

    ogr2ogr = shutil.which("ogr2ogr")
    if not ogr2ogr:
        raise RuntimeError("ogr2ogr is required to dissolve locality boundaries by region")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        localities_path = temp_path / "localities.geojson"
        dissolved_path = temp_path / "regions.geojson"
        localities_path.write_text(
            json.dumps({"type": "FeatureCollection", "features": enriched_features})
        )
        subprocess.run(
            [
                ogr2ogr,
                "-f",
                "GeoJSON",
                str(dissolved_path),
                str(localities_path),
                "-dialect",
                "SQLite",
                "-sql",
                (
                    "SELECT region_name, region_slug, region_color, COUNT(*) AS locality_count, "
                    "ST_Union(ST_MakeValid(geometry)) AS geometry "
                    "FROM localities GROUP BY region_name, region_slug, region_color"
                ),
                "-nln",
                "regions",
                "-lco",
                "COORDINATE_PRECISION=5",
            ],
            check=True,
        )
        regions = json.loads(dissolved_path.read_text())

    regions["name"] = "COSOLVE Virginia ecosystem regions"
    regions["description"] = (
        "Working analytical groupings derived from 2025 U.S. Census Bureau TIGERweb county "
        "and independent-city boundaries; not legal or official planning-district boundaries."
    )
    regions["features"].sort(key=lambda feature: feature["properties"]["region_name"])
    OUTPUT_PATH.write_text(json.dumps(regions, separators=(",", ":")) + "\n")
    print(f"Wrote {len(regions['features'])} regions to {OUTPUT_PATH}")


if __name__ == "__main__":
    build()
