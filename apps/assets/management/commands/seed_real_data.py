import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.assets.models import Asset, Relationship
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
            asset, was_created = Asset.objects.get_or_create(
                name=record["name"],
                city=record["city"],
                defaults={
                    "record_type": record["record_type"],
                    "short_description": record["short_description"],
                    "unmanned_systems_relevance": record["unmanned_systems_relevance"],
                    "latitude": record["latitude"],
                    "longitude": record["longitude"],
                    "location_precision": record["location_precision"],
                    "region": region,
                    "status": Asset.Status.PUBLISHED,
                    "visibility": Asset.Visibility.PUBLIC,
                },
            )
            for field in (
                "record_type",
                "short_description",
                "unmanned_systems_relevance",
                "latitude",
                "longitude",
                "location_precision",
            ):
                setattr(asset, field, record[field])
            asset.website_url = record.get("website_url", "")
            asset.state = record.get("state", "VA")
            asset.region = region
            asset.internal_notes = f"Catalog provenance: {record['provenance']}."
            asset.save()
            for field, model in TAXONOMY_FIELDS.items():
                values = [model.objects.get_or_create(name=name)[0] for name in record[field]]
                getattr(asset, field).set(values)

            source_titles = {source_data["title"] for source_data in record["sources"]}
            asset.sources.filter(notes__startswith="Catalog provenance:").exclude(
                title__in=source_titles
            ).delete()
            for source_data in record["sources"]:
                source, source_created = Source.objects.get_or_create(
                    asset=asset,
                    title=source_data["title"],
                )
                source.url = source_data["url"]
                source.notes = f"Catalog provenance: {record['provenance']}"
                source.is_public = True
                if source_created:
                    source.verification_status = "unreviewed"
                    source.last_verified_at = None
                source.save()
            created += int(was_created)
            updated += int(not was_created)

        relationships_created = 0
        for relationship_data in catalog.get("relationships", []):
            from_asset = Asset.objects.get(name=relationship_data["from"])
            to_asset = Asset.objects.get(name=relationship_data["to"])
            _relationship, was_created = Relationship.objects.update_or_create(
                from_asset=from_asset,
                to_asset=to_asset,
                relationship_type=relationship_data["type"],
                defaults={"is_public": True},
            )
            relationships_created += int(was_created)

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
                f"created {relationships_created} relationships; removed {deleted} demo-related "
                f"and {pruned} stale catalog database objects."
            )
        )
