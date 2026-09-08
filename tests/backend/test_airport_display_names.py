import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.assets.management.commands.fill_airport_display_names import MARKER
from apps.assets.models import Asset, AssetReviewComment
from apps.imports.services import asset_csv_row


class AirportCatalogNameTests(SimpleTestCase):
    def test_all_airport_labels_identify_the_facility_without_raw_abbreviations(self):
        catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        airports = [r for r in catalog["records"] if r["provenance"] == "faa-public-airport"]
        self.assertEqual(len(airports), 64)
        for record in airports:
            with self.subTest(name=record["name"]):
                label = record["display_name"]
                self.assertTrue(label.endswith(("Airport", "Air Park", "Seaplane Base")))
                self.assertNotRegex(label, r"\b(?:Intl|Rgnl|Muni|Exec|Fld)\b")
        self.assertEqual(
            next(r["display_name"] for r in airports if r["name"] == "Mc Laughlin"),
            "McLaughlin Seaplane Base",
        )


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class AirportNameDeploymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_superuser("name-editor", password="test-only")

    def setUp(self):
        self.asset = Asset.objects.create(
            name="Accomack County",
            record_type="infrastructure",
            short_description="Staff-authored airport description.",
            unmanned_systems_relevance="Supporting aviation infrastructure.",
            search_aliases="Staff alias\nMFV",
            city="Melfa",
            latitude="37.646889",
            longitude="-75.761056",
            location_precision="exact",
            status="source-backed",
            visibility="public",
            internal_notes="Catalog provenance: faa-public-airport.",
            reviewed_by=self.editor,
            reviewed_at=timezone.now(),
        )
        self.asset._history_user = self.editor
        self.asset.save()
        AssetReviewComment.objects.create(
            asset=self.asset, author=self.editor, body="Staff review."
        )
        self.record = {
            "name": "Accomack County",
            "display_name": "Accomack County Airport",
            "provenance": "faa-public-airport",
        }

    def apply(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps({"records": [self.record]}))
            call_command("fill_airport_display_names", catalog=path, stdout=StringIO())
        self.asset.refresh_from_db()

    def test_reviewed_asset_gets_only_missing_label_and_retains_identity_and_review(self):
        before = Asset.objects.values().get(pk=self.asset.pk)
        self.apply()
        after = Asset.objects.values().get(pk=self.asset.pk)
        self.assertEqual(self.asset.public_name, "Accomack County Airport")
        self.assertEqual(
            {key for key in before if before[key] != after[key]}, {"display_name"}
        )
        self.assertEqual(self.asset.get_absolute_url(), "/assets/accomack-county/")
        self.assertTrue(self.asset.history.filter(display_name="").exists())
        self.assertEqual(self.asset.history.first().display_name, self.asset.public_name)
        self.assertEqual(self.asset.review_comments.filter(body__startswith=MARKER).count(), 1)
        # Staff CSVs keep catalog identity for re-import; public map exports use the GeoJSON label.
        self.assertEqual(
            asset_csv_row(self.asset, include_internal=True)["name"], "Accomack County"
        )

    def test_repeat_deploy_is_idempotent_and_respects_later_clearing(self):
        self.apply()
        count = self.asset.history.count()
        self.apply()
        self.assertEqual(self.asset.history.count(), count)
        self.asset.display_name = ""
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.display_name, "")

    def test_custom_names_unrelated_records_and_nonpublic_records_are_untouched(self):
        for changes in (
            {"display_name": "Staff-selected name"},
            {"visibility": "internal"},
            {"status": "archived"},
            {"internal_notes": "Custom record"},
        ):
            original = {field: getattr(self.asset, field) for field in changes}
            for field, value in changes.items():
                setattr(self.asset, field, value)
            self.asset.save()
            with self.subTest(changes=changes):
                before = Asset.objects.values().get(pk=self.asset.pk)
                self.apply()
                self.assertEqual(Asset.objects.values().get(pk=self.asset.pk), before)
            for field, value in original.items():
                setattr(self.asset, field, value)
            self.asset.save()
        self.record["provenance"] = "curated-public-source"
        self.apply()
        self.assertEqual(self.asset.display_name, "")

    def test_ambiguous_identity_is_not_updated(self):
        Asset.objects.create(
            name=self.asset.name, city="Another locality", record_type="infrastructure",
            short_description="Separate site", unmanned_systems_relevance="Infrastructure",
        )
        self.apply()
        self.assertEqual(self.asset.display_name, "")

    def test_names_are_consistent_in_public_pages_map_and_staff_interfaces(self):
        self.apply()
        for url in (self.asset.get_absolute_url(), reverse("core:directory")):
            self.assertContains(self.client.get(url), self.asset.public_name)
        geo = self.client.get(reverse("api:asset-geojson"), {"q": "MFV"}).json()
        self.assertEqual(geo["features"][0]["properties"]["name"], self.asset.public_name)
        self.assertEqual(str(self.asset), self.asset.public_name)
        self.client.force_login(self.editor)
        response = self.client.get(reverse("admin:assets_asset_changelist"))
        self.assertContains(response, f'>{self.asset.public_name}</a>', html=False)
        response = self.client.get(reverse("admin:assets_asset_change", args=[self.asset.pk]))
        self.assertContains(
            response, f"<title>{self.asset.public_name} | Change asset | COSOLVE Admin</title>"
        )
        self.assertContains(
            self.client.get(reverse("imports:data-quality")), self.asset.public_name
        )

    def test_admin_sort_and_search_use_the_public_label(self):
        self.apply()
        other = Asset.objects.create(
            name="AAA original", display_name="Zulu Airport", record_type="infrastructure",
            short_description="Airport", unmanned_systems_relevance="Infrastructure",
        )
        self.client.force_login(self.editor)
        response = self.client.get(reverse("admin:assets_asset_changelist"))
        self.assertEqual(list(response.context["cl"].result_list), [self.asset, other])
        response = self.client.get(
            reverse("admin:assets_asset_changelist"), {"q": "County Airport"}
        )
        self.assertEqual(list(response.context["cl"].result_list), [self.asset])
