import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset
from apps.sources.models import Source


class PeerWebsiteCorrectionTests(TestCase):
    def test_unresolved_broken_website_can_be_suppressed_without_removing_evidence(self):
        asset = self.make_asset()
        Source.objects.create(asset=asset, title="Historical evidence", url=asset.website_url)
        self.correct(asset, new_url="")
        asset.refresh_from_db()
        self.assertEqual(asset.website_url, "")
        self.assertEqual(asset.contact_url, "")
        self.assertEqual(asset.sources.count(), 1)
        self.assertEqual(asset.sources.get().url, "https://old.example.edu/")

    def test_baseline_links_change_once_but_status_and_prior_sources_remain(self):
        asset = self.make_asset()
        old = Source.objects.create(asset=asset, title="Original evidence", url=asset.website_url)
        self.correct(asset)
        asset.refresh_from_db()
        self.assertEqual(asset.website_url, "https://new.example.edu/")
        self.assertEqual(asset.contact_url, asset.website_url)
        self.assertEqual(asset.status, Asset.Status.SOURCE_BACKED)
        self.assertEqual(asset.visibility, Asset.Visibility.INTERNAL)
        self.assertIsNone(asset.reviewed_by)
        old.refresh_from_db()
        self.assertEqual(old.url, "https://old.example.edu/")
        self.assertEqual(asset.sources.count(), 2)
        self.assertEqual(asset.sources.get(url=asset.website_url).verification_status, "unreviewed")
        self.correct(asset)
        self.assertEqual(asset.sources.count(), 2)

    def test_later_staff_edits_and_deleted_evidence_are_preserved(self):
        for protection in ("asset", "source", "deleted", "website", "virginia", "public"):
            asset = self.make_asset(name=f"Protected {protection}")
            user = get_user_model().objects.create_user(username=f"staff-{protection}")
            if protection == "asset":
                asset._history_user = user
                asset.save()
            elif protection == "source":
                source = Source(
                    asset=asset, title="Staff evidence", url="https://staff.example.edu/"
                )
                source._history_user = user
                source.save()
            elif protection == "deleted":
                source = Source.objects.create(
                    asset=asset, title="Retired", url="https://new.example.edu/"
                )
                source.delete()
            elif protection == "website":
                asset.website_url = "https://different.example.edu/"
                asset.save()
            elif protection == "virginia":
                asset.state = "VA"
                asset.save()
            elif protection == "public":
                asset.visibility = Asset.Visibility.PUBLIC
                asset.save()
            expected = asset.website_url
            self.correct(asset)
            asset.refresh_from_db()
            self.assertEqual(asset.website_url, expected, protection)

    def make_asset(self, name="Imported peer"):
        return Asset.objects.create(
            name=name,
            state="OH",
            record_type="organization",
            short_description="A preview record.",
            unmanned_systems_relevance="Supporting research.",
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.INTERNAL,
            benchmark_starter=True,
            website_url="https://old.example.edu/",
            contact_url="https://old.example.edu/",
        )

    def correct(self, asset, new_url="https://new.example.edu/"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrections.json"
            path.write_text(
                json.dumps(
                    {
                        "research_date": "2026-11-18",
                        "corrections": [
                            {
                                "state": "OH",
                                "name": asset.name,
                                "old_url": "https://old.example.edu/",
                                "new_url": new_url,
                                "source_title": "Current official website",
                                "supports": "Official replacement confirms the entity's identity.",
                            }
                        ],
                    }
                )
            )
            call_command(
                "correct_peer_websites", corrections=path, apply=True, stdout=io.StringIO()
            )
