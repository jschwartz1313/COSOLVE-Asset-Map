import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.assets.models import Asset
from apps.sources.models import Source


class SourceAuditImportTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            name="Source audit fixture",
            record_type=Asset.RecordType.FACILITY,
            short_description="Fixture",
            unmanned_systems_relevance="Fixture",
        )
        self.checked_at = timezone.now()

    def source(self, **kwargs):
        return Source.objects.create(
            asset=self.asset,
            title="Official source",
            url=kwargs.pop("url", "https://example.org/evidence"),
            **kwargs,
        )

    def observation(self, **kwargs):
        return {
            "url": "https://example.org/evidence",
            "checked_at": self.checked_at.isoformat(),
            "http_status": 200,
            "classification": "reachable",
            **kwargs,
        }

    def run_audit(self, observations, *args):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps({"urls": observations}))
            call_command("apply_source_audit", "--path", str(path), *args, verbosity=0)

    def test_updates_exact_matching_public_urls_and_keeps_manual_decisions(self):
        accepted = self.source(
            verification_status="verified",
            last_verified_at=self.checked_at.date(),
            notes="Checked substantive claims independently.",
            link_review_status=Source.LinkReviewStatus.ACCEPTED,
            link_review_notes="Readable in a regular browser.",
        )
        replacement = self.source(
            link_review_status=Source.LinkReviewStatus.NEEDS_REPLACEMENT,
            link_review_notes="Wrong evidence despite accessible page.",
        )
        different_url = self.source(url="https://example.org/evidence/")
        private = self.source(is_public=False)
        self.run_audit(
            [self.observation(http_status=403, classification="access_blocked_or_rate_limited")]
        )
        accepted.refresh_from_db()
        replacement.refresh_from_db()
        different_url.refresh_from_db()
        private.refresh_from_db()
        self.assertEqual(accepted.http_status, 403)
        self.assertEqual(accepted.last_checked_at, self.checked_at)
        self.assertIn("inconclusive", accepted.check_error)
        self.assertEqual(accepted.verification_status, "verified")
        self.assertEqual(accepted.last_verified_at, self.checked_at.date())
        self.assertEqual(accepted.notes, "Checked substantive claims independently.")
        self.assertEqual(accepted.link_review_notes, "Readable in a regular browser.")
        self.assertEqual(accepted.link_review_status, Source.LinkReviewStatus.ACCEPTED)
        self.assertFalse(accepted.has_link_issue)
        self.assertEqual(replacement.link_review_status, Source.LinkReviewStatus.NEEDS_REPLACEMENT)
        self.assertTrue(replacement.has_link_issue)
        self.assertIsNone(different_url.last_checked_at)
        self.assertIsNone(private.last_checked_at)

    def test_equal_or_newer_database_checks_are_not_overwritten(self):
        newer = self.source(last_checked_at=self.checked_at + timedelta(days=1), http_status=404)
        equal = self.source(last_checked_at=self.checked_at, http_status=403)
        self.run_audit([self.observation()])
        newer.refresh_from_db()
        equal.refresh_from_db()
        self.assertEqual(newer.http_status, 404)
        self.assertEqual(equal.http_status, 403)

    def test_success_clears_only_older_mechanical_failure_and_rerun_is_idempotent(self):
        source = self.source(
            last_checked_at=self.checked_at - timedelta(days=1),
            http_status=500,
            check_error="Previous transport failure",
        )
        self.run_audit([self.observation()])
        history_count = source.history.count()
        self.run_audit([self.observation()])
        source.refresh_from_db()
        self.assertEqual(source.http_status, 200)
        self.assertEqual(source.check_error, "")
        self.assertEqual(source.history.count(), history_count)
        self.assertEqual(source.verification_status, "unreviewed")
        self.assertIsNone(source.last_verified_at)

    def test_network_failure_and_homepage_redirect_remain_reviewable(self):
        network = self.source()
        redirect = self.source(url="https://example.org/old-specific-page")
        self.run_audit(
            [
                self.observation(
                    http_status=None, classification="network_or_tls_error", error="TLS failed"
                ),
                self.observation(url=redirect.url, classification="redirected_to_homepage_review"),
            ]
        )
        network.refresh_from_db()
        redirect.refresh_from_db()
        self.assertIsNone(network.http_status)
        self.assertIn("TLS failed", network.check_error)
        self.assertTrue(network.has_link_issue)
        self.assertEqual(redirect.http_status, 200)
        self.assertTrue(redirect.has_link_issue)

    def test_invalid_observation_prevents_all_writes(self):
        source = self.source()
        for invalid in (
            self.observation(url="https://example.org/invalid", checked_at="2026-09-04T12:00:00"),
            self.observation(url="https://example.org/invalid", http_status=True),
            self.observation(url="https://example.org/invalid", classification="made-up"),
            self.observation(),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(CommandError):
                self.run_audit([self.observation(), invalid])
            source.refresh_from_db()
            self.assertIsNone(source.last_checked_at)

    def test_dry_run_does_not_write(self):
        source = self.source()
        history_count = source.history.count()
        self.run_audit([self.observation()], "--dry-run")
        source.refresh_from_db()
        self.assertIsNone(source.last_checked_at)
        self.assertEqual(source.history.count(), history_count)
