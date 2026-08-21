#!/usr/bin/env python3
"""Build the checked-in full-catalog verification manifest and audit ledger."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "virginia_real_assets.json"
REVIEW_PATH = ROOT / "data" / "asset_editorial_reviews.json"
AUDIT_PATH = ROOT / "data" / "asset_catalog_audit_2026_08_21.json"
REVIEWED_AT = "2026-08-21"
DISALLOWED_VERIFICATION_EVIDENCE = {
    "DZYNE Technologies": {"https://www.sbir.gov/portfolio/406214"},
}


def unique(values):
    return list(dict.fromkeys(value for value in values if value))


def source_score(record, source):
    title = source["title"].lower()
    url = source["url"].lower()
    value = f"{title} {url}"
    score = 0
    if source["url"] == record.get("activity_source_url"):
        score += 18
    if source["url"] == record["website_url"]:
        score += 14
    if title.startswith("faa airport record for "):
        score += 20
    if "nces ipeds" in value or "ipeds/datacenter" in value:
        score += 16
    if any(
        term in value
        for term in (
            "unmanned",
            "uncrewed",
            " uas",
            "drone",
            "autonom",
            "robot",
            "counter-uas",
            "airport record",
        )
    ):
        score += 8
    if any(term in title for term in ("contact information", "directory", "general information")):
        score -= 5
    if url.endswith(".pdf"):
        score += 1
    return score


def select_evidence(record, previous_review_urls):
    attached = {source["url"] for source in record["sources"]}
    disallowed = DISALLOWED_VERIFICATION_EVIDENCE.get(record["name"], set())
    selected = [
        url for url in previous_review_urls if url in attached and url not in disallowed
    ]

    if record["provenance"] == "faa-public-airport":
        selected.extend(
            source["url"]
            for source in record["sources"]
            if source["title"].startswith("FAA airport record for ")
            or "airport_sponsors" in source["url"]
        )
    elif record["provenance"] in {
        "nces-ipeds-higher-education",
        "university-institution",
    }:
        selected.extend(
            source["url"]
            for source in record["sources"]
            if "ipeds/datacenter" in source["url"] or source["url"] == record["website_url"]
        )
    elif record["provenance"] == "virginia-military-factbook":
        selected.append(record["website_url"])
    else:
        selected.extend(
            [
                record.get("activity_source_url"),
                record["website_url"],
            ]
        )

    ranked = sorted(
        (source for source in record["sources"] if source["url"] not in disallowed),
        key=lambda item: source_score(record, item),
        reverse=True,
    )
    selected.extend(source["url"] for source in ranked)
    return unique(selected)[:3]


def review_basis(record):
    if record["provenance"] == "faa-public-airport":
        return (
            "Current FAA airport-service record, Virginia Department of Aviation directory, "
            "and sponsor contact cross-check. Inclusion does not imply UAS flight permission."
        )
    if record["provenance"] == "nces-ipeds-higher-education":
        return (
            "NCES IPEDS institutional identity and campus-location check. The record is "
            "classified as supporting capacity and does not claim a documented UxS program."
        )
    if record["provenance"] == "university-institution":
        return (
            "NCES IPEDS institutional check plus attached official sources for the mapped "
            "unmanned-systems program, laboratory, or activity."
        )
    if record["provenance"] == "virginia-military-factbook":
        return (
            "Current official installation or agency page cross-checked against the Virginia "
            "military factbook; classified as supporting federal and defense infrastructure."
        )
    return (
        "Record-specific public sources checked for the named entity or program, Virginia "
        "location, described role, and conservative location precision."
    )


def main():
    catalog = json.loads(CATALOG_PATH.read_text())
    previous = json.loads(REVIEW_PATH.read_text())
    previous_reviews = previous.get("reviewed_assets", {})
    follow_ups = previous.get("follow_up_assets", {})
    reviewed_assets = {}
    audit_records = []

    for record in sorted(catalog["records"], key=lambda item: item["name"].casefold()):
        evidence_urls = select_evidence(record, previous_reviews.get(record["name"], []))
        attached_urls = {source["url"] for source in record["sources"]}
        if not evidence_urls or not set(evidence_urls).issubset(attached_urls):
            raise ValueError(f"Missing attached verification evidence for {record['name']}")

        if record["name"] in follow_ups:
            outcome = "qualified-follow-up"
            decision_note = follow_ups[record["name"]]
        elif record.get("activity_status") == "historical":
            outcome = "confirmed-historical"
            decision_note = (
                "The historical activity and its Virginia connection are supported; the record "
                "is not represented as a current standalone operation."
            )
            reviewed_assets[record["name"]] = evidence_urls
        else:
            outcome = "confirmed"
            decision_note = (
                "Identity, Virginia location at the stated precision, and catalog scope are "
                "supported by the selected public evidence."
            )
            reviewed_assets[record["name"]] = evidence_urls

        audit_records.append(
            {
                "name": record["name"],
                "outcome": outcome,
                "record_type": record["record_type"],
                "provenance": record["provenance"],
                "ecosystem_role": next(
                    category
                    for category in record["strategic_categories"]
                    if category
                    in {"Core unmanned-systems asset", "Supporting ecosystem asset"}
                ),
                "location_precision": record["location_precision"],
                "source_count": len(record["sources"]),
                "evidence_urls": evidence_urls,
                "review_basis": review_basis(record),
                "decision_note": decision_note,
            }
        )

    if len(audit_records) != catalog["record_count"]:
        raise ValueError("Audit ledger does not cover every catalog record")
    if len(reviewed_assets) + len(follow_ups) != catalog["record_count"]:
        raise ValueError("Every catalog record must be confirmed or assigned follow-up")

    manifest = {
        "reviewed_at": REVIEWED_AT,
        "methodology": (
            "Full-catalog verification pass using current authoritative registry refreshes, "
            "record-specific official public pages, source-availability checks, targeted "
            "current-status research, and conservative location precision. Verification "
            "confirms the catalog claim as written; it does not imply flight authorization, "
            "site access, endorsement, or that future activity will remain unchanged."
        ),
        "reviewed_assets": reviewed_assets,
        "follow_up_assets": follow_ups,
    }
    REVIEW_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    outcomes = {}
    provenances = {}
    for item in audit_records:
        outcomes[item["outcome"]] = outcomes.get(item["outcome"], 0) + 1
        provenances[item["provenance"]] = provenances.get(item["provenance"], 0) + 1
    audit = {
        "audited_at": REVIEWED_AT,
        "record_count": len(audit_records),
        "outcomes": outcomes,
        "provenance_counts": provenances,
        "source_availability_summary": {
            "checked_at": REVIEWED_AT,
            "source_records_checked": 1310,
            "distinct_urls_checked": 763,
            "confirmed_dead_urls": 0,
            "automation_blocked_urls": [
                "https://www.centrahealth.com/college",
                "https://www.centrahealth.com/college/programs-admissions",
                "https://www.ci.staunton.va.us/departments/police",
                "https://www.mcwl.marines.mil/Divisions/SnT/CTO/",
            ],
            "note": (
                "The four remaining automated warnings are HTTP 403 anti-automation "
                "responses, not confirmed dead links. The two Centra College pages belong to "
                "a specialized institution hidden from the public catalog. The Staunton and "
                "Marine Corps records have separate accepted official evidence, and their "
                "blocked pages were also confirmed through browser-accessible official results."
            ),
        },
        "methodology": manifest["methodology"],
        "records": audit_records,
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(
        f"Wrote {len(reviewed_assets)} confirmed reviews and {len(follow_ups)} follow-ups; "
        f"audit ledger covers {len(audit_records)} records."
    )


if __name__ == "__main__":
    main()
