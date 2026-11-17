"""Run the existing ordered release manifest without restarting Django per step."""

import shlex

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


def release_steps(path):
    steps = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#") or line == "set -euo pipefail":
            continue
        tokens = shlex.split(line, comments=True)
        if len(tokens) < 3 or tokens[:2] != ["python", "manage.py"]:
            raise CommandError(f"Unsupported release manifest instruction on line {number}.")
        if tokens[2] in {"apply_release_steps", "release_database", "runserver"}:
            raise CommandError("A release manifest cannot recursively release or start a server.")
        steps.append(tokens[2:])
    if not steps or steps[0][0] != "migrate":
        raise CommandError("The release manifest must begin with migrations.")
    return steps


class Command(BaseCommand):
    help = "Run the guarded release.sh management commands in one Django process."

    def handle(self, *args, **options):
        steps = release_steps(settings.BASE_DIR / "release.sh")
        for command, *arguments in steps:
            self.stdout.write(f"Release step: {command}")
            self.stdout.flush()
            call_command(command, *arguments, stdout=self.stdout, stderr=self.stderr)
