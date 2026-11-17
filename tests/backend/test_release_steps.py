import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.assets.management.commands.apply_release_steps import release_steps


class ReleaseStepsTests(SimpleTestCase):
    def test_manifest_requires_migrations_and_rejects_unsupported_or_recursive_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release.sh"
            for content in (
                "python manage.py seed_peer_states --apply",
                "python manage.py migrate --noinput\necho unsafe",
                "python manage.py migrate --noinput\npython manage.py release_database",
            ):
                path.write_text(content)
                with self.assertRaises(CommandError):
                    release_steps(path)
            path.write_text("#!/bin/bash\nset -euo pipefail\n# ordered steps\n"
                            "python manage.py migrate --noinput\n"
                            "python manage.py seed_peer_states --apply\n")
            self.assertEqual(release_steps(path), [
                ["migrate", "--noinput"], ["seed_peer_states", "--apply"],
            ])

    @patch("apps.assets.management.commands.apply_release_steps.release_steps")
    @patch("apps.assets.management.commands.apply_release_steps.call_command")
    def test_in_process_runner_preserves_order_and_stops_on_failure(self, run, manifest):
        manifest.return_value = [["migrate", "--noinput"], ["seed_peer_states", "--apply"]]
        output = io.StringIO()
        errors = io.StringIO()
        call_command("apply_release_steps", stdout=output, stderr=errors)
        self.assertEqual([item.args for item in run.call_args_list], [
            ("migrate", "--noinput"), ("seed_peer_states", "--apply"),
        ])
        self.assertIs(run.call_args.kwargs["stdout"]._out, output)
        self.assertIs(run.call_args.kwargs["stderr"]._out, errors)
        run.reset_mock()
        run.side_effect = CommandError("Migration failed")
        with self.assertRaisesMessage(CommandError, "Migration failed"):
            call_command("apply_release_steps", stdout=output, stderr=errors)
        self.assertEqual(run.call_count, 1)
