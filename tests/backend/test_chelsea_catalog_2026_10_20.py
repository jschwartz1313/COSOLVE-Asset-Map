import json
from copy import deepcopy
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.api.serializers import asset_feature
from apps.assets.models import Asset, AssetReviewComment, Relationship
from apps.sources.models import Source

EXPANSION = settings.BASE_DIR / "data/asset_expansion_2026_10_20.json"
CORRECTIONS = settings.BASE_DIR / "data/asset_corrections_2026_10_20.json"
CATALOG = settings.BASE_DIR / "data/virginia_real_assets.json"
TAXONOMIES = ("strategic_categories", "platform_domains", "capabilities", "missions")
FIELD = "Newport News Park Radio Control Club Flying Field"
FASCOM = "U.S. Army Futures and Autonomous Systems Command"
ROCKET_LAB = "Rocket Lab Virginia Launch Operations"
JLAB = "Thomas Jefferson National Accelerator Facility (Jefferson Lab)"
AAES = "Aerospace Academy of the Eastern Shore"
SEFC = "Virginia Tech Corporate Research Center Newport News and Secure Energy Future Center"
JCC = "James City County Police Drone as First Responder Program"
MIC = "Hampton Roads Mobility Innovation Center"


def seed_payload(payload):
    with TemporaryDirectory() as directory:
        path = Path(directory) / "catalog.json"
        path.write_text(json.dumps(payload))
        call_command("seed_real_data", catalog=path, add_missing=True, stdout=StringIO())


def inventory_snapshot():
    return {
        "assets": list(Asset.objects.order_by("pk").values()),
        "asset_history": list(Asset.history.order_by("history_id").values()),
        "sources": list(Source.objects.order_by("pk").values()),
        "source_history": list(Source.history.order_by("history_id").values()),
        "relationships": list(Relationship.objects.order_by("pk").values()),
        "relationship_history": list(Relationship.history.order_by("history_id").values()),
        "taxonomy": {
            field: list(getattr(Asset, field).through.objects.order_by("pk").values())
            for field in TAXONOMIES
        },
    }


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class ChelseaCatalogReleaseTests(TestCase):
    def setUp(self):
        self.manifest = json.loads(EXPANSION.read_text())
        self.records = {record["name"]: record for record in self.manifest["records"]}
        endpoints = {
            item[field]
            for item in self.manifest["relationships"]
            for field in ("from", "to")
        } - self.records.keys()
        for name in sorted(endpoints):
            Asset.objects.create(
                name=name,
                record_type=Asset.RecordType.ORGANIZATION,
                short_description="Existing host or partner fixture.",
                overview="Retain this existing staff description.",
                unmanned_systems_relevance="Existing ecosystem record.",
                status=Asset.Status.SOURCE_BACKED,
                visibility=Asset.Visibility.PUBLIC,
            )

    def seed(self):
        call_command("seed_real_data", catalog=EXPANSION, add_missing=True, stdout=StringIO())

    def single_record_payload(self, record):
        return {
            "records": [record],
            "relationships": [
                item for item in self.manifest["relationships"]
                if record["name"] in (item["from"], item["to"])
            ],
        }

    def assert_manifest_scope(self):
        expected = {
            FIELD, FASCOM, ROCKET_LAB, JLAB, AAES, SEFC, "757 Collab",
            "Hampton Roads Workforce Council", "Innovate Hampton Roads",
            "Maxbyte Industry 4.0 Centre of Excellence at TCC", "Pancopia LLC",
            "Liti Holographics, Inc.",
        }
        self.assertEqual(set(self.records), expected)
        self.assertEqual(len(self.manifest["records"]), len(expected))
        self.assertEqual(len(self.manifest["relationships"]), 7)
        excluded = {
            "Smart Airspace 2.0", "USCG TTLC",
            "Hampton Roads Airspace Sensor Collaboration Working Group",
            "Langley Aerospace Innovation District", "Space Academy", "MechaStructure",
            "Firefly Aerospace Virginia Launch Operations", "HII ROMULUS", "HII REMUS",
            "HII Odyssey",
        }
        self.assertFalse(excluded.intersection(self.records))
        catalog = json.loads(CATALOG.read_text())
        self.assertEqual(catalog["record_count"], len(catalog["records"]))
        self.assertTrue(expected.issubset(record["name"] for record in catalog["records"]))
        self.assertTrue(all(record["identity_guard_terms"] for record in self.records.values()))
        def edges(items):
            return {(item["from"], item["type"], item["to"]) for item in items}

        self.assertTrue(
            edges(self.manifest["relationships"]).issubset(edges(catalog["relationships"]))
        )

    def test_new_records_are_pending_with_valid_models_unreviewed_sources_and_intended_edges(self):
        self.assert_manifest_scope()
        existing = list(Asset.objects.order_by("pk").values())
        self.seed()
        for record in self.records.values():
            with self.subTest(name=record["name"]):
                asset = Asset.objects.get(name=record["name"])
                asset.full_clean()
                self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
                self.assertEqual(asset.visibility, Asset.Visibility.PUBLIC)
                self.assertIsNone(asset.reviewed_at)
                self.assertIsNone(asset.reviewed_by_id)
                self.assertIsNone(asset.last_verified_at)
                self.assertIsNone(asset.published_at)
                self.assertEqual(
                    set(asset.sources.values_list("url", flat=True)),
                    {source["url"] for source in record["sources"]},
                )
                for source in asset.sources.all():
                    source.full_clean()
                    self.assertTrue(source.is_public)
                    self.assertEqual(source.verification_status, "unreviewed")
                    self.assertIsNone(source.last_verified_at)
                    self.assertIsNone(source.last_checked_at)
                response = self.client.get(f"/api/assets/{asset.slug}/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["review_status"], "source-backed")
        for before in existing:
            self.assertEqual(Asset.objects.filter(pk=before["id"]).values().get(), before)
        self.assertEqual(
            set(Relationship.objects.values_list(
                "from_asset__name", "relationship_type", "to_asset__name", "is_public",
            )),
            {(item["from"], item["type"], item["to"], True)
             for item in self.manifest["relationships"]},
        )
        for relationship in Relationship.objects.all():
            relationship.full_clean()

    def test_regional_and_unverified_address_records_do_not_acquire_fallback_map_points(self):
        self.seed()
        for name in (FASCOM, ROCKET_LAB, AAES, "757 Collab"):
            with self.subTest(name=name):
                asset = Asset.objects.get(name=name)
                self.assertEqual(asset.location_precision, Asset.LocationPrecision.REGIONAL)
                self.assertEqual(asset.location_method, Asset.LocationMethod.UNMAPPED)
                self.assertIsNone(asset.latitude)
                self.assertIsNone(asset.longitude)
                self.assertIsNone(asset_feature(asset)["geometry"])
                response = self.client.get(f"/api/assets/{asset.slug}/")
                self.assertEqual(response.json()["location"]["precision"], "regional")
        for name in (JLAB, SEFC):
            with self.subTest(name=name):
                asset = Asset.objects.get(name=name)
                self.assertTrue(asset.address_line)
                self.assertIsNone(asset.latitude)
                self.assertIsNone(asset.longitude)
                self.assertIsNone(asset_feature(asset)["geometry"])

        field = Asset.objects.get(name=FIELD)
        self.assertEqual(field.test_runway_length_ft, 400)
        self.assertEqual(field.location_method, Asset.LocationMethod.PUBLISHED)
        self.assertTrue(field.has_public_coordinates)
        self.assertIn("members", field.test_access.lower())
        self.assertIn("not a surveyed boundary", field.location_notes)
        self.assertContains(self.client.get(field.get_absolute_url()), "400-foot")
        pancopia = Asset.objects.get(name="Pancopia LLC")
        self.assertIn("occupancy", pancopia.location_notes)
        self.assertIn("not been independently confirmed", pancopia.location_notes)
        self.assertContains(self.client.get(pancopia.get_absolute_url()), "occupancy")
        for name in ("Innovate Hampton Roads", "Liti Holographics, Inc."):
            asset = Asset.objects.get(name=name)
            self.assertEqual(
                (asset.latitude, asset.longitude), (pancopia.latitude, pancopia.longitude)
            )
            self.assertIn("office-building reference", asset.location_notes)
        academy = Asset.objects.get(name=AAES)
        self.assertIn("not the program's campus", academy.location_notes)

    def test_repeated_add_missing_preserves_inventory_history_taxonomy_and_staff_sources(self):
        self.seed()
        asset = Asset.objects.get(name=FIELD)
        asset.overview = "Staff-maintained field description."
        asset.save()
        source = asset.sources.first()
        source.is_public = False
        source.verification_status = "rejected"
        source.link_review_status = Source.LinkReviewStatus.NEEDS_REPLACEMENT
        source.link_review_notes = "Preserve this staff evidence decision."
        source.save()
        Source.objects.create(
            asset=asset, title="Private staff evidence", url="https://example.org/private-evidence",
            is_public=False,
        )
        for index, link in enumerate(Relationship.objects.order_by("pk")):
            if index % 2:
                link.delete()
            else:
                link.is_public = False
                link.description = "Staff held this relationship."
                link.save()
        before = inventory_snapshot()

        self.seed()

        self.assertEqual(inventory_snapshot(), before)

    def test_current_staff_aliases_and_exact_identities_hold_each_candidate_and_its_edges(self):
        for record in self.records.values():
            for case in ("internal-alias", "archived-alias", "public-exact"):
                with self.subTest(name=record["name"], case=case), transaction.atomic():
                    staff = Asset.objects.create(
                        name=record["name"] if case == "public-exact" else "Staff-held identity",
                        search_aliases=("" if case == "public-exact"
                                        else record["identity_guard_terms"][0]),
                        record_type=Asset.RecordType.ORGANIZATION,
                        short_description="Retain the existing staff identity.",
                        unmanned_systems_relevance="Staff-managed evidence.",
                        status=(Asset.Status.ARCHIVED if case == "archived-alias"
                                else Asset.Status.SOURCE_BACKED),
                        visibility=(Asset.Visibility.INTERNAL if case == "internal-alias"
                                    else Asset.Visibility.PUBLIC),
                    )
                    Source.objects.create(
                        asset=staff, title="Staff source", url="https://example.org/staff-source",
                        is_public=False,
                    )
                    before = inventory_snapshot()

                    seed_payload(self.single_record_payload(record))

                    self.assertEqual(inventory_snapshot(), before)
                    transaction.set_rollback(True)


class ChelseaCatalogCorrectionTests(TestCase):
    def setUp(self):
        self.manifest = json.loads(CORRECTIONS.read_text())
        self.items = {item["name"]: item for item in self.manifest["corrections"]}
        current = {record["name"]: record for record in json.loads(CATALOG.read_text())["records"]}
        records = []
        for item in self.items.values():
            record = deepcopy(current[item["name"]])
            record.update(item["before"])
            new_urls = {source["url"] for source in item["add_sources"]}
            record["sources"] = [
                source for source in record["sources"] if source["url"] not in new_urls
            ]
            records.append(record)
        seed_payload({"records": records})
        jcc = Asset.objects.get(name=JCC)
        jcc.status = Asset.Status.PUBLISHED
        jcc.reviewed_at = timezone.now()
        jcc.last_verified_at = date(2026, 8, 11)
        jcc.save()
        for asset in Asset.objects.all():
            Source.objects.create(
                asset=asset, title="Private retained evidence",
                url=f"https://example.org/retained/{asset.slug}", is_public=False,
                verification_status="rejected",
            )
        Relationship.objects.create(
            from_asset=jcc, to_asset=Asset.objects.get(name=MIC),
            relationship_type=Relationship.RelationshipType.SUPPORTS, is_public=False,
            description="Retain this staff relationship choice.",
        )

    def apply(self, item=None):
        if item is None:
            call_command("apply_catalog_corrections", corrections=CORRECTIONS, stdout=StringIO())
            return
        with TemporaryDirectory() as directory:
            path = Path(directory) / "correction.json"
            path.write_text(json.dumps({**self.manifest, "corrections": [item]}))
            call_command("apply_catalog_corrections", corrections=path, stdout=StringIO())

    def test_exact_baselines_apply_only_atomic_groups_without_editorial_or_source_rewrites(self):
        before = inventory_snapshot()

        self.apply()

        after = inventory_snapshot()
        for old, new in zip(before["assets"], after["assets"], strict=True):
            item = self.items[new["name"]]
            changed = set(item["after"]) | {"updated_at"}
            self.assertEqual(
                {key: value for key, value in old.items() if key not in changed},
                {key: value for key, value in new.items() if key not in changed},
            )
            asset = Asset.objects.get(pk=new["id"])
            for field, value in item["after"].items():
                self.assertEqual(
                    getattr(asset, field), asset._meta.get_field(field).to_python(value)
                )
        old_sources = {source["id"]: source for source in before["sources"]}
        for source in after["sources"]:
            if source["id"] in old_sources:
                self.assertEqual(source, old_sources[source["id"]])
            else:
                self.assertEqual(source["verification_status"], "unreviewed")
                self.assertIsNone(source["last_verified_at"])
                self.assertTrue(source["is_public"])
        self.assertEqual(len(after["sources"]), len(before["sources"]) + 2)
        for key in ("relationships", "relationship_history", "taxonomy"):
            self.assertEqual(before[key], after[key])
        self.assertEqual(len(after["asset_history"]), len(before["asset_history"]) + 2)
        self.assertEqual(AssetReviewComment.objects.count(), 2)
        comments = list(AssetReviewComment.objects.order_by("pk").values())

        self.apply()

        self.assertEqual(inventory_snapshot(), after)
        self.assertEqual(list(AssetReviewComment.objects.order_by("pk").values()), comments)

    def test_saved_catalog_jcc_date_is_an_accepted_baseline_without_publishing_mic(self):
        jcc = Asset.objects.get(name=JCC)
        jcc.activity_last_verified_at = date(2026, 8, 21)
        jcc.save()

        self.apply()

        jcc.refresh_from_db()
        mic = Asset.objects.get(name=MIC)
        self.assertEqual(jcc.activity_status, Asset.ActivityStatus.ACTIVE)
        self.assertIn("August 1, 2026", jcc.current_activity)
        self.assertEqual(mic.activity_status, Asset.ActivityStatus.DEVELOPING)
        self.assertEqual(mic.development_status, Asset.DevelopmentStatus.IN_DEVELOPMENT)
        self.assertIn("future-facing", mic.current_activity)
        self.assertEqual(mic.status, Asset.Status.SOURCE_BACKED)
        self.assertIsNone(mic.reviewed_at)
        self.assertIsNone(mic.last_verified_at)

    def test_staff_values_history_comments_and_source_choices_hold_both_atomic_groups(self):
        user = get_user_model().objects.create_user("isolated-chelsea-reviewer")
        for name in self.items:
            for case in ("changed-field", "history", "comment", "hidden-source", "retired-source"):
                with self.subTest(name=name, case=case), transaction.atomic():
                    asset = Asset.objects.get(name=name)
                    if case == "changed-field":
                        if name == JCC:
                            asset.current_activity = "Staff-selected replacement text."
                        else:
                            asset.activity_status = Asset.ActivityStatus.DEVELOPING
                    elif case == "history":
                        asset._history_user = user
                    elif case == "comment":
                        AssetReviewComment.objects.create(asset=asset, author=user, body="Retain.")
                    else:
                        source = Source.objects.create(
                            asset=asset, title="Staff-held new evidence",
                            url=self.items[name]["add_sources"][0]["url"], is_public=False,
                        )
                        if case == "retired-source":
                            source.delete()
                    asset.save()
                    before = inventory_snapshot()
                    comments = list(AssetReviewComment.objects.order_by("pk").values())

                    self.apply(self.items[name])

                    self.assertEqual(inventory_snapshot(), before)
                    if case in {"history", "comment"}:
                        self.assertEqual(
                            list(AssetReviewComment.objects.order_by("pk").values()), comments
                        )
                    else:
                        self.assertEqual(asset.review_comments.count(), 1)
                        self.assertTrue(asset.review_comments.get().body.startswith(
                            "Catalog correction conflict:"
                        ))
                    after_comments = list(AssetReviewComment.objects.order_by("pk").values())
                    self.apply(self.items[name])
                    self.assertEqual(inventory_snapshot(), before)
                    self.assertEqual(
                        list(AssetReviewComment.objects.order_by("pk").values()), after_comments
                    )
                    transaction.set_rollback(True)


class RetiredCatalogIdentityTests(TestCase):
    def setUp(self):
        self.host = Asset.objects.create(
            name="Unrelated existing host",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="Preserved host fixture.",
            unmanned_systems_relevance="Existing ecosystem organization.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        self.guard_term = "Unique Chelsea identity fixture"
        self.candidate_name = "Proposed guarded catalog fixture"

    def seed_guarded_candidate(self):
        payload = {
            "records": [{
                "name": self.candidate_name,
                "identity_guard_terms": [self.guard_term],
                "record_type": "program",
                "short_description": "Source-backed program fixture.",
                "unmanned_systems_relevance": "Documented UAS program fixture.",
                "latitude": None,
                "longitude": None,
                "location_precision": "regional",
                "region": "Hampton Roads",
                "strategic_categories": ["Core unmanned-systems asset"],
                "platform_domains": [],
                "capabilities": [],
                "missions": [],
                "provenance": "curated-public-source",
                "sources": [{"title": "Fixture evidence", "url": "https://example.org/evidence"}],
            }],
            "relationships": [
                {"from": self.candidate_name, "type": "located-at", "to": self.host.name},
                {"from": self.host.name, "type": "supports", "to": self.candidate_name},
            ],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "guarded-candidate.json"
            path.write_text(json.dumps(payload))
            call_command("seed_real_data", catalog=path, add_missing=True, stdout=StringIO())

    def snapshot(self):
        return {
            "assets": list(Asset.objects.order_by("pk").values()),
            "asset_history": list(Asset.history.order_by("history_id").values()),
            "sources": list(Source.objects.order_by("pk").values()),
            "source_history": list(Source.history.order_by("history_id").values()),
            "relationships": list(Relationship.objects.order_by("pk").values()),
            "relationship_history": list(Relationship.history.order_by("history_id").values()),
        }

    def staff_identity(self, matching_field):
        return Asset.objects.create(
            **{
                "name": "Private staff identity fixture",
                "record_type": Asset.RecordType.PROGRAM,
                "short_description": "Retain this staff choice.",
                "unmanned_systems_relevance": "Staff evidence fixture.",
                "status": Asset.Status.ARCHIVED,
                "visibility": Asset.Visibility.INTERNAL,
                matching_field: self.guard_term,
            }
        )

    def test_deleted_staff_identity_history_holds_candidate_and_both_relationship_directions(self):
        for matching_field in ("name", "display_name", "search_aliases"):
            with self.subTest(matching_field=matching_field), transaction.atomic():
                staff = self.staff_identity(matching_field)
                staff.delete()
                before = self.snapshot()

                self.seed_guarded_candidate()

                self.assertFalse(Asset.objects.filter(name=self.candidate_name).exists())
                self.assertEqual(self.snapshot(), before)
                transaction.set_rollback(True)

    def test_renamed_staff_identity_history_holds_candidate_and_both_relationship_directions(self):
        for matching_field in ("name", "display_name", "search_aliases"):
            with self.subTest(matching_field=matching_field), transaction.atomic():
                staff = self.staff_identity(matching_field)
                staff.name = "Staff-selected replacement identity"
                staff.display_name = ""
                staff.search_aliases = ""
                staff.save()
                before = self.snapshot()

                self.seed_guarded_candidate()

                self.assertFalse(Asset.objects.filter(name=self.candidate_name).exists())
                self.assertEqual(self.snapshot(), before)
                transaction.set_rollback(True)
