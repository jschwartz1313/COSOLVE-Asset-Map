import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.assets.models import Asset, AssetReviewComment
from apps.sources.models import Source

REVIEW_COMMENT_PREFIX = "Catalog editorial review:"
FOLLOW_UP_COMMENT_PREFIX = "Catalog research follow-up:"


def review_key(reviewed_at, asset_name, evidence):
    payload = json.dumps(
        [reviewed_at.isoformat(), asset_name, evidence],
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class Command(BaseCommand):
    help = "Apply checked-in public-source reviews once while preserving later staff decisions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reviews",
            type=Path,
            default=settings.BASE_DIR / "data" / "asset_editorial_reviews.json",
            help="Path to the checked-in editorial review manifest.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        manifest = json.loads(options["reviews"].read_text())
        reviewed_on = date.fromisoformat(manifest["reviewed_at"])
        reviewed_at = timezone.make_aware(datetime.combine(reviewed_on, time(hour=12)))
        verified_assets = 0
        verified_sources = 0
        follow_ups = 0
        skipped = 0

        for asset_name, source_urls in manifest.get("reviewed_assets", {}).items():
            asset = Asset.objects.filter(name=asset_name).first()
            if asset is None or not asset.internal_notes.startswith("Catalog provenance:"):
                skipped += 1
                continue

            key = review_key(reviewed_on, asset_name, source_urls)
            marker = f"{REVIEW_COMMENT_PREFIX} {key}"
            if asset.review_comments.filter(body__startswith=marker).exists():
                continue
            if asset.reviewed_at is not None:
                skipped += 1
                continue

            sources = list(asset.sources.filter(is_public=True, url__in=source_urls))
            if {source.url for source in sources} != set(source_urls):
                missing = sorted(set(source_urls) - {source.url for source in sources})
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipped {asset_name}: missing reviewed source(s): {', '.join(missing)}"
                    )
                )
                skipped += 1
                continue

            for source in sources:
                source.verification_status = "verified"
                source.last_verified_at = reviewed_on
                source.link_review_status = Source.LinkReviewStatus.ACCEPTED
                source.link_review_notes = (
                    f"Official public source manually reviewed for the Tier 1 catalog audit "
                    f"on {reviewed_on:%Y-%m-%d}."
                )
                source._change_reason = "Source verified in the Tier 1 public-source audit."
                source.save()
                verified_sources += 1

            asset.status = Asset.Status.PUBLISHED
            asset.visibility = Asset.Visibility.PUBLIC
            asset.last_verified_at = reviewed_on
            asset.reviewed_at = reviewed_at
            asset.reviewed_by = None
            asset.review_assignee = None
            asset.review_due_at = None
            asset.review_priority = Asset.ReviewPriority.NORMAL
            if not asset.review_notes:
                asset.review_notes = (
                    "Tier 1 catalog review confirmed the record's identity, Virginia location, "
                    "and described unmanned-systems role against the listed official sources."
                )
            asset.published_at = asset.published_at or reviewed_at
            asset._change_reason = "Tier 1 editorial verification completed from official sources."
            asset.save()
            AssetReviewComment.objects.create(
                asset=asset,
                author=None,
                body=(
                    f"{marker}\nReviewed {reviewed_on:%Y-%m-%d}. Confirmed the named entity, "
                    "Virginia location, and described unmanned-systems role against: "
                    + ", ".join(source_urls)
                ),
            )
            verified_assets += 1

        for asset_name, reason in manifest.get("follow_up_assets", {}).items():
            asset = Asset.objects.filter(name=asset_name).first()
            if asset is None or not asset.internal_notes.startswith("Catalog provenance:"):
                skipped += 1
                continue
            key = review_key(reviewed_on, asset_name, reason)
            marker = f"{FOLLOW_UP_COMMENT_PREFIX} {key}"
            if asset.review_comments.filter(body__startswith=marker).exists():
                continue
            asset.review_priority = Asset.ReviewPriority.HIGH
            if not asset.review_notes:
                asset.review_notes = reason
            asset._change_reason = (
                "Operating agency remains unresolved after public-source research."
            )
            asset.save(update_fields=["review_priority", "review_notes", "updated_at"])
            AssetReviewComment.objects.create(
                asset=asset,
                author=None,
                body=f"{marker}\nReviewed {reviewed_on:%Y-%m-%d}. {reason}",
            )
            follow_ups += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Applied {verified_assets} Tier 1 asset reviews and {verified_sources} source "
                f"reviews; flagged {follow_ups} unresolved records; skipped {skipped}."
            )
        )
