import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial superuser or perform an explicitly requested recovery."

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()
        reset_requested = os.getenv("DJANGO_SUPERUSER_RESET", "false").lower() == "true"

        if reset_requested:
            if not username or not password:
                raise CommandError(
                    "Administrator recovery requires DJANGO_SUPERUSER_USERNAME and "
                    "DJANGO_SUPERUSER_PASSWORD."
                )
            user = user_model.objects.filter(username=username).first()
            if user is None:
                administrators = list(user_model.objects.filter(is_superuser=True)[:2])
                if len(administrators) > 1:
                    raise CommandError(
                        "Multiple administrators exist. Set DJANGO_SUPERUSER_USERNAME "
                        "to an existing administrator before requesting recovery."
                    )
                user = administrators[0] if administrators else user_model()
                user.username = username

            if email:
                user.email = email
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Recovered administrator {username!r}. "
                    "Remove DJANGO_SUPERUSER_RESET after signing in."
                )
            )
            return

        if user_model.objects.filter(is_superuser=True).exists():
            self.stdout.write("An administrator already exists; no account changes were made.")
            return

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
