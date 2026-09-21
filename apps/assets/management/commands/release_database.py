import os
import re
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.models import CompletedRelease

RELEASE_LOCK = 678655001


class Command(BaseCommand):
    help = "Apply database release steps once per commit, serializing PostgreSQL releases."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Reapply a completed release.")

    def handle(self, *args, **options):
        version = os.getenv("RENDER_GIT_COMMIT", "").strip()
        if version and not re.fullmatch(r"[0-9a-fA-F]{40,64}", version):
            raise CommandError("RENDER_GIT_COMMIT must be a full commit SHA.")

        # The lock survives child processes and is released even if a release fails.
        postgres = connection.vendor == "postgresql"
        if postgres:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", [RELEASE_LOCK])
        try:
            table_exists = CompletedRelease._meta.db_table in connection.introspection.table_names()
            if (
                version and table_exists and not options["force"]
                and CompletedRelease.objects.filter(pk=version).exists()
            ):
                self.stdout.write(
                    "Database release already completed; starting without data updates."
                )
                return
            try:
                subprocess.run(["bash", "release.sh"], cwd=settings.BASE_DIR, check=True)
            except subprocess.CalledProcessError as exc:
                raise CommandError(
                    "Database release failed; completion was not recorded "
                    "and server will not start."
                ) from exc
            if version:
                CompletedRelease.objects.update_or_create(version=version)
            self.stdout.write(self.style.SUCCESS("Database release completed."))
        finally:
            if postgres:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [RELEASE_LOCK])
