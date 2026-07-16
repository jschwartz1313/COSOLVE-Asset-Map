import csv
import io
from decimal import Decimal, InvalidOperation

from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory

REQUIRED_COLUMNS = {"name", "record_type", "short_description", "unmanned_systems_relevance"}
TAXONOMY_COLUMNS = {
    "strategic_categories": StrategicCategory,
    "platform_domains": PlatformDomain,
    "capabilities": Capability,
    "missions": MissionArea,
}


def split_values(value):
    return [item.strip() for item in value.split("|") if item.strip()]


def parse_csv(upload):
    text = upload.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        return [], [f"Missing required column(s): {', '.join(sorted(missing))}"]

    rows = []
    file_errors = []
    valid_record_types = {value for value, _label in Asset.RecordType.choices}
    for number, raw in enumerate(reader, start=2):
        row = {key: (value or "").strip() for key, value in raw.items()}
        errors = []
        if not row["name"]:
            errors.append("Name is required.")
        if row["record_type"] not in valid_record_types:
            errors.append("Record type is invalid.")
        if not row["short_description"]:
            errors.append("Short description is required.")
        if not row["unmanned_systems_relevance"]:
            errors.append("Unmanned systems relevance is required.")
        for coordinate in ("latitude", "longitude"):
            if row.get(coordinate):
                try:
                    Decimal(row[coordinate])
                except InvalidOperation:
                    errors.append(f"{coordinate.title()} must be numeric.")
        if bool(row.get("latitude")) != bool(row.get("longitude")):
            errors.append("Latitude and longitude must be provided together.")
        for column, model in TAXONOMY_COLUMNS.items():
            requested = split_values(row.get(column, ""))
            existing = set(model.objects.filter(slug__in=requested).values_list("slug", flat=True))
            missing_values = set(requested) - existing
            if missing_values:
                errors.append(f"Unknown {column}: {', '.join(sorted(missing_values))}")
        region_slug = row.get("region", "")
        if region_slug and not Region.objects.filter(slug=region_slug).exists():
            errors.append(f"Unknown region: {region_slug}")
        duplicate = Asset.objects.filter(
            name__iexact=row["name"], city__iexact=row.get("city", "")
        ).exists()
        rows.append({"number": number, "data": row, "errors": errors, "duplicate": duplicate})
    if not rows:
        file_errors.append("The CSV contains no data rows.")
    return rows, file_errors
