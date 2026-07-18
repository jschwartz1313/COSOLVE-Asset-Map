from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.sources.models import Source


def check_url(url):
    headers = {"User-Agent": "COSOLVE-Asset-Map/1.0 source-maintenance"}
    try:
        request = Request(url, headers=headers, method="HEAD")
        with urlopen(request, timeout=12) as response:  # noqa: S310
            return response.status, ""
    except HTTPError as error:
        if error.code not in {403, 405}:
            return error.code, ""
    except (TimeoutError, URLError) as error:
        return None, str(error.reason if isinstance(error, URLError) else error)[:240]

    try:
        request = Request(url, headers={**headers, "Range": "bytes=0-0"})
        with urlopen(request, timeout=15) as response:  # noqa: S310
            return response.status, ""
    except HTTPError as error:
        return error.code, ""
    except (TimeoutError, URLError) as error:
        return None, str(error.reason if isinstance(error, URLError) else error)[:240]


class Command(BaseCommand):
    help = "Check public source URLs and store their latest HTTP status."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Recheck every public source.")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--workers", type=int, default=8)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=7)
        queryset = Source.objects.filter(is_public=True).exclude(url="")
        if not options["all"]:
            queryset = queryset.filter(
                Q(last_checked_at__isnull=True) | Q(last_checked_at__lt=cutoff)
            )
        queryset = queryset.order_by("last_checked_at", "pk")
        limit = (
            options["limit"]
            if options["limit"] is not None
            else (None if options["all"] else 100)
        )
        sources = list(queryset[:limit] if limit is not None else queryset)
        checked_at = timezone.now()
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, options["workers"])) as executor:
            futures = {executor.submit(check_url, source.url): source for source in sources}
            for future in as_completed(futures):
                results[futures[future].pk] = future.result()

        failures = 0
        for source in sources:
            status, error = results[source.pk]
            source.http_status = status
            source.check_error = error
            source.last_checked_at = checked_at
            source.save(update_fields=("http_status", "check_error", "last_checked_at"))
            failures += int(bool(error) or (status is not None and status >= 400))
        self.stdout.write(f"Checked {len(sources)} source URL(s); {failures} need attention.")
