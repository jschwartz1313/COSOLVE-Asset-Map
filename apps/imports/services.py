import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator

from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source

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
IMPORT_FIELDS = set(CSV_COLUMNS) - {
    "slug",
    "region",
    "status",
    "visibility",
    "last_verified_at",
    "source_titles",
    "source_urls",
    "source_dates",
    *TAXONOMY_COLUMNS,
}


def prepare_import_asset(data, asset=None):
    """Apply supplied columns, preserving omitted fields on an existing record."""
    is_new = asset is None
    asset = asset or Asset()
    for name in IMPORT_FIELDS & data.keys():
        field = Asset._meta.get_field(name)
        value = data[name]
        if not value:
            value = None if field.null else field.get_default() if field.has_default() else ""
        setattr(asset, name, value)
    if is_new and data.get("slug"):
        asset.slug = data["slug"]
    if "region" in data:
        asset.region = Region.objects.filter(slug=data["region"]).first()
    if "location_precision" in data:
        asset.location_precision = data["location_precision"] or Asset.LocationPrecision.APPROXIMATE
    asset.status = Asset.Status.DRAFT if is_new else Asset.Status.NEEDS_REVIEW
    asset.visibility = Asset.Visibility.INTERNAL
    asset.last_verified_at = None
    asset.reviewed_at = None
    asset.reviewed_by = None
    asset.published_at = None
    asset.full_clean()
    return asset


def split_values(value):
    return [item.strip() for item in value.split("|") if item.strip()]


def split_aligned(value):
    return [item.strip() for item in value.split("|")] if value else []


def joined_slugs(items):
    return "|".join(items.values_list("slug", flat=True))


def asset_csv_row(asset, include_internal=False):
    sources = [source for source in asset.sources.all() if include_internal or source.is_public]
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
        "activity_status": asset.activity_status,
        "current_activity": asset.current_activity,
        "partnership_opportunities": asset.partnership_opportunities,
        "activity_source_url": asset.activity_source_url,
        "activity_last_verified_at": (
            asset.activity_last_verified_at.isoformat() if asset.activity_last_verified_at else ""
        ),
        "owner_operator": asset.owner_operator,
        "available_acreage": (
            asset.available_acreage if asset.available_acreage is not None else ""
        ),
        "development_status": asset.development_status,
        "development_notes": asset.development_notes,
        "infrastructure_access": asset.infrastructure_access,
        "development_source_url": asset.development_source_url,
        "development_last_verified_at": (
            asset.development_last_verified_at.isoformat()
            if asset.development_last_verified_at
            else ""
        ),
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
        "last_verified_at": (asset.last_verified_at.isoformat() if asset.last_verified_at else ""),
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
        for name, value in (("title", title), ("url", url)):
            try:
                Source._meta.get_field(name).clean(value, None)
            except ValidationError as error:
                errors.extend(f"Source {index}: {message}" for message in error.messages)
        parsed_date = parse_iso_date(source_date, f"Source {index} date", errors)
        sources.append(
            {
                "title": title,
                "url": url,
                "source_date": parsed_date.isoformat() if parsed_date else "",
            }
        )
    return sources


def save_import_source(asset, data):
    sources = asset.sources.filter(title=data["title"])
    source = sources.filter(url=data["url"]).first()
    if source is None:
        source = (
            sources.first() if sources.count() == 1 else Source(asset=asset, title=data["title"])
        )
    source.url = data["url"]
    source.source_date = date.fromisoformat(data["source_date"]) if data["source_date"] else None
    source.verification_status = "unreviewed"
    source.last_verified_at = None
    # Existing source visibility and manual decisions stay intact for the same URL.
    source.save()


def parse_csv(upload):
    text = upload.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), strict=True)
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        return [], [f"Missing required column(s): {', '.join(sorted(missing))}"]
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        return [], ["CSV column names must be unique."]

    rows = []
    seen_assets = set()
    file_errors = []
    valid_record_types = {value for value, _label in Asset.RecordType.choices}
    valid_location_precisions = {value for value, _label in Asset.LocationPrecision.choices}
    valid_activity_statuses = {value for value, _label in Asset.ActivityStatus.choices}
    valid_development_statuses = {value for value, _label in Asset.DevelopmentStatus.choices}
    for number, raw in enumerate(reader, start=2):
        row = {key: (value or "").strip() for key, value in raw.items() if key is not None}
        errors = []
        if None in raw:
            errors.append(
                "This row has more values than the CSV header; quote values containing commas."
            )
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
        validate_url(row.get("activity_source_url", ""), "Activity source URL", errors)
        validate_url(row.get("development_source_url", ""), "Development source URL", errors)
        if row.get("activity_status") and row["activity_status"] not in valid_activity_statuses:
            errors.append("Activity status is invalid.")
        if (
            row.get("development_status")
            and row["development_status"] not in valid_development_statuses
        ):
            errors.append("Development status is invalid.")
        if row.get("available_acreage"):
            try:
                acreage = Decimal(row["available_acreage"])
                if not acreage.is_finite():
                    errors.append("Available acreage must be finite.")
                elif acreage < 0:
                    errors.append("Available acreage cannot be negative.")
            except InvalidOperation:
                errors.append("Available acreage must be numeric.")
        parse_iso_date(row.get("activity_last_verified_at", ""), "Activity review date", errors)
        parse_iso_date(
            row.get("development_last_verified_at", ""),
            "Development review date",
            errors,
        )
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
        asset_id = str(asset.pk) if asset else ""
        identity = asset_id or (row["name"].casefold(), row.get("city", "").casefold())
        if identity in seen_assets:
            errors.append("This asset occurs more than once in the CSV.")
        seen_assets.add(identity)
        try:
            prepare_import_asset(row, asset)
        except ValidationError as error:
            errors.extend(error.messages)
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
