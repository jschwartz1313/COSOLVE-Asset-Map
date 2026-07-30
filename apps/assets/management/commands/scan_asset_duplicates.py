from django.core.management.base import BaseCommand

from apps.assets.quality import sync_duplicate_candidates


class Command(BaseCommand):
    help = "Detect likely duplicate asset records and refresh the duplicate review queue."

    def handle(self, *args, **options):
        result = sync_duplicate_candidates()
        self.stdout.write(
            self.style.SUCCESS(
                "Duplicate scan complete: "
                f"{result['detected']} detected, "
                f"{result['created']} created, "
                f"{result['updated']} updated, "
                f"{result['removed']} removed."
            )
        )
