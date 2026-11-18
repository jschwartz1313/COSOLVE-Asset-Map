import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from simple_history.utils import bulk_create_with_history

from apps.assets.geography import BY_CODE
from apps.assets.models import Asset
from apps.catalog.models import Capability, MissionArea, PlatformDomain, StrategicCategory
from apps.sources.models import Source

TAXONOMIES = {
    "strategic_categories": StrategicCategory,
    "platform_domains": PlatformDomain,
    "capabilities": Capability,
    "missions": MissionArea,
}
# Existing vocabulary not used by the Virginia seed, so absent on a clean live database.
ADDITIONAL_TAXONOMIES = {
    "strategic_categories": ("Digital, data, energy, and communications infrastructure",),
    "capabilities": ("Cybersecurity and resilient systems",),
    "missions": ("Intelligence, surveillance, and reconnaissance", "Mine countermeasures"),
}
TEXT_FIELDS = (
    "name",
    "record_type",
    "short_description",
    "overview",
    "unmanned_systems_relevance",
    "website_url",
    "city",
    "address_line",
    "postal_code",
    "contact_url",
    "contact_email",
    "contact_phone",
    "test_access",
    "location_source_url",
    "location_role",
    "search_aliases",
)


def locality_name(name):
    return re.sub(r"\s+(city|town|village|borough|CDP|municipality)$", "", name).casefold()


def load_records(paths):
    records = []
    seen = set()
    for path in paths:
        document = json.loads(path.read_text())
        research_date = date.fromisoformat(document["research_date"])
        for record in document["records"]:
            state = record.get("state")
            if state not in BY_CODE or state == "VA":
                raise CommandError(f"Unsupported peer state in {path.name}: {state}")
            identity = (state, record["name"].strip().casefold())
            if identity in seen:
                raise CommandError(f"Duplicate peer identity: {identity}")
            if not record.get("sources") or any(
                not source.get("url") or not source.get("supports") for source in record["sources"]
            ):
                raise CommandError(f"Missing claim-level source evidence: {record['name']}")
            seen.add(identity)
            records.append((record, research_date))
    return records


def insert_prepared_records(prepared, taxonomies):
    """Insert validated values in batches, including initial taxonomy history."""
    assets = Asset.objects.bulk_create([item[0] for item in prepared], batch_size=250)
    histories = Asset.history.bulk_history_create(
        assets, batch_size=250, default_change_reason="Public-source peer inventory import"
    )
    history_ids = {row.id: row.history_id for row in histories}
    for field_name, model in TAXONOMIES.items():
        requested = {name for _asset, record, _sources in prepared
                     for name in record.get(field_name, [])}
        for name in requested:
            if taxonomies[field_name][name].pk is None:
                item, _created = model.objects.get_or_create(name=name)
                taxonomies[field_name][name] = item
        field = Asset._meta.get_field(field_name)
        through = field.remote_field.through
        target_field = field.m2m_reverse_field_name() + "_id"
        links = []
        for asset, record, _sources in prepared:
            links.extend(through(asset_id=asset.pk, **{
                target_field: taxonomies[field_name][name].pk,
            }) for name in record.get(field_name, []))
        through.objects.bulk_create(links, batch_size=500)
        historical_through = getattr(Asset.history.model, field_name).model
        historical_through.objects.bulk_create([
            historical_through(
                history_id=history_ids[link.asset_id],
                **{item.attname: getattr(link, item.attname) for item in through._meta.fields},
            ) for link in links
        ], batch_size=500)
    sources = []
    for asset, _record, source_rows in prepared:
        for source in source_rows:
            source.asset = asset
            sources.append(source)
    bulk_create_with_history(
        sources, Source, batch_size=250,
        default_change_reason="Public-source peer inventory import",
    )


class Command(BaseCommand):
    help = "Preview or insert source-backed, internal-only benchmark state starter records."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--catalog", type=Path, action="append")

    @transaction.atomic
    def handle(self, *args, **options):
        root = settings.BASE_DIR / "data/multistate"
        paths = options["catalog"] or sorted(root.glob("*_starter.json"))
        if not paths:
            raise CommandError("No peer starter catalogs were found.")
        records = load_records(paths)
        self.stdout.write(f"Checking {len(records)} peer starter records.")
        self.stdout.flush()
        states = {record["state"] for record, _checked in records}
        identities = {
            (state, name.strip().casefold())
            for model in (Asset.objects, Asset.history)
            for state, name in model.filter(state__in=states).values_list("state", "name")
        }
        slugs = set(Asset.objects.values_list("slug", flat=True))
        taxonomies = {
            field: {item.name: item for item in model.objects.all()}
            for field, model in TAXONOMIES.items()
        }
        for field, names in ADDITIONAL_TAXONOMIES.items():
            for name in names:
                taxonomies[field].setdefault(name, TAXONOMIES[field](name=name))
        references = json.loads((root / "locality_references.json").read_text())
        geocode_path = root / "address_geocodes.json"
        geocodes = {
            (row["state"], row["name"], row["address_line"], row["city"], row["postal_code"]): row
            for row in (
                json.loads(geocode_path.read_text())["matches"] if geocode_path.exists() else []
            )
        }
        places = {}
        for place in references["places"]:
            places.setdefault((place["state"], locality_name(place["name"])), []).append(place)
        created = skipped = unmapped = 0
        prepared = []
        for record, research_date in records:
            state = record["state"]
            slug = slugify(f"{state}-{record['name']}")[:240]
            # Both existing staff edits and archived/deleted identities remain untouched.
            if (state, record["name"].strip().casefold()) in identities or slug in slugs:
                skipped += 1
                continue
            values = {field: record.get(field) or "" for field in TEXT_FIELDS}
            values.update(
                state=state,
                slug=slug,
                status=Asset.Status.SOURCE_BACKED,
                visibility=Asset.Visibility.INTERNAL,
                benchmark_starter=True,
            )
            precision = record.get("location_precision", "locality")
            latitude, longitude = record.get("latitude"), record.get("longitude")
            if (latitude is None) != (longitude is None):
                raise CommandError(f"Incomplete coordinate pair: {record['name']}")
            if precision == "regional" and latitude is not None:
                raise CommandError(f"Regional activity has a site point: {record['name']}")
            notes = record.get("research_notes", "")
            geocode = geocodes.get(
                (
                    state,
                    record["name"],
                    values["address_line"],
                    values["city"],
                    values["postal_code"],
                )
            )
            if (
                latitude is None
                and geocode
                and precision != "regional"
                and values["location_source_url"]
            ):
                latitude, longitude = geocode["latitude"], geocode["longitude"]
                precision = "approximate"
                values["location_method"] = Asset.LocationMethod.GEOCODED
                values["location_notes"] = (
                    "Published address geocoded using U.S. Census address ranges. "
                    "Approximate street position, not a surveyed facility point or entrance."
                )
            if latitude is None or longitude is None:
                matches = places.get((state, locality_name(values["city"])), [])
                if len(matches) == 1 and precision != "regional":
                    place = matches[0]
                    latitude, longitude = place["latitude"], place["longitude"]
                    precision = "locality"
                    values["location_source_url"] = references["source"]
                    values["location_method"] = Asset.LocationMethod.LOCALITY
                    values["location_notes"] = (
                        "Census representative locality point only, not a facility position. "
                        "A published address, where listed, has not yet been geocoded."
                    )
                else:
                    latitude = longitude = None
                    unmapped += 1
                    if values["location_source_url"]:
                        values["location_method"] = Asset.LocationMethod.UNMAPPED
                        values["location_notes"] = (
                            "No confirmed map point. See the source and "
                            "public location description."
                        )
            elif not values.get("location_method"):
                if not values["location_source_url"]:
                    raise CommandError(f"Coordinates need location evidence: {record['name']}")
                values["location_method"] = Asset.LocationMethod.PUBLISHED
                values["location_notes"] = (
                    "Published reference position; confirm site access with operator."
                )
            latitude = (
                Decimal(str(latitude)).quantize(Decimal("0.000001"))
                if latitude is not None
                else None
            )
            longitude = (
                Decimal(str(longitude)).quantize(Decimal("0.000001"))
                if longitude is not None
                else None
            )
            values.update(latitude=latitude, longitude=longitude, location_precision=precision)
            if record.get("location_notes"):
                values["location_notes"] = " ".join(filter(None, [
                    record["location_notes"], values.get("location_notes", ""),
                ]))
            if values.get("location_method"):
                values["location_last_verified_at"] = research_date
            if values["test_access"]:
                values["test_source_url"] = record["sources"][0]["url"]
                values["test_last_verified_at"] = research_date
            values["internal_notes"] = (
                f"Multistate starter: {state}; research {research_date}. "
                "Curated priority inventory, not an objective ranking. "
                "Public-source review is not a completed editorial or operator review. " + notes
            )
            asset = Asset(**values)
            try:
                # Cached identity checks and database constraints protect insert-only identities.
                asset.full_clean(validate_unique=False, validate_constraints=False)
                source_rows = [
                    Source(
                        asset=asset,
                        title=source["title"],
                        url=source["url"],
                        verification_status="unreviewed",
                        is_public=True,
                        notes=f"Research {research_date}: {source['supports']}",
                    )
                    for source in record["sources"]
                ]
                for source in source_rows:
                    source.full_clean(exclude=["asset"], validate_unique=False,
                                      validate_constraints=False)
            except ValidationError as exc:
                raise CommandError(f"Invalid peer asset {record['name']}: {exc}") from exc
            for field in TAXONOMIES:
                names = record.get(field, [])
                missing = set(names) - taxonomies[field].keys()
                if missing:
                    raise CommandError(f"Unknown {field} for {record['name']}: {sorted(missing)}")
                if len(names) != len(set(names)):
                    raise CommandError(f"Repeated {field} for {record['name']}")
            prepared.append((asset, record, source_rows))
            slugs.add(slug)
            created += 1
            if options["apply"] and created % 50 == 0:
                self.stdout.write(
                    f"Peer import progress: {created} records prepared in transaction."
                )
                self.stdout.flush()
        if options["apply"] and prepared:
            self.stdout.write(
                f"Writing {len(prepared)} validated records and their initial history."
            )
            self.stdout.flush()
            insert_prepared_records(prepared, taxonomies)
        mode = "Inserted" if options["apply"] else "Would insert"
        self.stdout.write(
            f"{mode} {created} internal peer assets; preserved {skipped}; "
            f"{unmapped} without a confirmed map point."
        )
