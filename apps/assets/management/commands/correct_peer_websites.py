"""Repair known imported links without changing staff-managed records."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction

from apps.assets.geography import BY_CODE
from apps.assets.management.commands.apply_catalog_corrections import protected_source_history
from apps.assets.models import Asset
from apps.sources.models import Source


class Command(BaseCommand):
    help = "Apply exact-baseline website repairs to untouched internal peer preview records."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument(
            "--corrections",
            type=Path,
            default=settings.BASE_DIR / "data/multistate/website_corrections_2026_11_18.json",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        document = json.loads(options["corrections"].read_text())
        changed = skipped = 0
        for correction in document["corrections"]:
            if (correction["state"] not in BY_CODE or correction["state"] == "VA"
                    or not correction.get("supports")):
                raise CommandError("Peer website corrections require peer geography and evidence.")
            if correction["new_url"]:
                URLValidator()(correction["new_url"])
            asset = (
                Asset.objects.select_for_update()
                .filter(
                    state=correction["state"],
                    name=correction["name"],
                    benchmark_starter=True,
                    visibility=Asset.Visibility.INTERNAL,
                    status=Asset.Status.SOURCE_BACKED,
                )
                .first()
            )
            if not asset or asset.website_url != correction["old_url"]:
                skipped += 1
                continue
            if (
                asset.reviewed_by_id
                or asset.review_assignee_id
                or asset.review_due_at
                or asset.history.filter(history_user_id__isnull=False).exists()
                or asset.review_comments.filter(author_id__isnull=False).exists()
                or Source.history.filter(asset_id=asset.pk, history_user_id__isnull=False).exists()
            ):
                skipped += 1
                continue
            existing = asset.sources.filter(url=correction["new_url"]).first()
            if protected_source_history(
                asset, correction["new_url"], current_exists=bool(existing)
            ) or (
                existing
                and (
                    not existing.is_public
                    or existing.verification_status != "unreviewed"
                    or existing.link_review_status != Source.LinkReviewStatus.AUTOMATIC
                )
            ):
                skipped += 1
                continue
            if options["apply"]:
                for field in (
                    "website_url",
                    "contact_url",
                ):
                    if getattr(asset, field) == correction["old_url"]:
                        setattr(asset, field, correction["new_url"])
                asset._change_reason = "Guarded peer website correction"
                asset.save()
                if correction["new_url"] and not existing:
                    Source.objects.create(
                        asset=asset,
                        title=correction["source_title"],
                        url=correction["new_url"],
                        notes=f"Research {document['research_date']}: {correction['supports']}",
                        verification_status="unreviewed",
                        is_public=True,
                    )
            changed += 1
        self.stdout.write(
            f"{'Corrected' if options['apply'] else 'Would correct'} {changed} peer websites; "
            f"preserved {skipped} absent, current or staff-managed records."
        )
