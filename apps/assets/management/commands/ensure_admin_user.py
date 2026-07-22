import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial superuser when no superuser exists."

    def handle(self, *args, **options):
        user_model = get_user_model()
        if user_model.objects.filter(is_superuser=True).exists():
            self.stdout.write("An administrator already exists; no account changes were made.")
            return

        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username or not password:
            raise CommandError(
                "No administrator exists. Set DJANGO_SUPERUSER_USERNAME and "
                "DJANGO_SUPERUSER_PASSWORD for the initial deployment."
            )
        if user_model.objects.filter(username=username).exists():
            raise CommandError(
                f"User {username!r} exists but is not a superuser; choose another initial username."
            )

        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(f"Created initial administrator {username!r}."))
