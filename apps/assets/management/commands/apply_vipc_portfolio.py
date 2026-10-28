"""Attach evidenced VIPC affiliations without replacing staff-maintained profiles."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assets.management.commands.apply_catalog_corrections import protected_source_history
from apps.assets.models import Asset, AssetReviewComment
from apps.sources.models import Source

MARKER = "VIPC portfolio affiliation: 2026-10-28"


class Command(BaseCommand):
    help = "Add sourced VIPC portfolio tags while preserving profiles, reviews and retired tags."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            type=Path,
            default=settings.BASE_DIR / "data/vipc_portfolio_2026_10_28.json",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        members = json.loads(options["manifest"].read_text())["memberships"]
        names = set()
        for item in members:
            source = item["source"]
            if (
                item["name"] in names
                or item["sector"] not in Asset.VipcPortfolioSector.values
                or urlsplit(source["url"]).hostname != "vipc.org"
            ):
                raise CommandError("Invalid or duplicate VIPC portfolio membership.")
            names.add(item["name"])
        tagged = attached = skipped = 0
        for item in members:
            asset = Asset.objects.select_for_update().filter(name=item["name"]).first()
            if (
                asset is None
                or asset.visibility != Asset.Visibility.PUBLIC
                or asset.status not in Asset.public_status_values()
            ):
                skipped += 1
                continue
            previous = asset.review_comments.filter(body__startswith=MARKER).exists()
            if (previous and not asset.vipc_portfolio_sector) or (
                asset.vipc_portfolio_sector not in ("", item["sector"])
            ):
                skipped += 1
                continue
            evidence = item["source"]
            source = asset.sources.filter(url=evidence["url"]).first()
            if (
                source
                and (
                    not source.is_public
                    or source.verification_status in {"rejected", "stale"}
                    or source.has_link_issue
                )
            ) or protected_source_history(
                asset, evidence["url"], current_exists=source is not None
            ):
                skipped += 1
                continue
            if source is None:
                Source.objects.create(
                    asset=asset,
                    title=evidence["title"],
                    url=evidence["url"],
                    notes=(
                        "VIPC portfolio evidence reviewed 2026-10-28. May represent a grant "
                        "recipient rather than an equity investment. Affiliation identifies the "
                        "represented organization, not a site-specific award or approval."
                    ),
                )
                attached += 1
            if not asset.vipc_portfolio_sector:
                asset.vipc_portfolio_sector = item["sector"]
                asset._change_reason = "Added source-backed VIPC portfolio affiliation"
                asset.save(update_fields=["vipc_portfolio_sector", "updated_at"])
                tagged += 1
            if not previous:
                AssetReviewComment.objects.create(
                    asset=asset,
                    body=(
                        f"{MARKER}\n{evidence['url']}\n"
                        "Added portfolio metadata only; existing review and publication "
                        "decisions were retained. Clearing the tag will not be undone on replay."
                    ),
                )
        self.stdout.write(
            f"Tagged {tagged} VIPC records; attached {attached} sources; "
            f"preserved/skipped {skipped}."
        )
