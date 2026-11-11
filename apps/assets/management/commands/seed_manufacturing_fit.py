"""Opt-in, insert-only manufacturing profiles for existing reviewed catalog assets."""

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assets.manufacturing import ManufacturingProfile
from apps.assets.models import Asset
from apps.assets.testing import evidence_usable
from apps.sources.models import Source

from .apply_catalog_corrections import protected_asset, protected_source_history

ASSET_KEYS = {"name", "city", "state", "record_type", "provenance"}
PROFILE_KEYS = {
    "processes", "materials", "service_modes", "access_types", "source_url", "reviewed_at", "notes"
}
SOURCE_KEYS = {"title", "url", "notes"}


def load_seed(path):
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(manifest, dict)
            or set(manifest) != {"schema_version", "records"}
            or manifest["schema_version"] != 1
            or not isinstance(manifest["records"], list)
        ):
            raise ValueError("Expected schema_version 1 and a records list")
        seen = set()
        records = []
        for item in manifest["records"]:
            if not isinstance(item, dict) or set(item) != {"asset", "profile", "source"}:
                raise ValueError("Each record requires asset, profile and source")
            for key, fields in (("asset", ASSET_KEYS), ("profile", PROFILE_KEYS),
                                ("source", SOURCE_KEYS)):
                if not isinstance(item[key], dict) or set(item[key]) != fields:
                    raise ValueError(f"Invalid {key} fields")
            identity, values, source = item["asset"], item["profile"].copy(), item["source"]
            if any(not isinstance(value, str) or not value.strip() for value in identity.values()):
                raise ValueError("Asset identity guards must be nonempty strings")
            if identity["name"] in seen:
                raise ValueError("Duplicate asset identity")
            seen.add(identity["name"])
            raw_date = values["reviewed_at"]
            values["reviewed_at"] = date.fromisoformat(raw_date)
            if values["reviewed_at"].isoformat() != raw_date:
                raise ValueError("Use an ISO YYYY-MM-DD source-review date")
            if source["url"] != values["source_url"]:
                raise ValueError("The source URL must match the profile URL exactly")
            if not isinstance(values["notes"], str) or not values["notes"].strip():
                raise ValueError("A public evidence-scope note is required")
            if any(not isinstance(value, str) or not value.strip() for value in source.values()):
                raise ValueError("Public source title, URL and scope notes are required")
            ManufacturingProfile(**values).full_clean(exclude=["asset"])
            Source(
                **source, is_public=True, verification_status="verified",
                last_verified_at=values["reviewed_at"],
            ).full_clean(exclude=["asset"])
            records.append((identity, values, source))
        return records
    except (OSError, ValueError, TypeError, ValidationError) as error:
        raise CommandError(f"Invalid manufacturing seed: {error}") from error


class Command(BaseCommand):
    help = "Preview or insert reviewed manufacturing profiles; never overwrite existing profiles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed", type=Path,
            default=settings.BASE_DIR / "data" / "manufacturing_fit_2026_11_11.json",
        )
        parser.add_argument("--apply", action="store_true", help="Write eligible new profiles.")
        parser.add_argument(
            "--add-missing-sources", action="store_true",
            help="Allow new public sources only when no current or retired source exists.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        records = load_seed(options["seed"])
        created = skipped = 0
        for identity, values, source_values in records:
            matches = list(Asset.objects.select_for_update().filter(name=identity["name"]))
            reason = "asset missing or ambiguous"
            if len(matches) == 1:
                asset = matches[0]
                reason = "asset identity changed or staff-managed"
                eligible = (
                    all(getattr(asset, key) == identity[key]
                        for key in ("city", "state", "record_type"))
                    and asset.internal_notes == f"Catalog provenance: {identity['provenance']}."
                    and asset.activity_status != "historical"
                    and not protected_asset(asset)
                )
                if eligible:
                    reason = "existing profile preserved"
                    if not ManufacturingProfile.objects.filter(asset=asset).exists():
                        url = values["source_url"]
                        current = asset.sources.filter(url=url).exists()
                        retired = protected_source_history(asset, url, current_exists=current)
                        supported = evidence_usable(asset, url, values["reviewed_at"])
                        reason = "source retired, missing, private or unusable"
                        can_add = not current and not retired and options["add_missing_sources"]
                        if not retired and (supported or can_add):
                            if options["apply"]:
                                if can_add:
                                    Source.objects.create(
                                        asset=asset, **source_values, is_public=True,
                                        verification_status="verified",
                                        last_verified_at=values["reviewed_at"],
                                    )
                                ManufacturingProfile.objects.create(asset=asset, **values)
                            created += 1
                            action = "Created" if options["apply"] else "Would create"
                            suffix = " (with new public source)" if can_add else ""
                            self.stdout.write(f"{action}: {asset.name}{suffix}")
                            continue
            skipped += 1
            self.stdout.write(f"Skipped: {identity['name']} ({reason})")
        action = "Created" if options["apply"] else "Preview: eligible"
        self.stdout.write(f"{action} {created}; skipped {skipped}. Existing profiles untouched.")
