import json
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.assets.models import Asset, AssetReviewComment, SavedView
from apps.imports.services import asset_csv_row, prepare_import_asset
from apps.sources.models import Source
from scripts.build_real_asset_catalog import apply_vipc_portfolio

MANIFEST = settings.BASE_DIR / "data/vipc_portfolio_2026_10_28.json"


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class VipcPortfolioTests(TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())
        self.members = self.manifest["memberships"]

    def apply(self):
        call_command("apply_vipc_portfolio", stdout=StringIO())

    def fixture(self, **overrides):
        values = dict(
            name="Adaptive Aerospace Group",
            record_type="organization",
            short_description="Staff-authored description.",
            overview="Keep this profile.",
            unmanned_systems_relevance="Staff-authored relevance.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            website_url="https://adaptiveaero.com/",
            last_verified_at=date(2026, 10, 1),
        )
        return Asset.objects.create(**(values | overrides))

    def test_manifest_completeness_and_catalog_rebuild(self):
        self.assertEqual(len(self.members), 39)
        self.assertEqual(len({m["name"] for m in self.members}), 39)
        self.assertEqual(len(self.manifest["records"]), 19)
        self.assertEqual(sum(m["sector"] == "aerospace" for m in self.members), 13)
        self.assertEqual(sum(m["sector"] == "autonomous-systems" for m in self.members), 26)
        catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        self.assertEqual(catalog["record_count"], len(catalog["records"]))
        records = {r["name"]: r for r in catalog["records"]}
        for member in self.members:
            record = records[member["name"]]
            self.assertEqual(record["vipc_portfolio_sector"], member["sector"])
            self.assertIn(member["source"]["url"], [s["url"] for s in record["sources"]])
        before = json.dumps(catalog, sort_keys=True)
        apply_vipc_portfolio(catalog["records"])
        self.assertEqual(before, json.dumps(catalog, sort_keys=True))
        sites = [r for r in self.manifest["records"] if r["latitude"] is not None]
        self.assertEqual(len(sites), 8)
        for record in sites:
            self.assertEqual(record["location_precision"], "site")
            self.assertIn("geocoding.geo.census.gov", record["location_source_url"])
            self.assertTrue(36.5 < record["latitude"] < 39.6)
            self.assertTrue(-83.8 < record["longitude"] < -75.1)
        for record in self.manifest["records"]:
            self.assertNotIn("vipc.org", record["website_url"])
            if record["name"] in {"LEAF", "Counter-Drone Research Corporation", "Eksdyne"}:
                self.assertEqual(record["website_url"], "")
                self.assertIsNone(record["latitude"])

    def test_new_records_validate_without_editorial_verification_or_invented_pins(self):
        call_command("seed_real_data", catalog=MANIFEST, add_missing=True, stdout=StringIO())
        self.assertEqual(Asset.objects.count(), 19)
        for asset in Asset.objects.all():
            asset.full_clean()
            self.assertTrue(asset.is_vipc_portfolio)
            self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
            self.assertFalse(asset.is_editorially_reviewed)
            self.assertIsNone(asset.last_verified_at)
            self.assertFalse(asset.sources.exclude(verification_status="unreviewed").exists())
        self.apply()
        counts = (Asset.history.count(), Source.history.count(), AssetReviewComment.objects.count())
        self.apply()
        self.assertEqual(
            counts,
            (
                Asset.history.count(),
                Source.history.count(),
                AssetReviewComment.objects.count(),
            ),
        )

    def test_existing_profiles_and_review_metadata_are_preserved(self):
        user = get_user_model().objects.create_user("reviewer")
        asset = self.fixture(reviewed_by=user)
        before = Asset.objects.values().get(pk=asset.pk)
        self.apply()
        asset.refresh_from_db()
        after = Asset.objects.values().get(pk=asset.pk)
        for field in before.keys() - {"vipc_portfolio_sector", "updated_at"}:
            self.assertEqual(before[field], after[field], field)
        self.assertEqual(asset.vipc_portfolio_sector, "autonomous-systems")
        self.assertEqual(asset.sources.count(), 1)
        self.assertEqual(asset.sources.get().verification_status, "unreviewed")
        counts = (asset.history.count(), asset.sources.count(), asset.review_comments.count())
        self.apply()
        self.assertEqual(
            counts,
            (
                asset.history.count(),
                asset.sources.count(),
                asset.review_comments.count(),
            ),
        )

    def test_private_archived_and_retired_tags_are_preserved(self):
        private = self.fixture(visibility=Asset.Visibility.INTERNAL)
        self.apply()
        private.refresh_from_db()
        self.assertEqual(private.vipc_portfolio_sector, "")
        self.assertFalse(private.sources.exists())
        private.visibility = Asset.Visibility.PUBLIC
        private.status = Asset.Status.ARCHIVED
        private.save()
        self.apply()
        private.refresh_from_db()
        self.assertEqual(private.vipc_portfolio_sector, "")
        private.status = Asset.Status.SOURCE_BACKED
        private.save()
        self.apply()
        private.refresh_from_db()
        self.assertTrue(private.is_vipc_portfolio)
        private.vipc_portfolio_sector = ""
        private.save()
        count = private.history.count()
        self.apply()
        private.refresh_from_db()
        self.assertEqual(private.vipc_portfolio_sector, "")
        self.assertEqual(count, private.history.count())

    def test_deleted_and_rejected_evidence_is_not_restored_or_promoted(self):
        asset = self.fixture()
        member = next(m for m in self.members if m["name"] == asset.name)
        source = Source.objects.create(
            asset=asset, **member["source"], verification_status="rejected"
        )
        self.apply()
        asset.refresh_from_db()
        self.assertFalse(asset.is_vipc_portfolio)
        source.delete()
        self.apply()
        asset.refresh_from_db()
        self.assertFalse(asset.is_vipc_portfolio)
        self.assertFalse(asset.sources.exists())

    def test_portfolio_filter_badge_api_csv_and_saved_view(self):
        member = self.fixture(vipc_portfolio_sector="autonomous-systems")
        self.fixture(name="Unrelated supplier")
        self.fixture(
            name="Private portfolio member",
            vipc_portfolio_sector="aerospace",
            visibility=Asset.Visibility.INTERNAL,
        )
        response = self.client.get(reverse("api:asset-geojson"), {"portfolio": "vipc"})
        data = response.json()
        self.assertEqual(data["result_count"], 1)
        self.assertEqual(
            data["features"][0]["properties"]["vipc_portfolio_sector"], "autonomous-systems"
        )
        self.assertEqual(
            self.client.get(
                reverse("api:asset-geojson"),
                {
                    "portfolio": "vipc",
                    "q": "unrelated",
                },
            ).json()["result_count"],
            0,
        )
        self.assertContains(
            self.client.get(member.get_absolute_url()), "VIPC portfolio organization"
        )
        self.assertContains(
            self.client.get(reverse("core:directory"), {"portfolio": "vipc"}), member.name
        )
        row = asset_csv_row(member)
        self.assertEqual(row["vipc_portfolio_sector"], "autonomous-systems")
        imported = prepare_import_asset(
            {
                "name": "Imported portfolio fixture",
                "record_type": "organization",
                "short_description": "Import fixture",
                "unmanned_systems_relevance": "Fixture",
                "vipc_portfolio_sector": "aerospace",
            }
        )
        self.assertTrue(imported.is_vipc_portfolio)
        owner = get_user_model().objects.create_user("owner")
        view = SavedView(owner=owner, name="VIPC", query_string="portfolio=vipc", view_type="map")
        view.full_clean()

    def test_unknown_sector_rejected_atomically(self):
        from django.core.management.base import CommandError

        self.fixture()
        self.members[-1]["sector"] = "unverified"
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps({"memberships": self.members}))
            with self.assertRaises(CommandError):
                call_command("apply_vipc_portfolio", manifest=path, stdout=StringIO())
        self.assertEqual(Asset.objects.get().vipc_portfolio_sector, "")
        self.assertFalse(Source.objects.exists())
