"""Fill missing airport labels without changing reviewed asset data."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assets.models import Asset, AssetReviewComment

MARKER = "Airport display name backfill: 2026-09-07"


class Command(BaseCommand):
    help = "Fill blank catalog-airport display names, preserving custom names and review decisions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--catalog", type=Path, default=settings.BASE_DIR / "data/virginia_real_assets.json"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        records = json.loads(options["catalog"].read_text())["records"]
        updated = skipped = 0
        for record in records:
            label = record.get("display_name", "").strip()
            if record.get("provenance") != "faa-public-airport" or not label:
                continue
            matches = list(Asset.objects.select_for_update().filter(name=record["name"]))
            if len(matches) != 1:
                skipped += 1
                continue
            asset = matches[0]
            if (
                asset.display_name
                or asset.internal_notes != "Catalog provenance: faa-public-airport."
                or asset.visibility != Asset.Visibility.PUBLIC
                or asset.status not in Asset.public_status_values()
                or asset.review_comments.filter(body__startswith=MARKER).exists()
            ):
                skipped += 1
                continue
            # This intentionally includes reviewed records: only a blank presentation label changes.
            asset.display_name = label
            asset._change_reason = "Filled missing public airport display name."
            asset.save(update_fields=["display_name"])
            AssetReviewComment.objects.create(
                asset=asset,
                body=(
                    f"{MARKER}\nFilled the missing public display name with '{label}'. "
                    "Catalog identity, URL, data fields and review decisions are unchanged."
                ),
            )
            updated += 1
        self.stdout.write(f"Airport display names filled: {updated}; unchanged/skipped: {skipped}.")
