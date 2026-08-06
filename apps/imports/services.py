import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator

from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory

REQUIRED_COLUMNS = {"name", "record_type", "short_description", "unmanned_systems_relevance"}
TAXONOMY_COLUMNS = {
    "strategic_categories": StrategicCategory,
    "platform_domains": PlatformDomain,
    "capabilities": Capability,
    "missions": MissionArea,
}
CSV_COLUMNS = [
    "slug",
    "name",
    "record_type",
    "short_description",
    "overview",
    "unmanned_systems_relevance",
    "website_url",
    "contact_text",
    "contact_phone",
    "contact_email",
    "contact_url",
    "address_line",
    "city",
    "state",
    "postal_code",
    "latitude",
    "longitude",
    "location_precision",
    "region",
    "strategic_categories",
    "platform_domains",
    "capabilities",
    "missions",
    "source_titles",
    "source_urls",
    "source_dates",
    "status",
    "visibility",
    "last_verified_at",
    "internal_notes",
]


def split_values(value):
    return [item.strip() for item in value.split("|") if item.strip()]


def split_aligned(value):
    return [item.strip() for item in value.split("|")] if value else []


def joined_slugs(items):
    return "|".join(items.values_list("slug", flat=True))


def asset_csv_row(asset, include_internal=False):
    sources = list(asset.sources.all())
    return {
        "slug": asset.slug,
        "name": asset.name,
        "record_type": asset.record_type,
        "short_description": asset.short_description,
        "overview": asset.overview,
        "unmanned_systems_relevance": asset.unmanned_systems_relevance,
        "website_url": asset.website_url,
        "contact_text": asset.contact_text,
        "contact_phone": asset.contact_phone,
        "contact_email": asset.contact_email,
        "contact_url": asset.contact_url,
        "address_line": asset.address_line,
        "city": asset.city,
        "state": asset.state,
        "postal_code": asset.postal_code,
        "latitude": asset.latitude if asset.latitude is not None else "",
        "longitude": asset.longitude if asset.longitude is not None else "",
        "location_precision": asset.location_precision,
        "region": asset.region.slug if asset.region else "",
        "strategic_categories": joined_slugs(asset.strategic_categories),
        "platform_domains": joined_slugs(asset.platform_domains),
        "capabilities": joined_slugs(asset.capabilities),
        "missions": joined_slugs(asset.missions),
        "source_titles": "|".join(source.title for source in sources),
        "source_urls": "|".join(source.url for source in sources),
        "source_dates": "|".join(
            source.source_date.isoformat() if source.source_date else "" for source in sources
        ),
        "status": asset.status,
        "visibility": asset.visibility,
        "last_verified_at": (
            asset.last_verified_at.isoformat() if asset.last_verified_at else ""
        ),
        "internal_notes": asset.internal_notes if include_internal else "",
    }


def validate_url(value, label, errors):
    if not value:
        return
    try:
        URLValidator(schemes=["http", "https"])(value)
    except ValidationError:
        errors.append(f"{label} must be a valid HTTP or HTTPS URL.")


def parse_iso_date(value, label, errors):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{label} must use YYYY-MM-DD format.")
        return None


def source_values(row, errors):
    titles = split_aligned(row.get("source_titles", ""))
    urls = split_aligned(row.get("source_urls", ""))
    dates = split_aligned(row.get("source_dates", ""))
    if not titles and row.get("source_title"):
        titles = [row["source_title"]]
        urls = [row.get("source_url", "")]
        dates = [row.get("source_date", "")]
    if not any(titles) and not any(urls) and not any(dates):
        return []
    if len(titles) != len(urls):
        errors.append(
            "Source titles and URLs must contain the same number of pipe-separated values."
        )
        return []
    if len(dates) > len(titles):
        errors.append("Source dates cannot outnumber source titles.")
        return []
    dates.extend([""] * (len(titles) - len(dates)))
    sources = []
    for index, (title, url, source_date) in enumerate(
        zip(titles, urls, dates, strict=True), start=1
    ):
        if not title or not url:
            errors.append(f"Source {index} requires both a title and URL.")
            continue
        validate_url(url, f"Source {index} URL", errors)
        parsed_date = parse_iso_date(source_date, f"Source {index} date", errors)
        sources.append(
            {
                "title": title,
                "url": url,
                "source_date": parsed_date.isoformat() if parsed_date else "",
            }
        )
    return sources


def parse_csv(upload):
    text = upload.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        return [], [f"Missing required column(s): {', '.join(sorted(missing))}"]

    rows = []
    file_errors = []
    valid_record_types = {value for value, _label in Asset.RecordType.choices}
    valid_location_precisions = {value for value, _label in Asset.LocationPrecision.choices}
    for number, raw in enumerate(reader, start=2):
        row = {key: (value or "").strip() for key, value in raw.items() if key is not None}
        errors = []
        if not row["name"]:
            errors.append("Name is required.")
        if row["record_type"] not in valid_record_types:
            errors.append("Record type is invalid.")
        if not row["short_description"]:
            errors.append("Short description is required.")
        if not row["unmanned_systems_relevance"]:
            errors.append("Unmanned systems relevance is required.")
        if row.get("state") and len(row["state"]) != 2:
            errors.append("State must use a two-letter abbreviation.")
        if (
            row.get("location_precision")
            and row["location_precision"] not in valid_location_precisions
        ):
            errors.append("Location precision is invalid.")
        for coordinate in ("latitude", "longitude"):
            if row.get(coordinate):
                try:
                    Decimal(row[coordinate])
                except InvalidOperation:
                    errors.append(f"{coordinate.title()} must be numeric.")
        if bool(row.get("latitude")) != bool(row.get("longitude")):
            errors.append("Latitude and longitude must be provided together.")
        validate_url(row.get("website_url", ""), "Website URL", errors)
        validate_url(row.get("contact_url", ""), "Contact URL", errors)
        if row.get("contact_email"):
            try:
                EmailValidator()(row["contact_email"])
            except ValidationError:
                errors.append("Contact email must be a valid email address.")
        for column, model in TAXONOMY_COLUMNS.items():
            requested = split_values(row.get(column, ""))
            existing = set(model.objects.filter(slug__in=requested).values_list("slug", flat=True))
            missing_values = set(requested) - existing
            if missing_values:
                errors.append(f"Unknown {column}: {', '.join(sorted(missing_values))}")
        region_slug = row.get("region", "")
        if region_slug and not Region.objects.filter(slug=region_slug).exists():
            errors.append(f"Unknown region: {region_slug}")
        sources = source_values(row, errors)
        asset = None
        if row.get("slug"):
            asset = Asset.objects.filter(slug=row["slug"]).first()
        if asset is None:
            asset = Asset.objects.filter(
                name__iexact=row["name"], city__iexact=row.get("city", "")
            ).first()
        rows.append(
            {
                "number": number,
                "data": row,
                "sources": sources,
                "errors": errors,
                "duplicate": asset is not None,
                "asset_id": str(asset.pk) if asset else "",
            }
        )
    if not rows:
        file_errors.append("The CSV contains no data rows.")
    return rows, file_errors
