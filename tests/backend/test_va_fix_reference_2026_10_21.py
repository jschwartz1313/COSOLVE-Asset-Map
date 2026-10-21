import json
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Asset, AssetReviewComment, Relationship
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source

MANIFEST = settings.BASE_DIR / "data/asset_reference_corrections_2026_10_21.json"
NAME = "Virginia Flight Information Exchange"
URL = (
    "https://doav.virginia.gov/wp-content/uploads/Files/DocumentLibrary/"
    "va--fix-conops-summary-version-7.pdf"
)
ALIASES = "VA FIX\nVA-FIX\nVirginia FIX"
TAXONOMY_MODELS = (StrategicCategory, PlatformDomain, Capability, MissionArea)
TAXONOMY_FIELDS = ("strategic_categories", "platform_domains", "capabilities", "missions")


def stored_snapshot():
    return {
        "assets": list(Asset.objects.order_by("pk").values()),
        "asset_history": list(Asset.history.order_by("history_id").values()),
        "sources": list(Source.objects.order_by("pk").values()),
        "source_history": list(Source.history.order_by("history_id").values()),
        "relationships": list(Relationship.objects.order_by("pk").values()),
        "relationship_history": list(Relationship.history.order_by("history_id").values()),
        "taxonomy": {
            field: list(getattr(Asset, field).through.objects.order_by("pk").values())
            for field in TAXONOMY_FIELDS
        },
    }


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class VaFixReferenceCorrectionTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            name=NAME,
            record_type=Asset.RecordType.PROGRAM,
            short_description="Existing statewide digital advisory program.",
            overview="Preserve the current hosted profile text.",
            unmanned_systems_relevance="Shares UAS safety and advisory information.",
            website_url="https://vipc.org/initiatives/virginia-unmanned-systems-center/",
            contact_url="https://vipc.org/initiatives/virginia-unmanned-systems-center/",
            contact_text="Existing public information route",
            activity_status=Asset.ActivityStatus.ACTIVE,
            current_activity="Existing program activity; no new readiness claim.",
            activity_source_url="https://doav.virginia.gov/aviation_programs_resources/",
            activity_last_verified_at=date(2026, 8, 6),
            location_precision=Asset.LocationPrecision.REGIONAL,
            location_role=Asset.LocationRole.SERVICE_AREA,
            location_method=Asset.LocationMethod.UNMAPPED,
            location_notes="Statewide digital program; retain the absence of a single point.",
            location_source_url="https://doav.virginia.gov/aviation_programs_resources/",
            location_last_verified_at=date(2026, 9, 16),
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
            last_verified_at=date(2026, 8, 11),
            reviewed_at=timezone.now(),
            internal_notes="Catalog provenance: curated-public-source.",
            region=Region.objects.create(name="Existing regional choice"),
        )
        self.original_source = Source.objects.create(
            asset=self.asset,
            title="Existing reviewed concept paper",
            url=(
                "https://doav.virginia.gov/wp-content/uploads/Files/DocumentLibrary/"
                "va-fix-concept-paper-july-2020---copyright-final-publication.pdf"
            ),
            verification_status="verified",
            last_verified_at=date(2026, 9, 16),
            notes="Preserve the existing source decision.",
        )
        self.other = Asset.objects.create(
            name="Existing aviation coordination fixture",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="An unrelated existing organization.",
            unmanned_systems_relevance="Existing public relationship endpoint.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Relationship.objects.create(
            from_asset=self.other,
            to_asset=self.asset,
            relationship_type=Relationship.RelationshipType.SUPPORTS,
        )
        for field, model in zip(TAXONOMY_FIELDS, TAXONOMY_MODELS, strict=True):
            getattr(self.asset, field).add(model.objects.create(name=f"Existing {field}"))

    def apply(self):
        call_command("apply_catalog_corrections", corrections=MANIFEST, stdout=StringIO())
        self.asset.refresh_from_db()

    def assert_held(self, before):
        self.assertEqual(stored_snapshot(), before)
        original = next(row for row in before["assets"] if row["id"] == self.asset.pk)
        self.assertEqual(self.asset.search_aliases, original["search_aliases"])

    def test_manifest_is_limited_to_one_existing_program_alias_group_and_dated_reference(self):
        manifest = json.loads(MANIFEST.read_text())
        self.assertEqual(len(manifest["corrections"]), 1)
        item = manifest["corrections"][0]
        self.assertEqual(item["name"], NAME)
        self.assertEqual(item["before"], {"search_aliases": ""})
        self.assertEqual(item["after"], {"search_aliases": ALIASES})
        self.assertEqual(len(item["add_sources"]), 1)
        self.assertEqual(item["add_sources"][0]["url"], URL)
        self.assertIn("2020", item["add_sources"][0]["title"])
        self.assertFalse(item.get("review_required"))
        self.assertFalse(item.get("replace_sources"))

    def test_applies_once_preserving_inventory_profile_editorial_state_and_existing_evidence(self):
        before = stored_snapshot()
        old_asset = Asset.objects.filter(pk=self.asset.pk).values().get()
        self.apply()
        new_asset = Asset.objects.filter(pk=self.asset.pk).values().get()
        changed = {field for field in old_asset if old_asset[field] != new_asset[field]}
        self.assertEqual(changed, {"search_aliases", "updated_at"})
        self.assertEqual(self.asset.search_aliases, ALIASES)
        self.assertEqual(Asset.objects.count(), 2)
        self.assertIsNone(self.asset.latitude)
        self.assertIsNone(self.asset.longitude)
        self.assertEqual(self.asset.status, Asset.Status.PUBLISHED)
        after = stored_snapshot()
        for key in ("relationships", "relationship_history", "taxonomy"):
            self.assertEqual(after[key], before[key])
        for key in ("assets", "asset_history"):
            self.assertEqual(
                [row for row in after[key] if row["id"] != self.asset.pk],
                [row for row in before[key] if row["id"] != self.asset.pk],
            )
        self.assertEqual(
            Source.objects.filter(pk=self.original_source.pk).values().get(),
            before["sources"][0],
        )
        self.assertEqual(
            list(Source.history.filter(id=self.original_source.pk).order_by("history_id").values()),
            before["source_history"],
        )
        source = self.asset.sources.get(url=URL)
        self.assertTrue(source.is_public)
        self.assertEqual(source.verification_status, "unreviewed")
        self.assertIsNone(source.source_date)
        self.assertIsNone(source.last_verified_at)
        self.assertIsNone(source.last_checked_at)
        self.assertIsNone(source.http_status)
        self.assertEqual(source.link_review_status, Source.LinkReviewStatus.AUTOMATIC)
        self.assertEqual(AssetReviewComment.objects.filter(asset=self.asset).count(), 1)
        first_result = stored_snapshot()
        comments = list(AssetReviewComment.objects.order_by("pk").values())
        self.apply()
        self.assertEqual(stored_snapshot(), first_result)
        self.assertEqual(list(AssetReviewComment.objects.order_by("pk").values()), comments)

    def test_exact_alias_queries_find_the_existing_unmapped_profile_without_duplicates(self):
        self.apply()
        for alias in ALIASES.splitlines():
            with self.subTest(alias=alias):
                response = self.client.get(reverse("api:asset-list"), {"q": f'"{alias}"'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["result_count"], 1)
                self.assertEqual(response.json()["results"][0]["slug"], self.asset.slug)
        detail = self.client.get(self.asset.get_absolute_url())
        self.assertContains(detail, URL)
        self.assertEqual(Asset.objects.filter(name=NAME).count(), 1)

    def test_nonblank_staff_alias_is_preserved_with_no_partial_source_addition(self):
        self.asset.search_aliases = "Staff preferred acronym"
        self.asset.save(update_fields=["search_aliases", "updated_at"])
        before = stored_snapshot()
        self.apply()
        self.assert_held(before)
        self.assertFalse(self.asset.sources.filter(url=URL).exists())
        self.assertTrue(self.asset.review_comments.filter(
            body__startswith="Catalog correction conflict:"
        ).exists())

    def test_attributed_asset_history_is_preserved_even_when_alias_baseline_matches(self):
        user = get_user_model().objects.create_user(username="reference-reviewer")
        self.asset._history_user = user
        self.asset.overview = "A staff-authored profile description."
        self.asset.save(update_fields=["overview", "updated_at"])
        before = stored_snapshot()
        self.apply()
        self.assert_held(before)
        self.assertFalse(self.asset.sources.filter(url=URL).exists())

    def test_visibility_status_and_provenance_holds_do_not_change_the_asset_or_sources(self):
        for field, value in (
            ("visibility", Asset.Visibility.INTERNAL),
            ("status", Asset.Status.ARCHIVED),
            ("internal_notes", "Staff-managed evidence and identity."),
        ):
            with self.subTest(field=field), transaction.atomic():
                self.asset.refresh_from_db()
                setattr(self.asset, field, value)
                if field == "visibility":
                    self.asset.status = Asset.Status.SOURCE_BACKED
                self.asset.save(update_fields=[field, "status", "updated_at"])
                before = stored_snapshot()
                self.apply()
                self.assert_held(before)
                self.assertFalse(self.asset.sources.filter(url=URL).exists())
                transaction.set_rollback(True)

    def test_hidden_rejected_or_replacement_source_holds_the_entire_alias_group(self):
        decisions = (
            {"is_public": False},
            {"verification_status": "rejected"},
            {"verification_status": "stale"},
            {"link_review_status": Source.LinkReviewStatus.NEEDS_REPLACEMENT,
             "link_review_notes": "Staff source decision."},
        )
        for decision in decisions:
            with self.subTest(decision=decision), transaction.atomic():
                Source.objects.create(asset=self.asset, title="Existing source decision", url=URL,
                                      **decision)
                before = stored_snapshot()
                self.apply()
                self.assert_held(before)
                self.assertEqual(self.asset.sources.filter(url=URL).count(), 1)
                transaction.set_rollback(True)

    def test_deleted_or_changed_source_history_is_not_restored(self):
        for retire in ("delete", "change-url"):
            with self.subTest(retire=retire), transaction.atomic():
                source = Source.objects.create(asset=self.asset, title="Retired reference", url=URL)
                if retire == "delete":
                    source.delete()
                else:
                    source.url = "https://example.org/staff-selected-replacement"
                    source.save()
                before = stored_snapshot()
                self.apply()
                self.assert_held(before)
                self.assertFalse(self.asset.sources.filter(url=URL).exists())
                transaction.set_rollback(True)
