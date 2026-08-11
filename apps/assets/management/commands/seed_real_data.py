import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
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

LEGACY_CATALOG_NAMES = {
    "Fort Walker": "Fort A.P. Hill",
    "Fort Gregg-Adams": "Fort Lee",
    "Fort Barfoot": "Fort Pickett",
    "VCU ARVL Robotic Drone System": "VCU UAV Research Laboratory",
    "Ashland Police Department Drone Program": (
        "Town of Ashland First Responder UAS Capability"
    ),
    "Haymarket Police Department Drone Program": (
        "Town of Haymarket First Responder UAS Capability"
    ),
    "Madison County Sheriff's Office UAS Program": (
        "Madison County First Responder UAS Capability"
    ),
    "Occoquan Police Department Public Safety Drone Program": (
        "Town of Occoquan First Responder UAS Capability"
    ),
    "Radford City Police Department Drone Program": (
        "City of Radford First Responder UAS Capability"
    ),
    "Wise County Sheriff's Office Drone Program": (
        "Wise County First Responder UAS Capability"
    ),
    "Wythe County Sheriff's Office Drone Program": (
        "Wythe County First Responder UAS Capability"
    ),
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
        parser.add_argument(
            "--only-if-empty",
            action="store_true",
            help="Load the catalog only when the database contains no assets.",
        )
        parser.add_argument(
            "--add-missing",
            action="store_true",
            help="Create missing catalog records without changing existing assets or sources.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["add_missing"] and options["prune"]:
            raise CommandError("--add-missing cannot be combined with --prune.")

        if options["only_if_empty"] and Asset.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Skipped catalog initialization because the database already contains assets."
                )
            )
            return

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
        skipped = 0
        catalog_names = {record["name"] for record in records}
        for record in records:
            asset = Asset.objects.filter(name=record["name"]).first()
            legacy_name = LEGACY_CATALOG_NAMES.get(record["name"])
            if asset is None and legacy_name:
                asset = Asset.objects.filter(
                    name=legacy_name,
                    internal_notes__startswith="Catalog provenance:",
                ).first()
                if asset is not None:
                    asset.name = record["name"]
                    asset.save(update_fields=["name", "slug", "updated_at"])
            if options["add_missing"] and asset is not None:
                skipped += 1
                continue

            region, _ = Region.objects.get_or_create(
                name=record["region"], defaults={"region_type": "Virginia ecosystem region"}
            )
            was_created = asset is None
            if was_created:
                asset = Asset(
                    name=record["name"],
                    record_type=record["record_type"],
                    status=Asset.Status.SOURCE_BACKED,
                    visibility=Asset.Visibility.PUBLIC,
                )
            for field in (
                "record_type",
                "short_description",
                "overview",
                "unmanned_systems_relevance",
                "activity_status",
                "current_activity",
                "partnership_opportunities",
                "activity_source_url",
                "owner_operator",
                "development_status",
                "development_notes",
                "infrastructure_access",
                "development_source_url",
                "address_line",
                "city",
                "postal_code",
                "latitude",
                "longitude",
                "location_precision",
            ):
                setattr(asset, field, record.get(field, ""))
            asset.activity_last_verified_at = (
                date.fromisoformat(record["activity_last_verified_at"])
                if record.get("activity_last_verified_at")
                else None
            )
            asset.available_acreage = record.get("available_acreage")
            asset.development_last_verified_at = (
                date.fromisoformat(record["development_last_verified_at"])
                if record.get("development_last_verified_at")
                else None
            )
            asset.website_url = record.get("website_url", "")
            asset.contact_text = record.get("contact_text", "")
            asset.contact_phone = record.get("contact_phone", "")
            asset.contact_email = record.get("contact_email", "")
            asset.contact_url = record.get("contact_url", "")
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
                    defaults={
                        "url": source_data["url"],
                        "notes": f"Catalog provenance: {record['provenance']}",
                        "is_public": True,
                    },
                )
                url_changed = source.url != source_data["url"]
                source.url = source_data["url"]
                source.notes = f"Catalog provenance: {record['provenance']}"
                source.is_public = True
                if source_created or url_changed:
                    source.verification_status = "unreviewed"
                    source.last_verified_at = None
                    source.last_checked_at = None
                    source.http_status = None
                    source.check_error = ""
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
                if asset.name not in catalog_names
            ]
            if stale_ids:
                pruned, _details = Asset.objects.filter(pk__in=stale_ids).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(records)} real assets ({created} created, {updated} updated, "
                f"{skipped} preserved); "
                f"created {relationships_created} relationships; removed {deleted} demo-related "
                f"and {pruned} stale catalog database objects."
            )
        )
