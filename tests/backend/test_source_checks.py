from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Asset
from apps.sources.management.commands.check_source_links import check_url
from apps.sources.models import Source


class SourceLinkCheckTests(TestCase):
    def test_long_public_evidence_urls_are_saved_without_truncation(self):
        asset = Asset.objects.create(
            name="Long source URL",
            record_type=Asset.RecordType.FACILITY,
            short_description="Fixture",
            unmanned_systems_relevance="Testing",
        )
        url = "https://example.org/official-evidence?address=" + "a" * 300
        source = Source.objects.create(asset=asset, title="Evidence URL", url=url)
        source.refresh_from_db()
        self.assertEqual(source.url, url)
        self.assertEqual(source.history.latest().url, url)

    def test_changing_url_resets_old_link_results_but_other_edits_preserve_them(self):
        asset = Asset.objects.create(
            name="Changing source",
            record_type=Asset.RecordType.FACILITY,
            short_description="Fixture",
            unmanned_systems_relevance="Testing",
        )
        source = Source.objects.create(
            asset=asset,
            title="Official source",
            url="https://example.org/old",
            last_checked_at=timezone.now(),
            http_status=403,
            check_error="Old URL error",
            verification_status="verified",
            last_verified_at=timezone.localdate(),
            link_review_status=Source.LinkReviewStatus.ACCEPTED,
            link_review_notes="Reviewed in browser",
        )
        source.title = "Updated title"
        source.save(update_fields=["title"])
        source.refresh_from_db()
        self.assertEqual(source.http_status, 403)
        self.assertEqual(source.link_review_status, Source.LinkReviewStatus.ACCEPTED)
        self.assertEqual(source.verification_status, "verified")
        source.url = "https://example.org/replacement"
        source.save(update_fields=["url"])
        source.refresh_from_db()
        self.assertIsNone(source.http_status)
        self.assertIsNone(source.last_checked_at)
        self.assertEqual(source.check_error, "")
        self.assertEqual(source.link_review_status, Source.LinkReviewStatus.AUTOMATIC)
        self.assertEqual(source.link_review_notes, "")
        self.assertEqual(source.verification_status, "unreviewed")
        self.assertIsNone(source.last_verified_at)

    def test_internal_network_urls_are_blocked_before_request(self):
        status, error = check_url("http://127.0.0.1/admin/")
        self.assertIsNone(status)
        self.assertIn("blocked", error)

    def test_head_error_is_retried_with_a_small_get_request(self):
        opener = MagicMock()
        response = MagicMock()
        response.__enter__.return_value.status = 200
        opener.open.side_effect = [
            HTTPError("https://example.test/source", 404, "Not Found", {}, None),
            response,
        ]

        with (
            patch("apps.sources.management.commands.check_source_links.validate_public_url"),
            patch(
                "apps.sources.management.commands.check_source_links.build_opener",
                return_value=opener,
            ),
        ):
            status, error = check_url("https://example.test/source")

        self.assertEqual(status, 200)
        self.assertEqual(error, "")
        self.assertEqual(opener.open.call_count, 2)

    def test_command_records_latest_link_status(self):
        asset = Asset.objects.create(
            name="Source Check Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="Fixture",
            unmanned_systems_relevance="Fixture relevance",
        )
        source = Source.objects.create(
            asset=asset,
            title="Fixture source",
            url="https://example.test/source",
        )
        Source.objects.bulk_create(
            [
                Source(
                    asset=asset,
                    title=f"Fixture source {index}",
                    url=f"https://example.test/source/{index}",
                )
                for index in range(100)
            ]
        )
        Source.objects.create(
            asset=asset,
            title="Duplicate fixture URL",
            url="https://example.test/source",
        )
        with patch(
            "apps.sources.management.commands.check_source_links.check_url",
            return_value=(200, ""),
        ) as mocked_check:
            call_command("check_source_links", "--all", verbosity=0)
        source.refresh_from_db()
        self.assertEqual(source.http_status, 200)
        self.assertIsNotNone(source.last_checked_at)
        self.assertEqual(source.check_error, "")
        self.assertEqual(Source.objects.filter(last_checked_at__isnull=False).count(), 102)
        self.assertEqual(mocked_check.call_count, 101)

    def test_command_keeps_checking_after_an_unexpected_network_failure(self):
        asset = Asset.objects.create(
            name="Source Check Failure Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="Fixture",
            unmanned_systems_relevance="Fixture relevance",
        )
        failed_source = Source.objects.create(
            asset=asset,
            title="Reset source",
            url="https://reset.example.test/source",
        )
        working_source = Source.objects.create(
            asset=asset,
            title="Working source",
            url="https://working.example.test/source",
        )

        def result_for(url):
            if "reset" in url:
                raise ConnectionResetError("Connection reset by peer")
            return 200, ""

        with patch(
            "apps.sources.management.commands.check_source_links.check_url",
            side_effect=result_for,
        ):
            call_command("check_source_links", "--all", "--workers", "2", verbosity=0)

        failed_source.refresh_from_db()
        working_source.refresh_from_db()
        self.assertIsNone(failed_source.http_status)
        self.assertIn("Connection reset by peer", failed_source.check_error)
        self.assertEqual(working_source.http_status, 200)
        self.assertEqual(working_source.check_error, "")
