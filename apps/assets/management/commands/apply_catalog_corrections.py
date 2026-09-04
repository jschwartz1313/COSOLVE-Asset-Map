"""Apply reviewed catalog changes only while their original values still match."""

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assets.models import Asset, AssetReviewComment
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source

PREFIX = "Catalog correction:"
CONFLICT_PREFIX = "Catalog correction conflict:"
TAXONOMY_FIELDS = {
    "capabilities": Capability,
    "missions": MissionArea,
    "platform_domains": PlatformDomain,
    "strategic_categories": StrategicCategory,
}
ALLOWED_FIELDS = {
    "address_line",
    "city",
    "postal_code",
    "latitude",
    "longitude",
    "location_precision",
    "region",
    "website_url",
    "contact_url",
    "contact_text",
    "contact_phone",
    "contact_email",
    "overview",
    "short_description",
    "unmanned_systems_relevance",
    "activity_source_url",
    "activity_status",
    "current_activity",
    "activity_last_verified_at",
}


def same_value(current, expected):
    if isinstance(current, date):
        return current.isoformat() == expected
    if isinstance(current, list) and isinstance(expected, list):
        return sorted(current) == sorted(expected)
    if isinstance(current, Decimal):
        try:
            return current == Decimal(str(expected)).quantize(Decimal("0.000001"))
        except (InvalidOperation, TypeError, ValueError):
            return False
    return current == expected or current in (None, "") and expected in (None, "")


def current_value(asset, field):
    if field in TAXONOMY_FIELDS:
        return list(getattr(asset, field).values_list("name", flat=True))
    return asset.region.name if field == "region" and asset.region_id else getattr(asset, field)


def protected_asset(asset):
    return bool(
        asset.visibility != Asset.Visibility.PUBLIC
        or asset.status not in Asset.public_status_values()
        or asset.reviewed_by_id
        or asset.review_assignee_id
        or asset.review_due_at
        or asset.history.filter(history_user_id__isnull=False).exists()
        or asset.review_comments.filter(author_id__isnull=False).exists()
    )


def history_reason(instance, reason):
    maximum = instance.history.model._meta.get_field("history_change_reason").max_length
    return reason[:maximum] if maximum else reason


def review_required_names():
    path = settings.BASE_DIR / "data" / "asset_corrections_2026_09_04.json"
    if not path.exists():
        return set()
    return {
        item["name"]
        for item in json.loads(path.read_text()).get("corrections", [])
        if item.get("review_required")
    }


class Command(BaseCommand):
    help = "Apply baseline-guarded catalog corrections without replacing later staff edits."

    def add_arguments(self, parser):
        parser.add_argument(
            "--corrections",
            type=Path,
            default=settings.BASE_DIR / "data" / "asset_corrections_2026_09_04.json",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        manifest = json.loads(options["corrections"].read_text())
        final_values = {}
        for item in manifest.get("corrections", []):
            final_values.setdefault(item["name"], {}).update(item.get("after", {}))
        applied = skipped = 0
        for item in manifest.get("corrections", []):
            before, after = item.get("before", {}), item.get("after", {})
            if set(before) != set(after) or not set(after) <= ALLOWED_FIELDS | set(TAXONOMY_FIELDS):
                raise CommandError(f"Invalid correction fields for {item['name']}")
            accepted_baselines = item.get("accepted_baselines", [])
            if not isinstance(accepted_baselines, list) or any(
                not isinstance(baseline, dict) or set(baseline) != set(before)
                for baseline in accepted_baselines
            ):
                raise CommandError(f"Invalid accepted baselines for {item['name']}")
            matches = list(Asset.objects.select_for_update().filter(name=item["name"]))
            if len(matches) != 1:
                skipped += 1
                continue
            asset = matches[0]
            if (
                asset.internal_notes != f"Catalog provenance: {item['provenance']}."
                or protected_asset(asset)
            ):
                skipped += 1
                continue
            identity = {name: value for name, value in item.items() if name != "accepted_baselines"}
            key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
            marker = f"{PREFIX} {key}"
            if asset.review_comments.filter(body__startswith=marker).exists():
                continue
            # Treat location/text groups atomically: never combine staff and catalog coordinates.
            baseline_matches = any(
                all(
                    same_value(current_value(asset, field), value)
                    for field, value in baseline.items()
                )
                for baseline in [before, *accepted_baselines]
            )
            already_current = all(
                same_value(current_value(asset, field), final_values[item["name"]][field])
                for field in after
            )
            if not baseline_matches and not already_current:
                conflict_marker = f"{CONFLICT_PREFIX} {key}"
                if not asset.review_comments.filter(body__startswith=conflict_marker).exists():
                    AssetReviewComment.objects.create(
                        asset=asset,
                        body=(
                            f"{conflict_marker}\n"
                            "Preserved values that differ from the correction baseline."
                        ),
                    )
                skipped += 1
                continue
            replacements = []
            source_conflict = False
            for replacement in item.get("replace_sources", []):
                old_matches = list(
                    asset.sources.select_for_update().filter(url=replacement["old_url"])
                )
                if (
                    len(old_matches) > 1
                    or Source.history.filter(
                        asset_id=asset.pk,
                        url=replacement["old_url"],
                        history_type="-",
                        history_user_id__isnull=False,
                    ).exists()
                ):
                    source_conflict = True
                    break
                old = old_matches[0] if old_matches else None
                if (
                    old is None
                    and not asset.sources.filter(url=replacement["source"]["url"]).exists()
                ):
                    source_conflict = True
                    break
                if old and (
                    old.notes != f"Catalog provenance: {item['provenance']}"
                    or not old.is_public
                    or old.history.filter(history_user_id__isnull=False).exists()
                ):
                    source_conflict = True
                    break
                replacements.append((old, replacement["source"]))
            # Do not expose a replacement that a staff member has deliberately hidden/rejected.
            new_sources = item.get("add_sources", []) + [x[1] for x in replacements]
            for data in new_sources:
                existing_matches = list(asset.sources.select_for_update().filter(url=data["url"]))
                if (
                    len(existing_matches) > 1
                    or Source.history.filter(
                        asset_id=asset.pk,
                        url=data["url"],
                        history_type="-",
                        history_user_id__isnull=False,
                    ).exists()
                ):
                    source_conflict = True
                    break
                existing = existing_matches[0] if existing_matches else None
                if existing and (
                    not existing.is_public
                    or existing.verification_status in {"stale", "rejected"}
                    or existing.link_review_status == Source.LinkReviewStatus.NEEDS_REPLACEMENT
                ):
                    source_conflict = True
            if source_conflict:
                conflict_marker = f"{CONFLICT_PREFIX} {key}"
                if not asset.review_comments.filter(body__startswith=conflict_marker).exists():
                    AssetReviewComment.objects.create(
                        asset=asset,
                        body=(
                            f"{conflict_marker}\n"
                            "Preserved an ambiguous or staff-managed source decision."
                        ),
                    )
                skipped += 1
                continue
            changed_values = after if baseline_matches else {}
            for field, value in changed_values.items():
                if field in TAXONOMY_FIELDS:
                    continue
                if field == "region":
                    asset.region = Region.objects.get(name=value)
                elif field == "activity_last_verified_at":
                    asset.activity_last_verified_at = date.fromisoformat(value) if value else None
                else:
                    setattr(asset, field, value)
            scalar_fields = set(changed_values) - set(TAXONOMY_FIELDS)
            if item.get("review_required"):
                asset.status = Asset.Status.SOURCE_BACKED
                asset.last_verified_at = None
                asset.reviewed_at = None
                asset.reviewed_by = None
                asset.published_at = None
                if asset.review_priority == Asset.ReviewPriority.NORMAL:
                    asset.review_priority = Asset.ReviewPriority.HIGH
                if not asset.review_notes:
                    asset.review_notes = item["reason"]
                scalar_fields.update(
                    {
                        "status",
                        "last_verified_at",
                        "reviewed_at",
                        "reviewed_by",
                        "published_at",
                        "review_priority",
                        "review_notes",
                    }
                )
            if scalar_fields:
                asset._change_reason = history_reason(asset, item["reason"])
                asset.save(update_fields=[*scalar_fields, "updated_at"])
            for field in set(changed_values) & set(TAXONOMY_FIELDS):
                model = TAXONOMY_FIELDS[field]
                getattr(asset, field).set([model.objects.get(name=name) for name in after[field]])
            for data in new_sources:
                asset.sources.get_or_create(
                    url=data["url"],
                    defaults={
                        "title": data["title"],
                        "is_public": True,
                        "notes": f"Catalog provenance: {item['provenance']}",
                    },
                )
            for old, data in replacements:
                if old and old.url != data["url"]:
                    # Retain the obsolete record and its history for staff instead of deleting it.
                    old.is_public = False
                    old.verification_status = "stale"
                    old.link_review_status = Source.LinkReviewStatus.NEEDS_REPLACEMENT
                    old.link_review_notes = (
                        f"Superseded on {manifest['reviewed_at']}: {data['url']}"
                    )
                    old._change_reason = history_reason(old, item["reason"])
                    old.save()
            AssetReviewComment.objects.create(
                asset=asset,
                body=f"{marker}\n{manifest['reviewed_at']}: {item['reason']}",
            )
            for conflict in asset.review_comments.filter(
                body__startswith=f"{CONFLICT_PREFIX} {key}\n",
                author_id__isnull=True,
            ):
                conflict.body = (
                    conflict.body.replace(
                        CONFLICT_PREFIX,
                        "Catalog correction conflict resolved:",
                        1,
                    )
                    + f"\nResolved after successful correction on {manifest['reviewed_at']}."
                )
                conflict.save(update_fields=["body"])
            applied += 1
        self.stdout.write(f"Applied {applied} catalog corrections; preserved {skipped} conflicts.")
