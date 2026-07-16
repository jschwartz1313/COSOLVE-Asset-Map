import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source

TAXONOMY_FIELDS = {
    "strategic_categories": StrategicCategory,
    "platform_domains": PlatformDomain,
    "capabilities": Capability,
    "missions": MissionArea,
}


class Command(BaseCommand):
    help = "Load the source-backed Virginia real-asset catalog."

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace-demo",
            action="store_true",
            help="Delete the clearly labeled fictional demo fixtures before loading real records.",
        )
        parser.add_argument(
            "--catalog",
            type=Path,
            default=settings.BASE_DIR / "data" / "virginia_real_assets.json",
            help="Path to the generated real-asset catalog JSON.",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Delete catalog-managed records that are no longer in the current catalog.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        catalog = json.loads(options["catalog"].read_text())
        records = catalog["records"]

        deleted = 0
        if options["replace_demo"]:
            deleted, _details = Asset.objects.filter(
                Q(name__startswith="Demo ")
                | Q(internal_notes__icontains="fictional development fixture")
            ).delete()

        created = 0
        updated = 0
        catalog_keys = {(record["name"], record["city"]) for record in records}
        for record in records:
            region, _ = Region.objects.get_or_create(
                name=record["region"], defaults={"region_type": "Virginia ecosystem region"}
            )
            verified_at = date.fromisoformat(
                max(
                    source.get("last_verified_at", catalog["generated_at"])
                    for source in record["sources"]
                )
            )
            asset, was_created = Asset.objects.update_or_create(
                name=record["name"],
                city=record["city"],
                defaults={
                    "record_type": record["record_type"],
                    "short_description": record["short_description"],
                    "unmanned_systems_relevance": record["unmanned_systems_relevance"],
                    "website_url": record.get("website_url", ""),
                    "state": record.get("state", "VA"),
                    "latitude": record["latitude"],
                    "longitude": record["longitude"],
                    "location_precision": record["location_precision"],
                    "region": region,
                    "status": Asset.Status.PUBLISHED,
                    "visibility": Asset.Visibility.PUBLIC,
                    "last_verified_at": verified_at,
                    "internal_notes": (
                        f"Catalog provenance: {record['provenance']}. "
                        f"Source snapshot verified {verified_at.isoformat()}."
                    ),
                },
            )
            for field, model in TAXONOMY_FIELDS.items():
                values = [model.objects.get_or_create(name=name)[0] for name in record[field]]
                getattr(asset, field).set(values)

            for source_data in record["sources"]:
                Source.objects.update_or_create(
                    asset=asset,
                    title=source_data["title"],
                    defaults={
                        "url": source_data["url"],
                        "last_verified_at": date.fromisoformat(
                            source_data.get("last_verified_at", catalog["generated_at"])
                        ),
                        "verification_status": "verified",
                        "notes": f"Catalog provenance: {record['provenance']}",
                        "is_public": True,
                    },
                )
            created += int(was_created)
            updated += int(not was_created)

        pruned = 0
        if options["prune"]:
            stale_ids = [
                asset.pk
                for asset in Asset.objects.filter(internal_notes__startswith="Catalog provenance:")
                if (asset.name, asset.city) not in catalog_keys
            ]
            if stale_ids:
                pruned, _details = Asset.objects.filter(pk__in=stale_ids).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(records)} real assets ({created} created, {updated} updated); "
                f"removed {deleted} demo-related and {pruned} stale catalog database objects."
            )
        )
