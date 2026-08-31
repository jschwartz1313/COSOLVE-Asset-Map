import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assets.models import Asset
from apps.catalog.models import Capability, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source

PROFILE_FIELDS = (
    "overview",
    "contact_text",
    "contact_phone",
    "contact_email",
    "contact_url",
    "activity_status",
    "current_activity",
    "partnership_opportunities",
    "activity_source_url",
    "activity_last_verified_at",
    "owner_operator",
    "available_acreage",
    "development_status",
    "development_notes",
    "infrastructure_access",
    "development_source_url",
    "development_last_verified_at",
)
DATE_FIELDS = {"activity_last_verified_at", "development_last_verified_at"}
LOCATION_CORRECTION_LEGACY_CITIES = {
    "Virginia Advanced Air Mobility Program": "Richmond",
    "Virginia Department of Aviation": "Richmond",
    "Virginia Flight Information Exchange": "Blacksburg",
}
LEGACY_DESCRIPTIONS = {
    "Public degree-granting community college serving Virginia students and employers.",
    "Public degree-granting college or university in Virginia.",
    "Private nonprofit degree-granting college or university in Virginia.",
    "Private degree-granting university included in SCHEV statewide completion reporting.",
}
ECOSYSTEM_ROLE_CATEGORIES = {
    "Core unmanned-systems asset",
    "Supporting ecosystem asset",
}
MANUFACTURING_FACILITY_CATEGORY = "Manufacturing facilities"
MANUFACTURING_CAPABILITY = "Manufacturing, materials, and prototyping"
ADDITIVE_STRATEGIC_CATEGORIES = ECOSYSTEM_ROLE_CATEGORIES | {
    MANUFACTURING_FACILITY_CATEGORY
}
TARGET_CONTACT_UPGRADES = {
    "ANRA Technologies",
    "Advanced Aircraft Company",
    "AeroVironment Corporate Headquarters",
    "Aurora Flight Sciences",
    "Longbow Unmanned Systems Research and Test Center",
    "Mid-Atlantic Aviation Partnership",
    "ODU Institute for Autonomous and Connected Systems",
    "ODU Maritime Autonomous Systems Test Site",
    "Virginia Tech Drone Park",
    "Virginia Unmanned Systems Center",
    "Wallops Research Park",
    "Autonomous Flight Technologies",
    "DZYNE Technologies",
    "DroneUp",
    "Former Dedrone Washington-Area Headquarters",
}
RESOLVED_JURISDICTION_RECORDS = {
    "Amherst County Fire and EMS Drone Program",
    "Ashland Police Department Drone Program",
    "Haymarket Police Department Drone Program",
    "Madison County Sheriff's Office UAS Program",
    "Occoquan Police Department Public Safety Drone Program",
    "Radford City Police Department Drone Program",
    "Staunton Police Department UAS Program",
    "Wise County Sheriff's Office Drone Program",
    "Wythe County Sheriff's Office Drone Program",
}
TARGET_CONTACT_UPGRADES |= RESOLVED_JURISDICTION_RECORDS
GENERATED_CONTACT_SCOPES = {
    "Facility or operator public information",
    "Organization public information and inquiries",
    "Public information route; a direct asset contact is not published in the catalog",
    "Site operator or program information",
}
STALE_CATALOG_SOURCE_URLS = {
    "Accomack County Emergency Management Drone Program": {
        "https://www.co.accomack.va.us/Home/Components/News/News/381/18",
    },
    "Dominion Energy UAS Program": {
        "https://www.dominionenergy.com/our-stories/unmanned-aerial-inspections",
    },
    "Hampden-Sydney College": {
        "https://www.hsc.edu/admissions-and-financial-aid",
    },
    "HII Unmanned Systems Center of Excellence": {
        "https://www.hampton.gov/CivicAlerts.aspx?AID=4656&ARC=9365",
        "https://www.hampton.gov/CivicAlerts.aspx?AID=4759&ARC=9695",
    },
    "Autonomous Flight Technologies": {
        "https://www.autonomousflight.us/contact-offices",
    },
    "DZYNE Technologies": {
        "https://www.sbir.gov/portfolio/406214",
    },
    "Former Dedrone Washington-Area Headquarters": {
        "https://www.dedrone.com/about/contact-us",
        "https://www.dedrone.com/contact",
    },
    "Haymarket Police Department Drone Program": {
        "https://www.townofhaymarket.org/sites/default/files/fileattachments/police/page/2971/haymarket_police_department_annual_report_2022.pdf",
        "https://www.townofhaymarket.org/1450/Patrol-Division",
    },
    "Navy TALSA East Small UAS Training Facility": {
        "https://www.navair.navy.mil/contact-us",
    },
    "York County ROVER Team": {
        "https://www.yorkcounty.gov/99/Fire-Life-Safety",
    },
    "Longbow Unmanned Systems Research and Test Center": {
        "https://www.hampton.gov/CivicAlerts.aspx?AID=4973&ARC=10333",
        "https://www.usrtc.org/",
        "https://www.usrtc.org/about-us",
    },
    "Orange County Sheriff's Office Drone Team": {
        "https://www.louisacounty.gov/m/newsflash?cat=22%2C1",
    },
    "National Institute of Aerospace": {
        "https://www.nianet.org/contact/",
    },
    "Virginia Military Institute": {
        "https://www.vmi.edu/about/our-location/map-and-directions/",
    },
}
LEGACY_SHARED_WEBSITE_URLS = {
    "https://www.vedp.org/industry/unmanned-systems",
    (
        "https://www.vada.virginia.gov/media/governorvirginiagov/"
        "secretary-of-veterans-and-defense-affairs/pdf/VA-FactBook_WEB_2020-10-19-CSG.pdf"
    ),
}
LEGACY_JURISDICTION_WEBSITE_URLS = {
    "https://www.dcjs.virginia.gov/grants/programs/cy-26-unmanned-aircraft-trade-and-replace-program",
    "https://www.vaco.org/wp-content/uploads/2025/12/DCJS-Meeting-UAB-Chart.pdf",
}
LEGACY_WEBSITE_URLS_BY_ASSET = {
    "Autonomous Flight Technologies": {
        "https://www.autonomousflight.us/company",
    },
    "DZYNE Technologies": {
        "https://dzyne.com/about/",
    },
    "DroneUp": {
        "https://www.vedp.org/news/home-business-more-400-years",
    },
    "Former Dedrone Washington-Area Headquarters": {
        "https://www.dedrone.com/about/contact-us",
    },
    "Haymarket Police Department Drone Program": {
        "https://www.townofhaymarket.org/sites/default/files/fileattachments/police/page/2971/haymarket_police_department_annual_report_2022.pdf",
    },
    "Accomack County Emergency Management Drone Program": {
        "https://www.co.accomack.va.us/Home/Components/News/News/381/18"
    },
    "Dominion Energy UAS Program": {
        "https://www.dominionenergy.com/our-stories/unmanned-aerial-inspections"
    },
    "Longbow Unmanned Systems Research and Test Center": {
        "https://www.hampton.gov/CivicAlerts.aspx?AID=4973&ARC=10333",
        "https://www.usrtc.org/",
    },
    "Orange County Sheriff's Office Drone Team": {
        "https://www.louisacounty.gov/m/newsflash?cat=22%2C1",
    },
    "VCU ARVL Robotic Drone System": {"https://arvl.lab.vcu.edu/"},
}
LEGACY_CONTACT_URLS_BY_ASSET = {
    "Autonomous Flight Technologies": {
        "https://www.autonomousflight.us/contact-offices",
    },
    "Former Dedrone Washington-Area Headquarters": {
        "https://www.dedrone.com/contact",
    },
    "Haymarket Police Department Drone Program": {
        "https://www.townofhaymarket.org/1450/Patrol-Division",
    },
    "Navy TALSA East Small UAS Training Facility": {
        "https://www.navair.navy.mil/contact-us",
        "https://cnrma.cnic.navy.mil/Installations/JEB-Little-Creek-Fort-Story/Contact-Us/",
    },
    "York County ROVER Team": {
        "https://www.yorkcounty.gov/1874/The-ROVER-Team",
        "https://www.yorkcounty.gov/99/Fire-Life-Safety",
    },
    "Accomack County Emergency Management Drone Program": {
        "https://www.co.accomack.va.us/Home/Components/News/News/381/18"
    },
    "Dominion Energy UAS Program": {
        "https://www.dominionenergy.com/our-stories/unmanned-aerial-inspections"
    },
    "Hampden-Sydney College": {"https://www.hsc.edu/admissions-and-financial-aid"},
    "Longbow Unmanned Systems Research and Test Center": {
        "https://www.hampton.gov/CivicAlerts.aspx?AID=4973&ARC=10333",
        "https://www.usrtc.org/",
        "https://www.usrtc.org/about-us",
    },
    "National Institute of Aerospace": {"https://www.nianet.org/contact/"},
}

LEGACY_FIELD_VALUES_BY_ASSET = {
    "Autonomous Flight Technologies": {
        "city": {"Roanoke"},
        "address_line": {""},
        "postal_code": {""},
        "latitude": {37.271},
        "longitude": {-79.941},
        "location_precision": {Asset.LocationPrecision.LOCALITY},
        "short_description": {
            "Roanoke-based developer of unmanned aircraft, avionics, and "
            "autonomous-flight technologies."
        },
    },
    "DZYNE Technologies": {
        "address_line": {"8280 Willow Oaks Corporate Drive, Suite 200"},
        "postal_code": {"22031"},
        "latitude": {38.863831},
        "longitude": {-77.230173},
        "location_precision": {Asset.LocationPrecision.EXACT},
        "short_description": {
            "Fairfax office of an autonomous-systems company developing long-endurance "
            "unmanned aircraft, autonomy software, and counter-unmanned capabilities."
        },
    },
    "DroneUp": {
        "address_line": {"160 Newtown Road, Suite 302"},
        "postal_code": {"23462"},
        "latitude": {36.842642},
        "longitude": {-76.186071},
        "location_precision": {Asset.LocationPrecision.SITE},
        "short_description": {
            "Virginia Beach-founded drone services, operations, software, training, "
            "and delivery company."
        },
    },
    "Former Dedrone Washington-Area Headquarters": {
        "short_description": {
            "Sterling headquarters for counter-drone sensing, identification, tracking, "
            "and airspace-security technology."
        },
    },
}


def matches_legacy_value(value, candidates):
    if value in candidates:
        return True
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False
    return any(
        abs(numeric_value - float(candidate)) < 0.000001
        for candidate in candidates
        if isinstance(candidate, (int, float))
    )


class Command(BaseCommand):
    help = "Fill missing source-backed asset profiles and contacts without replacing staff edits."

    def add_arguments(self, parser):
        parser.add_argument(
            "--catalog",
            type=Path,
            default=settings.BASE_DIR / "data" / "virginia_real_assets.json",
            help="Path to the generated real-asset catalog JSON.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        records = json.loads(options["catalog"].read_text())["records"]
        updated_assets = 0
        added_sources = 0
        removed_stale_sources = 0
        for record in records:
            asset = Asset.objects.filter(name=record["name"]).first()
            if asset is None:
                continue

            changed_fields = []
            catalog_managed = asset.internal_notes.startswith("Catalog provenance:")
            legacy_website_urls = LEGACY_SHARED_WEBSITE_URLS | LEGACY_WEBSITE_URLS_BY_ASSET.get(
                record["name"], set()
            )
            if (
                catalog_managed
                and record.get("website_url")
                and (
                    asset.website_url in legacy_website_urls
                    or (
                        record["name"] in RESOLVED_JURISDICTION_RECORDS
                        and asset.website_url in LEGACY_JURISDICTION_WEBSITE_URLS
                    )
                )
                and asset.website_url != record["website_url"]
            ):
                asset.website_url = record["website_url"]
                changed_fields.append("website_url")

            if (
                catalog_managed
                and asset.contact_url in LEGACY_CONTACT_URLS_BY_ASSET.get(record["name"], set())
                and record.get("contact_url")
                and asset.contact_url != record["contact_url"]
            ):
                for field in ("contact_phone", "contact_email", "contact_url"):
                    if record.get(field) not in (None, ""):
                        setattr(asset, field, record[field])
                        changed_fields.append(field)

            corrected_description = False
            legacy_fields = LEGACY_FIELD_VALUES_BY_ASSET.get(record["name"], {})
            location_fields = {
                "address_line",
                "city",
                "postal_code",
                "latitude",
                "longitude",
                "location_precision",
            }.intersection(legacy_fields)
            legacy_location_matches = all(
                matches_legacy_value(getattr(asset, field), legacy_fields[field])
                for field in location_fields
            )
            for field, legacy_values in legacy_fields.items():
                if field in location_fields and not legacy_location_matches:
                    continue
                current_value = getattr(asset, field)
                target_value = record.get(field, "")
                if (
                    catalog_managed
                    and matches_legacy_value(current_value, legacy_values)
                    and current_value != target_value
                ):
                    setattr(asset, field, target_value)
                    changed_fields.append(field)
                    corrected_description |= field == "short_description"
            if corrected_description and asset.overview.startswith(
                tuple(
                    LEGACY_FIELD_VALUES_BY_ASSET[record["name"]].get(
                        "short_description", set()
                    )
                )
            ):
                asset.overview = record["overview"]
                changed_fields.append("overview")

            for field in PROFILE_FIELDS:
                if getattr(asset, field) in (None, "") and record.get(field) not in (None, ""):
                    value = record[field]
                    if field in DATE_FIELDS:
                        value = date.fromisoformat(value)
                    setattr(asset, field, value)
                    changed_fields.append(field)

            if "Advanced Air Mobility" in record.get("platform_domains", []):
                aam_domain, _created = PlatformDomain.objects.get_or_create(
                    name="Advanced Air Mobility"
                )
                if not asset.platform_domains.filter(pk=aam_domain.pk).exists():
                    asset.platform_domains.add(aam_domain)

            for category_name in ADDITIVE_STRATEGIC_CATEGORIES.intersection(
                record.get("strategic_categories", [])
            ):
                role_category, _created = StrategicCategory.objects.get_or_create(
                    name=category_name
                )
                if not asset.strategic_categories.filter(pk=role_category.pk).exists():
                    asset.strategic_categories.add(role_category)

            if MANUFACTURING_FACILITY_CATEGORY in record.get("strategic_categories", []):
                manufacturing_capability, _created = Capability.objects.get_or_create(
                    name=MANUFACTURING_CAPABILITY
                )
                if not asset.capabilities.filter(pk=manufacturing_capability.pk).exists():
                    asset.capabilities.add(manufacturing_capability)

            if (
                record["name"] in TARGET_CONTACT_UPGRADES
                and asset.contact_text in GENERATED_CONTACT_SCOPES
            ):
                for field in (
                    "contact_text",
                    "contact_phone",
                    "contact_email",
                    "contact_url",
                ):
                    if record.get(field):
                        setattr(asset, field, record[field])
                        changed_fields.append(field)

            legacy_airport_description = asset.short_description.startswith(
                "Operational public-use Virginia aviation facility (FAA identifier "
            )
            resolved_jurisdiction_description = (
                catalog_managed
                and record["name"] in RESOLVED_JURISDICTION_RECORDS
                and asset.short_description.startswith(
                    "A CY 2026 Virginia DCJS award documents an unmanned aircraft"
                )
            )
            if (
                asset.short_description in LEGACY_DESCRIPTIONS
                or legacy_airport_description
                or resolved_jurisdiction_description
            ):
                asset.short_description = record["short_description"]
                changed_fields.append("short_description")
            if resolved_jurisdiction_description:
                asset.overview = record["overview"]
                changed_fields.append("overview")

            if record["provenance"] == "faa-public-airport":
                for field in ("address_line", "postal_code"):
                    if not getattr(asset, field) and record.get(field):
                        setattr(asset, field, record[field])
                        changed_fields.append(field)

            if (
                catalog_managed
                and not asset.address_line
                and asset.location_precision
                in {
                    Asset.LocationPrecision.APPROXIMATE,
                    Asset.LocationPrecision.LOCALITY,
                }
                and record.get("location_precision")
                in {
                    Asset.LocationPrecision.EXACT,
                    Asset.LocationPrecision.SITE,
                }
            ):
                for field in (
                    "address_line",
                    "city",
                    "postal_code",
                    "latitude",
                    "longitude",
                    "location_precision",
                ):
                    setattr(asset, field, record.get(field))
                    changed_fields.append(field)
                asset.region, _created = Region.objects.get_or_create(
                    name=record["region"],
                    defaults={"region_type": "Virginia ecosystem region"},
                )
                changed_fields.append("region")

            legacy_city = LOCATION_CORRECTION_LEGACY_CITIES.get(record["name"])
            if (
                legacy_city
                and asset.city == legacy_city
                and not asset.address_line
                and asset.location_precision == Asset.LocationPrecision.LOCALITY
            ):
                for field in (
                    "address_line",
                    "city",
                    "postal_code",
                    "latitude",
                    "longitude",
                    "location_precision",
                ):
                    value = record.get(field, "")
                    if field in {"latitude", "longitude"}:
                        value = record.get(field)
                    setattr(asset, field, value)
                    changed_fields.append(field)
                asset.region, _created = Region.objects.get_or_create(
                    name=record["region"],
                    defaults={"region_type": "Virginia ecosystem region"},
                )
                changed_fields.append("region")

            if changed_fields:
                asset.save(update_fields=[*changed_fields, "updated_at"])
                updated_assets += 1

            existing_urls = set(asset.sources.values_list("url", flat=True))
            for source_data in record["sources"]:
                if source_data["url"] in existing_urls:
                    continue
                Source.objects.create(
                    asset=asset,
                    title=source_data["title"],
                    url=source_data["url"],
                    notes=f"Catalog provenance: {record['provenance']}",
                    is_public=True,
                )
                existing_urls.add(source_data["url"])
                added_sources += 1

            stale_urls = STALE_CATALOG_SOURCE_URLS.get(record["name"], set())
            if stale_urls:
                deleted_count, _details = asset.sources.filter(
                    url__in=stale_urls,
                    notes__startswith="Catalog provenance:",
                ).delete()
                removed_stale_sources += deleted_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Enriched {updated_assets} existing assets and added "
                f"{added_sources} public sources; removed "
                f"{removed_stale_sources} obsolete catalog sources."
            )
        )
