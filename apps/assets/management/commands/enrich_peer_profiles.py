"""Apply source-backed profile improvements to untouched peer-preview records."""

import hashlib
import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assets.geography import BY_CODE
from apps.assets.management.commands.apply_catalog_corrections import (
    history_reason,
    protected_source_history,
    same_value,
)
from apps.assets.models import Asset, AssetReviewComment
from apps.sources.models import Source

FIELDS = {
    "overview", "short_description", "unmanned_systems_relevance", "website_url",
    "contact_text", "contact_url", "contact_email", "contact_phone",
    "test_aircraft", "test_dimensions", "test_access", "test_source_url",
    "test_last_verified_at", "test_runway_length_ft",
}


class Command(BaseCommand):
    help = "Preview or apply exact-baseline peer profiles without replacing staff edits."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--profiles", type=Path, default=(
            settings.BASE_DIR / "data/multistate/profiles_2026_11_24.json"
        ))

    @transaction.atomic
    def handle(self, *args, **options):
        document = json.loads(options["profiles"].read_text())
        checked = date.fromisoformat(document["research_date"])
        changed = preserved = current = 0
        for item in document["profiles"]:
            before, after = item["before"], item["after"]
            if (item["state"] not in BY_CODE or item["state"] == "VA"
                    or not before or set(before) != set(after) or not set(after) <= FIELDS
                    or not item.get("sources")):
                raise CommandError(
                    "Peer profiles require supported fields, baselines and evidence."
                )
            sources = [Source(title=source["title"], url=source["url"],
                              notes=source["supports"], is_public=True)
                       for source in item["sources"]]
            for source in sources:
                if not source.url or not source.notes:
                    raise CommandError("Each profile source requires a URL and supported claims.")
                source.full_clean(exclude=["asset"])
            asset = Asset.objects.select_for_update().filter(
                state=item["state"], name=item["name"], benchmark_starter=True,
                visibility=Asset.Visibility.INTERNAL, status=Asset.Status.SOURCE_BACKED,
            ).first()
            if not asset or (
                asset.reviewed_by_id or asset.reviewed_at or asset.last_verified_at
                or asset.review_assignee_id or asset.review_due_at
                or asset.history.filter(history_user_id__isnull=False).exists()
                or asset.review_comments.filter(author_id__isnull=False).exists()
                or Source.history.filter(asset_id=asset.pk, history_user_id__isnull=False).exists()
            ):
                preserved += 1
                continue
            marker = "Peer profile enrichment: " + hashlib.sha256(
                json.dumps(item, sort_keys=True).encode()
            ).hexdigest()[:20]
            if asset.review_comments.filter(body__startswith=marker).exists():
                current += 1
                continue
            if not all(same_value(getattr(asset, key), value) for key, value in before.items()):
                preserved += 1
                continue
            conflict = False
            for source in sources:
                matches = list(asset.sources.filter(url=source.url))
                if (len(matches) > 1
                        or protected_source_history(asset, source.url, current_exists=bool(matches))
                        or matches and (not matches[0].is_public
                                        or matches[0].verification_status != "unreviewed"
                                        or matches[0].link_review_status != "automatic")):
                    conflict = True
                    break
            if conflict:
                preserved += 1
                continue
            for key, value in after.items():
                setattr(asset, key, asset._meta.get_field(key).to_python(value))
            asset.full_clean()
            if options["apply"]:
                reason = "Official-source peer capability and access enrichment"
                asset._change_reason = history_reason(asset, reason)
                asset.save(update_fields=[*after, "updated_at"])
                for source in sources:
                    asset.sources.get_or_create(url=source.url, defaults={
                        "title": source.title, "notes": f"Research {checked}: {source.notes}",
                        "is_public": True, "verification_status": "unreviewed",
                    })
                AssetReviewComment.objects.create(asset=asset, body=(
                    f"{marker}\nResearch {checked}. {reason}. "
                    "No editorial or operator verification implied.\n" +
                    "\n".join(source.url for source in sources)
                ))
            changed += 1
        self.stdout.write(
            f"{'Enriched' if options['apply'] else 'Would enrich'} {changed} peer profiles; "
            f"{current} already applied; preserved {preserved} absent or edited records."
        )
