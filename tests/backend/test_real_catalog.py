import json
from datetime import date
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset, Relationship
from apps.sources.models import Source


class RealCatalogFileTests(TestCase):
    def load_catalog(self):
        path = settings.BASE_DIR / "data" / "virginia_real_assets.json"
        return json.loads(path.read_text())

    def test_catalog_has_at_least_232_real_source_backed_records(self):
        catalog = self.load_catalog()
        records = catalog["records"]
        self.assertGreaterEqual(len(records), 232)
        self.assertEqual(catalog["record_count"], len(records))
        self.assertGreaterEqual(len(catalog["relationships"]), 90)
        self.assertFalse(any(record["name"].startswith("Demo ") for record in records))
        self.assertTrue(
            all(record["sources"] and record["unmanned_systems_relevance"] for record in records)
        )
        airport_regions = {
            record["name"]: record["region"]
            for record in records
            if record["provenance"] == "faa-public-airport"
        }
        self.assertEqual(airport_regions["Accomack County"], "Eastern Shore")
        self.assertEqual(airport_regions["Lynchburg Rgnl/Preston Glenn Fld"], "Lynchburg Region")
        self.assertEqual(airport_regions["Roanoke/Blacksburg Rgnl (Woodrum Fld)"], "Roanoke Valley")
        universities = [record for record in records if record["record_type"] == "university"]
        self.assertEqual(len(universities), 10)
        self.assertTrue(
            all(
                source.get("url", "").startswith("https://")
                for record in records
                for source in record["sources"]
            )
        )

    def test_catalog_seed_is_idempotent(self):
        catalog = self.load_catalog()
        call_command("seed_real_data", verbosity=0)
        first_record = catalog["records"][0]
        first_source = first_record["sources"][0]
        source = Source.objects.get(
            asset__name=first_record["name"],
            asset__city=first_record["city"],
            title=first_source["title"],
        )
        source.url = "https://example.test/obsolete"
        source.verification_status = "verified"
        source.last_verified_at = date(2026, 1, 1)
        source.http_status = 404
        source.check_error = "Old result"
        source.save()
        call_command("seed_real_data", verbosity=0)
        self.assertEqual(Asset.public.count(), catalog["record_count"])
        self.assertEqual(Relationship.objects.count(), len(catalog["relationships"]))
        self.assertGreaterEqual(Source.objects.count(), catalog["record_count"])
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())
        self.assertFalse(Source.objects.filter(last_verified_at__isnull=False).exists())
        source.refresh_from_db()
        self.assertEqual(source.url, first_source["url"])
        self.assertIsNone(source.http_status)
        self.assertEqual(source.check_error, "")
        self.assertFalse(Asset.objects.filter(name__startswith="Demo ").exists())
        self.assertEqual(Asset.public.filter(record_type=Asset.RecordType.UNIVERSITY).count(), 10)
        self.assertTrue(
            Relationship.objects.filter(
                from_asset__record_type=Asset.RecordType.UNIVERSITY,
                relationship_type=Relationship.RelationshipType.SUPPORTS,
            ).exists()
        )

    def test_only_if_empty_preserves_existing_database_edits(self):
        call_command("seed_real_data", verbosity=0)
        asset = Asset.objects.order_by("pk").first()
        asset.short_description = "Reviewed and corrected by a staff member."
        asset.save(update_fields=["short_description"])
        output = StringIO()

        call_command(
            "seed_real_data",
            prune=True,
            only_if_empty=True,
            stdout=output,
            verbosity=0,
        )

        asset.refresh_from_db()
        self.assertEqual(
            asset.short_description,
            "Reviewed and corrected by a staff member.",
        )
        self.assertIn("Skipped catalog initialization", output.getvalue())

    def test_only_if_empty_loads_a_new_database(self):
        catalog = self.load_catalog()

        call_command("seed_real_data", only_if_empty=True, verbosity=0)

        self.assertEqual(Asset.public.count(), catalog["record_count"])
