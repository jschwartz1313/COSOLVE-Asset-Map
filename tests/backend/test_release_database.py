import subprocess
from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase

from apps.core.models import CompletedRelease


class ReleaseDatabaseTests(TestCase):
    def run_release(self, version="a" * 40, *, force=False):
        with patch.dict("os.environ", {"RENDER_GIT_COMMIT": version}):
            call_command("release_database", force=force, stdout=StringIO())

    @patch("apps.assets.management.commands.release_database.subprocess.run")
    def test_release_runs_once_per_version_and_repeats_for_new_version(self, run):
        self.run_release()
        self.run_release()
        self.assertEqual(run.call_count, 1)
        self.run_release("b" * 40)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(CompletedRelease.objects.count(), 2)

    @patch("apps.assets.management.commands.release_database.subprocess.run")
    def test_forced_release_reapplies_without_duplicate_record(self, run):
        self.run_release()
        self.run_release(force=True)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(CompletedRelease.objects.count(), 1)

    @patch("apps.assets.management.commands.release_database.subprocess.run")
    def test_failed_release_is_not_marked_complete_and_can_retry(self, run):
        run.side_effect = subprocess.CalledProcessError(1, "release.sh")
        with self.assertRaisesMessage(CommandError, "completion was not recorded"):
            self.run_release()
        self.assertFalse(CompletedRelease.objects.exists())
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                               "AND pid = pg_backend_pid()")
                self.assertEqual(cursor.fetchone()[0], 0)
        run.side_effect = None
        self.run_release()
        self.assertTrue(CompletedRelease.objects.exists())

    @patch("apps.assets.management.commands.release_database.subprocess.run")
    def test_missing_version_runs_manual_release_without_recording(self, run):
        self.run_release("")
        self.assertEqual(run.call_count, 1)
        self.assertFalse(CompletedRelease.objects.exists())

    @patch("apps.assets.management.commands.release_database.subprocess.run")
    def test_invalid_version_fails_without_running_release(self, run):
        with self.assertRaisesMessage(CommandError, "full commit SHA"):
            self.run_release("invalid")
        run.assert_not_called()

    @patch("apps.assets.management.commands.release_database.subprocess.run")
    def test_first_deployment_handles_missing_marker_table(self, run):
        with patch.object(connection.introspection, "table_names", return_value=[]):
            self.run_release()
        run.assert_called_once()
        self.assertTrue(CompletedRelease.objects.exists())
