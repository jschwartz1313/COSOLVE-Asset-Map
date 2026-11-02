import json
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from apps.assets.management.commands.enrich_asset_profiles import LOCATION_CONTEXT_FIELDS
from apps.assets.models import Asset


class ProfileEnrichmentLocationGuardsTests(TestCase):
    def test_atomic_location_corrections_precede_generic_enrichment(self):
        release = (settings.BASE_DIR / "release.sh").read_text()
        self.assertLess(
            release.index("--corrections data/asset_reference_profiles_2026_11_02.json"),
            release.index("python manage.py enrich_asset_profiles"),
        )

    def setUp(self):
        records = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        self.record = next(record for record in records["records"]
                           if record["name"] ==
                           "Thomas Jefferson National Accelerator Facility (Jefferson Lab)")
        self.asset = Asset.objects.create(
            name=self.record["name"],
            record_type=self.record["record_type"],
            short_description=self.record["short_description"],
            unmanned_systems_relevance=self.record["unmanned_systems_relevance"],
            status="source-backed",
            visibility="public",
            internal_notes=f"Catalog provenance: {self.record['provenance']}.",
            city="Newport News",
            location_precision="locality",
            location_method="unmapped",
            location_source_url="https://www.jlab.org/visiting",
            location_last_verified_at=date(2026, 11, 1),
        )

    def enrich(self, records):
        output, errors = StringIO(), StringIO()
        with TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text(json.dumps({"records": records}))
            call_command("enrich_asset_profiles", catalog=catalog, stdout=output, stderr=errors)
        return output.getvalue(), errors.getvalue()

    def test_reviewed_unmapped_location_is_not_partially_replaced(self):
        fields = (*LOCATION_CONTEXT_FIELDS, "latitude", "longitude", "address_line",
                  "city", "postal_code", "location_precision")
        original = {field: getattr(self.asset, field) for field in fields}
        self.enrich([self.record])
        self.asset.refresh_from_db()
        self.assertEqual({field: getattr(self.asset, field) for field in fields}, original)
        self.assertEqual(self.asset.overview, self.record["overview"])
        self.asset.full_clean()

    def test_existing_invalid_record_is_reported_without_partial_changes(self):
        Asset.objects.filter(pk=self.asset.pk).update(latitude="37.1", longitude="-76.5")
        valid_record = dict(self.record, name="Valid profile fixture")
        valid = Asset.objects.create(
            name=valid_record["name"], status="source-backed", visibility="public",
            record_type=valid_record["record_type"],
            short_description=valid_record["short_description"],
            unmanned_systems_relevance=valid_record["unmanned_systems_relevance"],
            internal_notes=f"Catalog provenance: {valid_record['provenance']}.",
        )
        history_count = self.asset.history.count()
        output, errors = self.enrich([self.record, valid_record])
        self.asset.refresh_from_db()
        valid.refresh_from_db()
        self.assertIn(self.asset.name, errors)
        self.assertIn("unmapped", errors)
        self.assertIn("skipped 1 invalid existing assets", output)
        self.assertEqual(self.asset.overview, "")
        self.assertEqual(self.asset.history.count(), history_count)
        self.assertFalse(self.asset.sources.exists())
        self.assertFalse(self.asset.strategic_categories.exists())
        self.assertEqual(valid.overview, valid_record["overview"])
        valid.full_clean()
