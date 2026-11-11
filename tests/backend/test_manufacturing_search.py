import csv
import json
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import include, path
from django.utils import timezone

from apps.assets.management.commands.seed_manufacturing_fit import load_seed
from apps.assets.manufacturing import (
    ManufacturingProfile,
    compare_manufacturing,
    manufacturing_candidates,
)
from apps.assets.models import Asset
from apps.catalog.models import Region, StrategicCategory
from apps.core.manufacturing_forms import ManufacturingSearchForm
from apps.core.manufacturing_views import manufacturing_search
from apps.sources.models import Source

urlpatterns = [
    path("manufacturing-fixture/", manufacturing_search),
    path("", include("config.urls")),
]
SEARCH_URL = "/manufacturing-fixture/"


class ManufacturingFixtures:
    @classmethod
    def make_asset(cls, **overrides):
        values = {
            "name": "Documented local manufacturer",
            "record_type": "facility",
            "city": "Danville",
            "state": "VA",
            "short_description": "CNC, aluminum, titanium and contract work in unstructured prose",
            "unmanned_systems_relevance": "Manufacturing fixture",
            "status": "source-backed",
            "visibility": "public",
            "internal_notes": "Catalog provenance: manufacturing-fixture.",
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    @classmethod
    def profile_values(cls, **overrides):
        values = {
            "processes": ["cnc-machining", "metrology"],
            "materials": ["aluminum"],
            "service_modes": ["inspection-services"],
            "access_types": ["commercial"],
            "source_url": "https://manufacturer.example/local-capabilities",
            "reviewed_at": timezone.localdate(),
            "notes": "Local machining and inspection; no general contract-production claim.",
        }
        values.update(overrides)
        return values

    @classmethod
    def make_source(cls, asset, **overrides):
        values = {
            "title": "Local operator capabilities",
            "url": cls.profile_values()["source_url"],
            "is_public": True,
        }
        values.update(overrides)
        return Source.objects.create(asset=asset, **values)


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="", ROOT_URLCONF=__name__)
class ManufacturingSearchTests(ManufacturingFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.site = cls.make_asset()
        cls.source = cls.make_source(cls.site)
        cls.profile = ManufacturingProfile.objects.create(asset=cls.site, **cls.profile_values())

    def compare(self, **requirements):
        return compare_manufacturing(Asset.objects.get(pk=self.site.pk), requirements)

    def test_no_requirements_is_reference_not_suitability(self):
        row = self.compare()
        self.assertEqual(row["state"], "reference")
        self.assertEqual(row["checks"], [])

    def test_only_documented_fields_match(self):
        row = self.compare(
            process="cnc-machining", material="aluminum", mode="inspection-services",
            access="commercial",
        )
        self.assertEqual(row["state"], "match")
        self.assertEqual([check["status"] for check in row["checks"]], ["match"] * 4)

    def test_missing_attributes_are_unknown_not_conflicts_or_exclusions(self):
        for requirements in (
            {"process": "pcb-assembly"}, {"material": "titanium"},
            {"mode": "contract-manufacturing"}, {"access": "restricted"},
        ):
            with self.subTest(requirements=requirements):
                row = self.compare(**requirements)
                self.assertEqual(row["state"], "unknown")
                self.assertEqual(row["checks"][0]["status"], "unknown")
                response = self.client.get(SEARCH_URL, requirements)
                self.assertEqual(response.context["result_count"], 1)

    def test_empty_lists_remain_unknown(self):
        ManufacturingProfile.objects.filter(pk=self.profile.pk).update(
            materials=[], access_types=[]
        )
        self.assertEqual(self.compare(material="aluminum")["state"], "unknown")
        self.assertEqual(self.compare(access="commercial")["state"], "unknown")

    def test_own_product_factory_does_not_imply_contract_service(self):
        ManufacturingProfile.objects.filter(pk=self.profile.pk).update(
            service_modes=["product-manufacturing"], access_types=[]
        )
        self.assertEqual(self.compare(mode="product-manufacturing")["state"], "match")
        self.assertEqual(self.compare(mode="contract-manufacturing")["state"], "unknown")
        self.assertEqual(self.compare(access="commercial")["state"], "unknown")

    def test_unusable_sources_hide_all_claims_and_notes(self):
        for updates in (
            {"is_public": False}, {"verification_status": "stale"},
            {"verification_status": "rejected"}, {"link_review_status": "needs-replacement"},
            {"url": "https://manufacturer.example/other-site"},
        ):
            with self.subTest(updates=updates):
                Source.objects.filter(pk=self.source.pk).update(
                    is_public=True, verification_status="unreviewed",
                    link_review_status="automatic", url=self.profile.source_url,
                )
                Source.objects.filter(pk=self.source.pk).update(**updates)
                row = self.compare(process="cnc-machining", access="commercial")
                self.assertEqual(row["state"], "unknown")
                self.assertFalse(row["evidence_usable"])
                for key in ("process_labels", "material_labels", "service_mode_labels",
                            "access_labels", "source_url", "notes"):
                    self.assertFalse(row[key])

    def test_private_duplicate_source_also_blocks_evidence(self):
        self.make_source(self.site, is_public=False, title="Private duplicate")
        self.assertEqual(self.compare(process="cnc-machining")["state"], "unknown")

    def test_matching_source_on_another_asset_is_insufficient(self):
        Source.objects.filter(pk=self.source.pk).delete()
        self.make_source(self.make_asset(name="Remote factory"))
        self.assertEqual(self.compare(process="cnc-machining")["state"], "unknown")

    def test_missing_future_or_unsafe_evidence_is_unknown(self):
        for changes in (
            {"reviewed_at": None},
            {"reviewed_at": timezone.localdate() + timedelta(days=1)},
            {"source_url": "javascript:alert(1)"},
            {"source_url": ""},
        ):
            with self.subTest(changes=changes):
                asset = Asset.objects.get(pk=self.site.pk)
                profile = asset.manufacturing_profile
                for key, value in changes.items():
                    setattr(profile, key, value)
                self.assertEqual(
                    compare_manufacturing(asset, {"process": "cnc-machining"})["state"], "unknown"
                )

    def test_malformed_stored_choices_do_not_match(self):
        for values in ("cnc-machining", ["cnc-machining", {}],
                       ["cnc-machining", "cnc-machining"], None):
            with self.subTest(values=values):
                asset = Asset.objects.get(pk=self.site.pk)
                asset.manufacturing_profile.processes = values
                self.assertEqual(
                    compare_manufacturing(asset, {"process": "cnc-machining"})["state"], "unknown"
                )

    def test_category_without_profile_is_unknown(self):
        site = self.make_asset(name="Legacy category-only site")
        site.strategic_categories.add(StrategicCategory.objects.create(name="Manufacturing sites"))
        row = compare_manufacturing(site, {"process": "cnc-machining"})
        self.assertEqual(row["state"], "unknown")
        self.assertIn(site, manufacturing_candidates(Asset.public.all()))

    def test_candidates_are_category_or_profile_not_corporate_keywords(self):
        company = self.make_asset(name="Corporate CNC machining and manufacturing supplier")
        company.strategic_categories.add(
            StrategicCategory.objects.create(name="Manufacturing and supply chain")
        )
        self.assertNotIn(company, manufacturing_candidates(Asset.public.all()))
        existing_category = self.make_asset(name="Existing manufacturing category")
        existing_category.strategic_categories.add(
            StrategicCategory.objects.create(name="Manufacturing facilities")
        )
        self.assertIn(existing_category, manufacturing_candidates(Asset.public.all()))

    def test_historical_private_and_draft_assets_are_hidden(self):
        for updates in (
            {"visibility": "internal"}, {"activity_status": "historical"}, {"status": "draft"},
        ):
            with self.subTest(updates=updates):
                Asset.objects.filter(pk=self.site.pk).update(
                    visibility="public", activity_status="", status="source-backed"
                )
                Asset.objects.filter(pk=self.site.pk).update(**updates)
                self.assertEqual(self.client.get(SEARCH_URL).context["result_count"], 0)

    @override_settings(PUBLIC_REGION_SLUG="hampton-roads")
    def test_regional_release_cannot_be_overridden(self):
        region = Region.objects.create(name="Southside", slug="southside")
        Asset.objects.filter(pk=self.site.pk).update(region=region)
        response = self.client.get(SEARCH_URL, {"region": "southside", "process": "cnc-machining"})
        self.assertEqual(response.context["result_count"], 0)

    def test_planned_pilot_and_developing_are_not_current_availability_matches(self):
        for activity in ("planned", "developing", "pilot"):
            with self.subTest(activity=activity):
                Asset.objects.filter(pk=self.site.pk).update(activity_status=activity)
                self.assertEqual(self.compare(process="cnc-machining")["state"], "unknown")

    def test_invalid_filters_return_errors_without_comparison_or_csv(self):
        for field in ("process", "material", "mode", "access", "outcome"):
            with self.subTest(field=field):
                self.assertFalse(ManufacturingSearchForm({field: "invented"}).is_valid())
                response = self.client.get(SEARCH_URL, {field: "invented", "download": "csv"})
                self.assertContains(response, "No comparison has been made")
                self.assertEqual(response.context["result_count"], 0)
                self.assertNotIn("text/csv", response["Content-Type"])

    def test_outcome_filter_is_explicit_and_csv_consistent(self):
        requirements = {"process": "pcb-assembly"}
        self.assertEqual(self.client.get(SEARCH_URL, requirements).context["result_count"], 1)
        requirements["outcome"] = "match"
        self.assertEqual(self.client.get(SEARCH_URL, requirements).context["result_count"], 0)
        requirements["outcome"] = "unknown"
        response = self.client.get(SEARCH_URL, requirements)
        self.assertEqual(response.context["result_count"], 1)
        exported = self.client.get(SEARCH_URL, {**requirements, "download": "csv"})
        self.assertIn("text/csv", exported["Content-Type"])
        self.assertContains(exported, self.site.public_name)
        self.assertContains(exported, self.profile.source_url)
        self.assertContains(exported, "Needs confirmation")

    def test_review_date_is_internal_in_html_and_export(self):
        ManufacturingProfile.objects.filter(pk=self.profile.pk).update(reviewed_at="2020-05-17")
        for params in ({}, {"download": "csv"}):
            with self.subTest(params=params):
                response = self.client.get(SEARCH_URL, params)
                self.assertNotContains(response, "2020-05-17")
                self.assertNotContains(response, "Source checked")
                self.assertNotContains(response, "Last updated")

    def test_csv_formula_cells_are_escaped(self):
        Asset.objects.filter(pk=self.site.pk).update(display_name="=UNTRUSTED()")
        ManufacturingProfile.objects.filter(pk=self.profile.pk).update(notes=" +UNTRUSTED()")
        response = self.client.get(SEARCH_URL, {"download": "csv"})
        rows = list(csv.reader(StringIO(response.content.decode())))
        self.assertIn("'=UNTRUSTED()", rows[-1])
        self.assertIn("' +UNTRUSTED()", rows[-1])

    def test_invalid_choices_and_evidence_cannot_be_saved(self):
        for field, value in (
            ("processes", ["invented"]), ("materials", ["aluminum", "aluminum"]),
            ("service_modes", [{"bad": "value"}]), ("access_types", "commercial"),
            ("source_url", ""), ("source_url", "ftp://manufacturer.example/specs"),
            ("source_url", "https://manufacturer.example/unattached"),
            ("reviewed_at", None), ("reviewed_at", timezone.localdate() + timedelta(days=1)),
        ):
            with self.subTest(field=field, value=value):
                profile = ManufacturingProfile.objects.get(pk=self.profile.pk)
                setattr(profile, field, value)
                with self.assertRaises(ValidationError):
                    profile.save()

    def test_source_and_review_required_even_with_no_known_attributes(self):
        profile = ManufacturingProfile(asset=self.site)
        with self.assertRaises(ValidationError):
            profile.full_clean()

    def test_prefetch_avoids_per_row_evidence_queries(self):
        with self.assertNumQueries(2):
            candidates = manufacturing_candidates(
                Asset.public.select_related("manufacturing_profile").prefetch_related("sources")
            )
            rows = [compare_manufacturing(asset, {"process": "cnc-machining"})
                    for asset in candidates]
        self.assertEqual(rows[0]["state"], "match")


@override_settings(PUBLIC_REGION_SLUG="")
class ManufacturingSeedTests(ManufacturingFixtures, TestCase):
    def setUp(self):
        self.site = self.make_asset()
        self.source = self.make_source(self.site)

    def record(self, **overrides):
        values = self.profile_values()
        values["reviewed_at"] = values["reviewed_at"].isoformat()
        item = {
            "asset": {
                "name": self.site.name, "city": self.site.city, "state": self.site.state,
                "record_type": self.site.record_type, "provenance": "manufacturing-fixture",
            },
            "profile": values,
            "source": {
                "url": values["source_url"], "title": "Reviewed local capabilities",
                "notes": "Local source scope, not remote corporate capabilities.",
            },
        }
        item.update(overrides)
        return item

    @contextmanager
    def seed(self, records=None):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manufacturing.json"
            path.write_text(json.dumps({
                "schema_version": 1, "records": records if records is not None else [self.record()]
            }), encoding="utf-8")
            yield path

    def run_seed(self, **options):
        output = StringIO()
        with self.seed() as seed:
            call_command("seed_manufacturing_fit", seed=seed, stdout=output, **options)
        return output.getvalue()

    def test_default_is_read_only_preview(self):
        source_history = Source.history.count()
        output = self.run_seed()
        self.assertIn("Would create", output)
        self.assertFalse(ManufacturingProfile.objects.exists())
        self.assertEqual(Source.history.count(), source_history)

    def test_apply_is_insert_only_and_preserves_staff_profile_edits(self):
        self.run_seed(apply=True)
        profile = ManufacturingProfile.objects.get(asset=self.site)
        profile.notes = "Staff-authored scope remains authoritative."
        profile.save()
        self.run_seed(apply=True, add_missing_sources=True)
        profile.refresh_from_db()
        self.assertEqual(profile.notes, "Staff-authored scope remains authoritative.")
        self.assertEqual(ManufacturingProfile.objects.count(), 1)
        self.assertEqual(Source.objects.count(), 1)

    def test_missing_sources_require_explicit_opt_in(self):
        source_url = "https://manufacturer.example/new-reviewed-page"
        record = self.record()
        record["profile"]["source_url"] = source_url
        record["source"]["url"] = source_url
        with self.seed([record]) as seed:
            call_command("seed_manufacturing_fit", seed=seed, apply=True, stdout=StringIO())
            self.assertFalse(ManufacturingProfile.objects.exists())
            call_command(
                "seed_manufacturing_fit", seed=seed, add_missing_sources=True, stdout=StringIO()
            )
            self.assertFalse(Source.objects.filter(url=source_url).exists())
            call_command(
                "seed_manufacturing_fit", seed=seed, apply=True, add_missing_sources=True,
                stdout=StringIO(),
            )
        profile = ManufacturingProfile.objects.get(asset=self.site)
        self.assertEqual(profile.source_url, source_url)
        source = Source.objects.get(asset=self.site, url=source_url)
        self.assertTrue(source.is_public)
        self.assertEqual(source.verification_status, "verified")

    def test_existing_profile_blocks_even_new_source_creation(self):
        ManufacturingProfile.objects.create(asset=self.site, **self.profile_values())
        record = self.record()
        record["profile"]["source_url"] = "https://manufacturer.example/new"
        record["source"]["url"] = record["profile"]["source_url"]
        with self.seed([record]) as seed:
            call_command(
                "seed_manufacturing_fit", seed=seed, apply=True, add_missing_sources=True,
                stdout=StringIO(),
            )
        self.assertEqual(Source.objects.count(), 1)

    def test_private_stale_rejected_and_retired_sources_are_never_repaired(self):
        for updates in (
            {"is_public": False}, {"verification_status": "stale"},
            {"verification_status": "rejected"}, {"link_review_status": "needs-replacement"},
        ):
            with self.subTest(updates=updates):
                Source.objects.filter(pk=self.source.pk).update(
                    is_public=True, verification_status="unreviewed", link_review_status="automatic"
                )
                Source.objects.filter(pk=self.source.pk).update(**updates)
                self.run_seed(apply=True, add_missing_sources=True)
                self.assertFalse(ManufacturingProfile.objects.exists())
                self.source.refresh_from_db()
                for field, value in updates.items():
                    self.assertEqual(getattr(self.source, field), value)
        self.source.delete()
        self.run_seed(apply=True, add_missing_sources=True)
        self.assertFalse(Source.objects.exists())
        self.assertFalse(ManufacturingProfile.objects.exists())

    def test_changed_or_attributed_staff_assets_are_skipped(self):
        user = get_user_model().objects.create_user(username="manufacturing-editor")
        for updates in (
            {"city": "Other city"}, {"internal_notes": "Staff notes"},
            {"reviewed_by": user}, {"visibility": "internal"}, {"activity_status": "historical"},
        ):
            with self.subTest(updates=updates):
                Asset.objects.filter(pk=self.site.pk).update(**updates)
                self.run_seed(apply=True, add_missing_sources=True)
                self.assertFalse(ManufacturingProfile.objects.exists())
                Asset.objects.filter(pk=self.site.pk).update(
                    city=self.site.city, internal_notes=self.site.internal_notes, reviewed_by=None,
                    visibility="public", activity_status="",
                )
        self.site._history_user = user
        self.site.save()
        self.run_seed(apply=True)
        self.assertFalse(ManufacturingProfile.objects.exists())

    def test_missing_assets_are_not_created(self):
        self.site.delete()
        self.run_seed(apply=True, add_missing_sources=True)
        self.assertFalse(Asset.objects.exists())
        self.assertFalse(ManufacturingProfile.objects.exists())

    def test_manifest_fully_validated_before_any_write(self):
        bad = self.record()
        bad["asset"]["name"] = "Other seed identity"
        bad["profile"]["materials"] = ["invented"]
        with self.seed([self.record(), bad]) as seed, self.assertRaises(CommandError):
            call_command("seed_manufacturing_fit", seed=seed, apply=True, stdout=StringIO())
        self.assertFalse(ManufacturingProfile.objects.exists())

    def test_seed_dates_source_urls_and_duplicate_identities_are_validated(self):
        invalid_records = []
        for field, value in (
            ("reviewed_at", None),
            ("reviewed_at", (timezone.localdate() + timedelta(days=1)).isoformat()),
            ("source_url", "ftp://manufacturer.example/source"),
        ):
            record = self.record()
            record["profile"][field] = value
            if field == "source_url":
                record["source"]["url"] = value
            invalid_records.append([record])
        mismatched = self.record()
        mismatched["source"]["url"] += "-different"
        invalid_records.extend([[mismatched], [self.record(), self.record()]])
        for records in invalid_records:
            with self.subTest(records=records), self.seed(records) as seed:
                with self.assertRaises(CommandError):
                    call_command("seed_manufacturing_fit", seed=seed, apply=True, stdout=StringIO())
        self.assertFalse(ManufacturingProfile.objects.exists())

    def test_bundled_seed_is_small_site_specific_and_conservative(self):
        records = load_seed(settings.BASE_DIR / "data" / "manufacturing_fit_2026_11_11.json")
        self.assertEqual(len(records), 8)
        by_name = {identity["name"]: values for identity, values, source in records}
        self.assertEqual(by_name["Allocortech"]["processes"], ["electronics-assembly"])
        self.assertEqual(by_name["Kollmorgen Radford Motion Systems"]["access_types"], [])
        self.assertEqual(by_name["Moog Blacksburg Power and Data Division"]["access_types"], [])
        for identity in (
            "Kollmorgen Radford Motion Systems", "Moog Blacksburg Power and Data Division"
        ):
            self.assertNotIn("contract-manufacturing", by_name[identity]["service_modes"])
        radian = by_name["Radian Forge Portsmouth Manufacturing Facility"]
        self.assertNotIn("cnc-machining", radian["processes"])
        self.assertNotIn("titanium", radian["materials"])
