from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assets.diagrams import SiteDiagram
from apps.assets.models import Asset, AssetReviewComment
from apps.assets.profile_media import photo_manifest

MARKER = "Profile photograph import: 2026-11-19"


class Command(BaseCommand):
    help = "Add two sourced NASA profile photos once, preserving later staff decisions."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        manifest = photo_manifest()
        added = skipped = 0
        for entry in manifest["photos"]:
            asset = Asset.objects.select_for_update().filter(
                state=entry["state"], name=entry["asset_name"], visibility=Asset.Visibility.PUBLIC,
                status__in=Asset.public_status_values(),
            ).first()
            if not asset or AssetReviewComment.history.filter(
                asset_id=asset.pk, body__startswith=MARKER,
            ).exists() or asset.site_diagrams.filter(image_url=entry["image_url"]).exists() or (
                asset.site_diagrams.filter(image_kind=SiteDiagram.ImageKind.PHOTO).exists()
            ):
                skipped += 1
                continue
            if options["apply"]:
                SiteDiagram.objects.create(
                    asset=asset, image_kind=SiteDiagram.ImageKind.PHOTO,
                    **{field: entry[field] for field in
                       ("title", "image_url", "alt_text", "caption", "credit", "source_url")},
                    publication_approved=True,
                )
                AssetReviewComment.objects.create(asset=asset, body=(
                    f"{MARKER}\n{entry['credit']}\n{entry['source_url']}\n"
                    f"{manifest['permission_basis']}\n{manifest['permission_url']}\n"
                    "This does not verify the asset, current equipment, availability or access."
                ))
            added += 1
        self.stdout.write(
            f"{'Added' if options['apply'] else 'Would add'} {added} approved profile photographs; "
            f"preserved {skipped} absent or previously managed records."
        )
