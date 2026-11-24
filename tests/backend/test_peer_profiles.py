import json
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.assets.geography import BY_CODE
from apps.assets.models import Asset
from apps.sources.models import Source


class PeerProfileTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            name="Peer integration laboratory", state="OH", record_type="facility",
            short_description="A real test fixture.", overview="Original overview.",
            unmanned_systems_relevance="UAS testing.", benchmark_starter=True,
            status="source-backed", visibility="internal",
        )
        self.document = {
            "research_date":"2026-11-24",
            "profiles":[{
                "state":"OH", "name":self.asset.name,
                "before":{"overview":"Original overview.", "contact_text":""},
                "after":{"overview":"Documented uses and access conditions.",
                         "contact_text":"Published project inquiry route."},
                "sources":[{"title":"Operator capabilities",
                            "url":"https://operator.example/capabilities",
                            "supports":"Named test capabilities and project intake."}],
            }],
        }

    def run_update(self, apply=True):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            path.write_text(json.dumps(self.document))
            output = StringIO()
            call_command("enrich_peer_profiles", profiles=path, apply=apply, stdout=output)
            return output.getvalue()

    def test_preview_does_not_write_and_apply_is_internal_and_idempotent(self):
        original_history = self.asset.history.count()
        self.assertIn("Would enrich 1", self.run_update(apply=False))
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.overview, "Original overview.")
        self.assertEqual(self.asset.history.count(), original_history)
        self.assertFalse(self.asset.sources.exists())
        self.assertIn("Enriched 1", self.run_update())
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.overview, "Documented uses and access conditions.")
        self.assertEqual(self.asset.visibility, "internal")
        self.assertIsNone(self.asset.last_verified_at)
        self.assertIsNone(self.asset.reviewed_at)
        source = self.asset.sources.get()
        self.assertEqual(source.verification_status, "unreviewed")
        self.assertIsNone(source.last_verified_at)
        history = self.asset.history.count()
        self.assertIn("1 already applied", self.run_update())
        self.assertEqual(self.asset.history.count(), history)
        self.assertEqual(self.asset.review_comments.count(), 1)
        self.assertEqual(self.asset.sources.count(), 1)

    def test_one_changed_baseline_preserves_the_whole_profile(self):
        self.asset.contact_text = "Independently maintained contact."
        self.asset.save()
        self.assertIn("preserved 1", self.run_update())
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.overview, "Original overview.")
        self.assertEqual(self.asset.contact_text, "Independently maintained contact.")

    def test_staff_review_assignments_and_attributed_history_are_preserved(self):
        user = get_user_model().objects.create_user("peer-editor")
        for changes in (
            {"review_assignee":user}, {"review_due_at":date(2026,12,1)},
            {"last_verified_at":date(2026,11,1)}, {"visibility":"public"},
            {"benchmark_starter":False},
        ):
            with self.subTest(changes=changes):
                Asset.objects.filter(pk=self.asset.pk).update(**changes)
                self.assertIn("preserved 1", self.run_update())
                Asset.objects.filter(pk=self.asset.pk).update(
                    review_assignee=None, review_due_at=None, last_verified_at=None,
                    visibility="internal", benchmark_starter=True,
                )
        self.asset._history_user = user
        self.asset.save()
        self.assertIn("preserved 1", self.run_update())

    def test_hidden_rejected_or_deleted_sources_are_not_restored(self):
        url = self.document["profiles"][0]["sources"][0]["url"]
        source = Source.objects.create(asset=self.asset, title="Prior decision", url=url,
                                       is_public=False)
        self.assertIn("preserved 1", self.run_update())
        source.is_public = True
        source.verification_status = "rejected"
        source.save()
        self.assertIn("preserved 1", self.run_update())
        source.delete()
        self.assertIn("preserved 1", self.run_update())
        self.assertFalse(self.asset.sources.exists())

    def test_manifest_cannot_change_visibility_or_touch_virginia(self):
        self.document["profiles"][0]["before"]["visibility"] = "internal"
        self.document["profiles"][0]["after"]["visibility"] = "public"
        with self.assertRaises(CommandError):
            self.run_update()
        self.document["profiles"][0]["before"].pop("visibility")
        self.document["profiles"][0]["after"].pop("visibility")
        self.document["profiles"][0]["state"] = "VA"
        with self.assertRaises(CommandError):
            self.run_update()

    def test_shipped_profiles_cover_all_peer_states_and_retain_claim_sources(self):
        document = json.loads(
            (settings.BASE_DIR / "data/multistate/profiles_2026_11_24.json").read_text()
        )
        self.assertEqual({row["state"] for row in document["profiles"]}, set(BY_CODE) - {"VA"})
        for row in document["profiles"]:
            self.assertEqual(set(row["before"]), set(row["after"]))
            self.assertGreater(len(row["after"]["overview"]), 400)
            self.assertTrue(row["sources"])
            for source in row["sources"]:
                self.assertTrue(source["supports"])
                self.assertTrue(source["url"].startswith("https://"))
