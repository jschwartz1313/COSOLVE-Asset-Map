import json

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset, Relationship
from apps.sources.models import Source


class RealCatalogFileTests(TestCase):
    def load_catalog(self):
        path = settings.BASE_DIR / "data" / "virginia_real_assets.json"
        return json.loads(path.read_text())

    def test_catalog_has_at_least_222_real_source_backed_records(self):
        catalog = self.load_catalog()
        records = catalog["records"]
        self.assertGreaterEqual(len(records), 222)
        self.assertEqual(catalog["record_count"], len(records))
        self.assertGreaterEqual(len(catalog["relationships"]), 90)
        self.assertFalse(any(record["name"].startswith("Demo ") for record in records))
        self.assertTrue(
            all(record["sources"] and record["unmanned_systems_relevance"] for record in records)
        )
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
        call_command("seed_real_data", verbosity=0)
        self.assertEqual(Asset.public.count(), catalog["record_count"])
        self.assertEqual(Relationship.objects.count(), len(catalog["relationships"]))
        self.assertGreaterEqual(Source.objects.count(), catalog["record_count"])
        self.assertFalse(Source.objects.exclude(verification_status="unreviewed").exists())
        self.assertFalse(Source.objects.filter(last_verified_at__isnull=False).exists())
        self.assertFalse(Asset.objects.filter(name__startswith="Demo ").exists())
