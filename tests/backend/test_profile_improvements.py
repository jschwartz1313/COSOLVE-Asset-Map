import json
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.api.query import filter_public_assets
from apps.api.search import search_terms
from apps.assets.discovery import IDENTITY_FIELDS, LOCATION_EVIDENCE_FIELDS
from apps.assets.models import Asset, Relationship
from apps.catalog.models import Capability, Region
from apps.imports.services import asset_csv_row, prepare_import_asset
from apps.sources.models import Source
from scripts.build_real_asset_catalog import apply_reviewed_corrections

MANIFEST = settings.BASE_DIR / "data/profile_improvements_2026_09_06.json"


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class PublicProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hampton Roads")
        cls.other_region = Region.objects.create(name="New River Valley")
        cls.asset = Asset.objects.create(
            name="Norfolk Intl",
            display_name="Norfolk International Airport",
            search_aliases="ORF\nNorfolk Airport",
            record_type="infrastructure",
            short_description="Aviation infrastructure",
            unmanned_systems_relevance="Supporting UAS research",
            city="Norfolk",
            region=cls.region,
            status="source-backed",
            visibility="public",
            latitude="36.89",
            longitude="-76.20",
            location_precision="site",
            location_role="airport",
            location_method="published",
            location_notes="Reference point, not an approved launch location.",
            location_source_url="https://example.org/airport",
            location_last_verified_at=date(2026, 9, 4),
        )
        cls.asset.capabilities.add(Capability.objects.create(name="Flight testing"))
        for title in ("Public certification", "Public training"):
            Source.objects.create(asset=cls.asset, title=title, url="https://example.org/source")
        Source.objects.create(
            asset=cls.asset,
            title="Confidential redcode",
            url="https://example.org/private",
            is_public=False,
        )
        cls.private = Asset.objects.create(
            name="Private partner",
            display_name="Hiddenname",
            search_aliases="Secretalias",
            record_type="organization",
            short_description="Private",
            unmanned_systems_relevance="Private",
            visibility="internal",
            status="verified",
        )
        Relationship.objects.create(
            from_asset=cls.asset,
            to_asset=cls.private,
            relationship_type="supports",
        )
        cls.partner = Asset.objects.create(
            name="Partner Rgnl",
            display_name="Regional Partner",
            record_type="organization",
            short_description="Partner",
            unmanned_systems_relevance="Partner",
            region=cls.other_region,
            status="source-backed",
            visibility="public",
        )
        Relationship.objects.create(
            from_asset=cls.asset,
            to_asset=cls.partner,
            relationship_type="supports",
        )

    def results(self, query, **filters):
        params = QueryDict(mutable=True)
        params.update({"q": query, **filters})
        return list(filter_public_assets(params).values_list("pk", flat=True))

    def test_public_name_and_location_context_are_consistent(self):
        for url in (self.asset.get_absolute_url(), reverse("core:directory")):
            self.assertContains(self.client.get(url), self.asset.public_name)
        detail = self.client.get(reverse("api:asset-detail", args=[self.asset.slug])).json()
        self.assertEqual(detail["name"], self.asset.public_name)
        self.assertEqual(detail["location"]["role"], "airport")
        self.assertEqual(detail["location"]["reviewed_at"], "2026-09-04")
        geo = self.client.get(reverse("api:asset-geojson"), {"q": "ORF"}).json()
        self.assertEqual(geo["features"][0]["properties"]["name"], self.asset.public_name)
        self.assertEqual(geo["features"][0]["properties"]["location"]["method"], "published")
        self.assertEqual(self.asset.slug, "norfolk-intl")
        self.assertEqual(self.asset.name, "Norfolk Intl")

    def test_words_can_match_different_fields_and_order_does_not_matter(self):
        for query in ("Norfolk testing", "testing Norfolk", "ORF infrastructure"):
            with self.subTest(query=query):
                self.assertEqual(self.results(query), [self.asset.pk])
        self.assertEqual(self.results("ORF missingword"), [])

    def test_words_can_match_different_public_sources_without_duplicates(self):
        self.assertEqual(self.results("certification training"), [self.asset.pk])

    def test_quoted_phrases_are_strict_and_unquoted_drone_terms_expand(self):
        self.assertEqual(self.results('"Norfolk testing"'), [])
        self.assertEqual(
            set(self.results('"Norfolk International"')), {self.asset.pk, self.partner.pk}
        )
        self.assertEqual(self.results("drone Norfolk"), [self.asset.pk])
        self.assertEqual(self.results('"drone" Norfolk'), [])

    def test_private_sources_assets_and_related_names_do_not_leak(self):
        for query in ("redcode", "Hiddenname", "Secretalias"):
            self.assertEqual(self.results(query), [])
        self.assertEqual(set(self.results("Regional Partner")), {self.asset.pk, self.partner.pk})

    def test_excluded_institutions_are_not_searchable_through_relations(self):
        excluded = Asset.objects.create(
            name="Sentara College of Health Sciences",
            record_type="university",
            short_description="Specialized institution",
            unmanned_systems_relevance="Excluded",
            status="source-backed",
            visibility="public",
        )
        Relationship.objects.create(
            from_asset=self.asset,
            to_asset=excluded,
            relationship_type="supports",
        )
        self.assertEqual(self.results("Sentara"), [])

    @override_settings(PUBLIC_REGION_SLUG="hampton-roads")
    def test_related_name_search_obeys_release_scope(self):
        self.assertEqual(self.results("Regional Partner"), [])
        self.assertEqual(self.results("ORF", region="new-river-valley"), [self.asset.pk])

    def test_name_matches_rank_before_incidental_mentions(self):
        mention = Asset.objects.create(
            name="Aardvark",
            record_type="organization",
            short_description="Norfolk Intl",
            unmanned_systems_relevance="Supporting aviation",
            status="source-backed",
            visibility="public",
        )
        self.assertEqual(self.results("Norfolk Intl"), [self.asset.pk, mention.pk, self.partner.pk])
        response = self.client.get(reverse("core:directory"), {"q": "Norfolk Intl"})
        self.assertEqual(response.context["sort_key"], "relevance")
        self.assertEqual(list(response.context["page_obj"])[0].pk, self.asset.pk)
        response = self.client.get(reverse("core:directory"), {"q": "Norfolk Intl", "sort": "name"})
        self.assertEqual(list(response.context["page_obj"])[0].pk, mention.pk)

    def test_exact_alias_ranks_before_an_incidental_description(self):
        mention = Asset.objects.create(
            name="Aardvark",
            record_type="organization",
            short_description="ORF infrastructure",
            unmanned_systems_relevance="Supporting aviation",
            status="source-backed",
            visibility="public",
        )
        self.assertEqual(self.results("ORF"), [self.asset.pk, mention.pk, self.partner.pk])

    def test_default_order_uses_display_name_and_plain_names_still_work(self):
        self.partner.display_name = "Airport Partner"
        self.partner.save()
        self.assertEqual(self.results(""), [self.partner.pk, self.asset.pk])
        self.partner.display_name = ""
        self.assertEqual(self.partner.public_name, "Partner Rgnl")

    def test_excessive_search_is_bounded_and_does_not_return_partial_matches(self):
        self.assertEqual(self.results("x" * 501), [])
        self.assertEqual(self.results(" ".join(f"word{i}" for i in range(17))), [])
        self.assertEqual(
            search_terms('"unclosed phrase'), [('"unclosed', False), ("phrase", False)]
        )

    def test_names_and_location_context_round_trip_without_renaming_catalog_identity(self):
        row = {
            key: str(value) if value is not None else ""
            for key, value in asset_csv_row(self.asset).items()
        }
        imported = prepare_import_asset(row, self.asset)
        for field in (*IDENTITY_FIELDS, *LOCATION_EVIDENCE_FIELDS):
            self.assertEqual(getattr(imported, field), getattr(self.asset, field))
        self.assertEqual(imported.name, "Norfolk Intl")
        self.assertEqual(imported.slug, "norfolk-intl")
        imported.save()
        self.assertEqual(imported.history.first().display_name, self.asset.public_name)
        self.assertEqual(imported.history.first().location_role, "airport")
        partial = prepare_import_asset({"short_description": "Revised"}, imported)
        self.assertEqual(partial.location_notes, self.asset.location_notes)
        self.assertEqual(partial.display_name, self.asset.display_name)

    def test_unsourced_or_invalid_location_import_is_rejected(self):
        for field, value in (
            ("location_source_url", ""),
            ("location_last_verified_at", ""),
            ("location_role", "imaginary"),
            ("location_method", "unmapped"),
        ):
            fresh = Asset.objects.get(pk=self.asset.pk)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                prepare_import_asset({field: value}, fresh)

    def test_unmapped_asset_stays_in_directory_but_has_no_pin(self):
        self.asset.location_method = "unmapped"
        self.asset.location_role = "service-area"
        self.asset.location_precision = "regional"
        self.asset.latitude = self.asset.longitude = None
        self.asset.full_clean()
        self.asset.save()
        self.assertContains(self.client.get(reverse("core:directory")), self.asset.public_name)
        geo = self.client.get(reverse("api:asset-geojson"), {"q": "ORF"}).json()
        self.assertIsNone(geo["features"][0]["geometry"])

    def test_old_location_evidence_enters_existing_staff_review_queue(self):
        self.asset.location_last_verified_at = date(2000, 1, 1)
        self.asset.save()
        user = get_user_model().objects.create_superuser("profile-reviewer", password="test-only")
        self.client.force_login(user)
        response = self.client.get(reverse("imports:data-quality"))
        self.assertIn(self.asset, response.context["dynamic_claims_stale"])


class ProfileManifestTests(SimpleTestCase):
    def test_catalog_has_documented_public_names_and_pin_context(self):
        catalog = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())
        by_name = {r["name"]: r for r in catalog["records"]}
        airports = [r for r in catalog["records"] if r["provenance"] == "faa-public-airport"]
        self.assertEqual(len(airports), 64)
        for record in airports:
            with self.subTest(name=record["name"]):
                self.assertTrue(record["display_name"])
                self.assertTrue(record["search_aliases"])
                self.assertEqual(record["location_role"], "airport")
                self.assertEqual(record["location_method"], "published")
                self.assertIn(record["location_source_url"], {s["url"] for s in record["sources"]})
        for name in ("AUVSI Ridge and Valley Chapter", "Virginia Automated Corridors"):
            self.assertIsNone(by_name[name]["latitude"])
            self.assertIsNone(by_name[name]["longitude"])
            self.assertEqual(by_name[name]["location_precision"], "regional")
        self.assertEqual(by_name["MITRE National Range"]["location_precision"], "locality")
        self.assertIn("Maryland", by_name["Magothy River Technologies"]["location_notes"])

    def test_specs_do_not_conflate_building_area_runways_and_distinct_sites(self):
        manifest = json.loads(MANIFEST.read_text())
        changes = {
            c["name"]: c["after"]
            for c in manifest["corrections"]
            if "test_source_url" in c["after"]
        }
        self.assertEqual(len(changes), 9)
        self.assertEqual(
            changes["Kentland Experimental Aerial Systems Laboratory"]["test_runway_length_ft"],
            300,
        )
        for name, fields in changes.items():
            if name != "Kentland Experimental Aerial Systems Laboratory":
                self.assertIsNone(fields["test_runway_length_ft"])
        xelevate = changes["Xelevate Leesburg Unmanned Systems Facility"]
        self.assertIn("66-acre", xelevate["test_dimensions"])
        self.assertIn("different site", xelevate["test_dimensions"])

    def test_regeneration_is_idempotent_and_preserves_names(self):
        records = json.loads((settings.BASE_DIR / "data/virginia_real_assets.json").read_text())[
            "records"
        ]
        names = [r["name"] for r in records]
        apply_reviewed_corrections(records)
        first = json.dumps(records, sort_keys=True)
        apply_reviewed_corrections(records)
        self.assertEqual(first, json.dumps(records, sort_keys=True))
        self.assertEqual(names, [r["name"] for r in records])


class ProfileDeploymentTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            name="Kentland Experimental Aerial Systems Laboratory",
            record_type="facility",
            short_description="Laboratory",
            unmanned_systems_relevance="UAS testing",
            status="source-backed",
            visibility="public",
            internal_notes="Catalog provenance: curated-public-source.",
        )

    def apply(self):
        call_command("apply_catalog_corrections", corrections=MANIFEST, stdout=StringIO())
        self.asset.refresh_from_db()

    def test_corrections_are_idempotent_and_do_not_mark_records_verified(self):
        self.apply()
        self.assertEqual(self.asset.location_role, "test-site")
        self.assertEqual(self.asset.location_last_verified_at, date(2026, 9, 6))
        self.assertEqual(self.asset.test_runway_length_ft, 300)
        self.assertIn("KEAS", self.asset.search_aliases)
        self.assertEqual(self.asset.status, "source-backed")
        self.assertIsNone(self.asset.reviewed_at)
        count = self.asset.history.count()
        self.apply()
        self.assertEqual(self.asset.history.count(), count)
        self.assertFalse(self.asset.sources.exclude(verification_status="unreviewed").exists())

    def test_staff_edits_are_not_overwritten(self):
        self.asset._history_user = get_user_model().objects.create_user("editor")
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.search_aliases, "")
        self.assertEqual(self.asset.test_aircraft, "")

    def test_unsourced_baseline_conflict_preserves_entire_test_group(self):
        self.asset.test_access = "Staff-specific test arrangements"
        self.asset.test_source_url = "https://example.org/staff"
        self.asset.test_last_verified_at = date(2026, 9, 5)
        self.asset.save()
        self.apply()
        self.assertEqual(self.asset.test_access, "Staff-specific test arrangements")
        self.assertIsNone(self.asset.test_runway_length_ft)
        self.assertIn("KEAS", self.asset.search_aliases)

    def test_hidden_source_blocks_location_and_specs_but_not_independent_aliases(self):
        Source.objects.create(
            asset=self.asset,
            title="Hidden source",
            url="https://autonomyandrobotics.centers.vt.edu/groups/keas.html",
            is_public=False,
        )
        self.apply()
        self.assertEqual(self.asset.location_role, "")
        self.assertEqual(self.asset.test_aircraft, "")
        self.assertIn("KEAS", self.asset.search_aliases)
