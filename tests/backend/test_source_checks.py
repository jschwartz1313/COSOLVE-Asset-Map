from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.assets.models import Asset
from apps.sources.models import Source


class SourceLinkCheckTests(TestCase):
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
        with patch(
            "apps.sources.management.commands.check_source_links.check_url",
            return_value=(200, ""),
        ):
            call_command("check_source_links", "--all", verbosity=0)
        source.refresh_from_db()
        self.assertEqual(source.http_status, 200)
        self.assertIsNotNone(source.last_checked_at)
        self.assertEqual(source.check_error, "")
        self.assertEqual(Source.objects.filter(last_checked_at__isnull=False).count(), 101)
