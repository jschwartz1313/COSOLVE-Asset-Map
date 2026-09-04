#!/usr/bin/env python3
"""Prepare evidence-review candidates; never turn heuristics into editorial verification."""

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "virginia_real_assets.json"


def build_candidates(catalog, reviewed_at):
    return {
        "prepared_at": reviewed_at,
        "methodology": (
            "Candidate evidence index only. Attached links and catalog statements have not "
            "been independently confirmed by this script. An editor must review identity, "
            "Virginia location, relevance, activity status, and each material claim before "
            "creating a separate editorial-review manifest. Availability checks belong in "
            "audit_catalog_sources.py; successful HTTP responses do not verify claims."
        ),
        "record_count": len(catalog["records"]),
        "reviewed_assets": {},
        "candidates": [
            {
                "name": record["name"],
                "outcome": "pending-editorial-review",
                "location_precision": record["location_precision"],
                "evidence_urls": list(dict.fromkeys(source["url"] for source in record["sources"])),
            }
            for record in sorted(catalog["records"], key=lambda item: item["name"].casefold())
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New candidate-review file; existing files are never overwritten.",
    )
    options = parser.parse_args()
    if options.output.name.startswith(("asset_editorial_reviews", "asset_catalog_audit")):
        parser.error(
            "Candidate output cannot use an editorial-review or historical-audit filename."
        )
    candidates = build_candidates(json.loads(options.catalog.read_text()), date.today().isoformat())
    with options.output.open("x") as destination:
        destination.write(json.dumps(candidates, indent=2, sort_keys=True) + "\n")
    print(f"Prepared {candidates['record_count']} candidates; no records marked verified.")


if __name__ == "__main__":
    main()
