#!/usr/bin/env python3
"""Extract review leads, not publishable assets, from current official SBIR award titles."""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "tmp/peer-expansion-20261118"
STATES = {"Arizona": "AZ", "California": "CA", "Colorado": "CO", "Florida": "FL",
          "Michigan": "MI", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
          "Ohio": "OH", "Oklahoma": "OK", "Pennsylvania": "PA", "Texas": "TX", "Utah": "UT"}
MATCH = re.compile(r"\b(unmanned|uncrewed|drone\w*|robot\w*|autonom\w*|UAS|UAV|UUV|USV|UGV|"
                   r"eVTOL|counter[- ]UAS|advanced air mobility)\b", re.I)
EXCLUDE = re.compile(r"\b(surg\w*|rehabilitation|prosthe\w*|endoscop\w*)\b", re.I)


def main():
    firms = defaultdict(list)
    with (CACHE / "sbir_awards_no_abstract.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            state = STATES.get(row["State"])
            if not state or int(row["Award Year"] or 0) < 2023:
                continue
            if not MATCH.search(row["Award Title"]) or EXCLUDE.search(row["Award Title"]):
                continue
            identity = row["UEI"] or row["Company"].strip().casefold()
            firms[(state, identity)].append({
                "name": row["Company"].strip(), "year": int(row["Award Year"]),
                "title": row["Award Title"].strip(), "agency": row["Agency"],
                "city": row["City"].strip(), "website": row["Company Website"].strip(),
                "uei": row["UEI"], "contract": row["Contract"],
            })
    records = []
    for (state, _identity), awards in firms.items():
        awards.sort(key=lambda row: -row["year"])
        records.append({"state": state, **awards[0], "awards": awards})
    result = {
        "retrieved": "2026-11-18",
        "source": "https://data.www.sbir.gov/mod_awarddatapublic_no_abstract/"
                  "award_data_no_abstract.csv",
        "note": "Research candidates only. Award location/title is dated evidence, not "
                "current operating presence, product availability or editorial verification. "
                "Confirm company identity and current in-state activity with first-party sources. "
                "No personal contacts or residential mailing addresses are retained here.",
        "records": sorted(records, key=lambda row: (row["state"], -row["year"], row["name"])),
    }
    (CACHE / "sbir_candidates.json").write_text(json.dumps(result, indent=2) + "\n")
    print(Counter(row["state"] for row in records))


if __name__ == "__main__":
    main()
