import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ReleaseScriptTests(SimpleTestCase):
    def test_production_requires_explicit_false_to_publish(self):
        for value, expected in [(None, "True"), ("", "True"), ("false", "False")]:
            with self.subTest(value=value):
                environment = {
                    "DJANGO_SECRET_KEY": "test-production-secret-not-used-by-a-server",
                    "DJANGO_ALLOWED_HOSTS": "example.com",
                    "DATABASE_URL": "sqlite:///:memory:",
                }
                if value is not None:
                    environment["REQUIRE_SITE_LOGIN"] = value
                result = subprocess.run(
                    [sys.executable, "-c",
                     "from unittest.mock import patch\n"
                     "with patch('dotenv.load_dotenv'):\n"
                     " from config.settings.production import REQUIRE_SITE_LOGIN\n"
                     " print(REQUIRE_SITE_LOGIN)"],
                    cwd=settings.BASE_DIR, env=environment, capture_output=True,
                    text=True, check=True,
                )
                self.assertEqual(result.stdout.strip(), expected)

    def run_script(self, name, *, failure=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "commands.log"
            stub = (
                '#!/bin/bash\n'
                'printf "%s %s\\n" "$(basename "$0")" "$*" >> "$COMMAND_LOG"\n'
                'if [[ -n "$FAIL_COMMAND" && "$*" == *"$FAIL_COMMAND"* ]]; then exit 23; fi\n'
            )
            for binary in ["python", "gunicorn"]:
                path = root / binary
                path.write_text(stub)
                path.chmod(0o700)
            result = subprocess.run(
                ["bash", name], cwd=settings.BASE_DIR, capture_output=True, text=True,
                env={**os.environ, "PATH": f"{root}:{os.environ['PATH']}",
                     "COMMAND_LOG": str(log), "FAIL_COMMAND": failure, "PORT": "8123"},
                check=False,
            )
            return result.returncode, log.read_text().splitlines()

    def test_build_never_mutates_database(self):
        code, commands = self.run_script("build.sh")
        self.assertEqual(code, 0)
        self.assertEqual(commands, [
            "python -m pip install -e .", "python manage.py collectstatic --noinput",
        ])

    def test_failed_build_stops_without_database_changes(self):
        code, commands = self.run_script("build.sh", failure="pip install")
        self.assertEqual(code, 23)
        self.assertEqual(len(commands), 1)

    def test_start_releases_before_serving_and_never_recovers_accounts(self):
        code, commands = self.run_script("start.sh")
        self.assertEqual(code, 0)
        self.assertEqual(commands[0], "python manage.py migrate --noinput")
        self.assertEqual(commands[-2], "python manage.py ensure_admin_user --skip-recovery")
        self.assertEqual(commands[-1], "gunicorn config.wsgi:application --bind 0.0.0.0:8123")

    def test_failed_release_does_not_start_server(self):
        code, commands = self.run_script("start.sh", failure="migrate")
        self.assertEqual(code, 23)
        self.assertEqual(commands, ["python manage.py migrate --noinput"])

    def test_paid_release_is_separate_and_both_blueprints_are_private(self):
        root = settings.BASE_DIR
        for filename in ["render.yaml", "render.production.yaml"]:
            blueprint = (root / filename).read_text()
            self.assertIn('key: REQUIRE_SITE_LOGIN\n        value: "true"', blueprint)
        self.assertIn("startCommand: bash start.sh", (root / "render.yaml").read_text())
        self.assertIn(
            "preDeployCommand: bash release.sh", (root / "render.production.yaml").read_text()
        )
