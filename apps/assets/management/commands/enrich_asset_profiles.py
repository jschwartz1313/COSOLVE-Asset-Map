import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assets.models import Asset
from apps.sources.models import Source

PROFILE_FIELDS = (
    "overview",
    "contact_text",
    "contact_phone",
    "contact_email",
    "contact_url",
)
LEGACY_DESCRIPTIONS = {
    "Public degree-granting community college serving Virginia students and employers.",
    "Public degree-granting college or university in Virginia.",
    "Private nonprofit degree-granting college or university in Virginia.",
    "Private degree-granting university included in SCHEV statewide completion reporting.",
}


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
        for record in records:
            asset = Asset.objects.filter(name=record["name"]).first()
            if asset is None:
                continue

            changed_fields = []
            for field in PROFILE_FIELDS:
                if not getattr(asset, field) and record.get(field):
                    setattr(asset, field, record[field])
                    changed_fields.append(field)

            legacy_airport_description = asset.short_description.startswith(
                "Operational public-use Virginia aviation facility (FAA identifier "
            )
            if asset.short_description in LEGACY_DESCRIPTIONS or legacy_airport_description:
                asset.short_description = record["short_description"]
                changed_fields.append("short_description")

            if record["provenance"] == "faa-public-airport":
                for field in ("address_line", "postal_code"):
                    if not getattr(asset, field) and record.get(field):
                        setattr(asset, field, record[field])
                        changed_fields.append(field)

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

        self.stdout.write(
            self.style.SUCCESS(
                f"Enriched {updated_assets} existing assets and added "
                f"{added_sources} public sources."
            )
        )
