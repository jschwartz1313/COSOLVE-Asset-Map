import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.sources.models import Source


class UnsafeSourceURL(ValueError):
    pass


def network_error_message(error):
    reason = error.reason if isinstance(error, URLError) else error
    return str(reason)[:240]


def validate_public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeSourceURL("Only public HTTP and HTTPS URLs can be checked.")
    if parsed.username or parsed.password:
        raise UnsafeSourceURL("URLs containing credentials cannot be checked.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise UnsafeSourceURL("The URL contains an invalid port.") from error
    if port not in {80, 443}:
        raise UnsafeSourceURL("Only standard HTTP and HTTPS ports can be checked.")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as error:
        raise UnsafeSourceURL("The source hostname could not be resolved.") from error
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise UnsafeSourceURL("Private, local, or reserved source addresses are blocked.")


class PublicOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_url(url):
    headers = {"User-Agent": "COSOLVE-Asset-Map/1.0 source-maintenance"}
    try:
        validate_public_url(url)
    except UnsafeSourceURL as error:
        return None, str(error)[:240]
    opener = build_opener(PublicOnlyRedirectHandler)
    try:
        request = Request(url, headers=headers, method="HEAD")
        with opener.open(request, timeout=12) as response:  # noqa: S310
            return response.status, ""
    except HTTPError:
        pass
    except (TimeoutError, URLError, OSError, HTTPException) as error:
        return None, network_error_message(error)

    try:
        request = Request(url, headers={**headers, "Range": "bytes=0-0"})
        with opener.open(request, timeout=15) as response:  # noqa: S310
            return response.status, ""
    except HTTPError as error:
        return error.code, ""
    except (TimeoutError, URLError, OSError, HTTPException) as error:
        return None, network_error_message(error)


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
            options["limit"] if options["limit"] is not None else (None if options["all"] else 100)
        )
        sources = list(queryset[:limit] if limit is not None else queryset)
        checked_at = timezone.now()
        urls = {source.url for source in sources}
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, options["workers"])) as executor:
            futures = {executor.submit(check_url, url): url for url in urls}
            for future in as_completed(futures):
                url = futures[future]
                try:
                    results[url] = future.result()
                except Exception as error:  # Keep one unusual server from aborting the batch.
                    results[url] = (None, f"Unexpected check failure: {error}"[:240])

        failures = 0
        for source in sources:
            status, error = results[source.url]
            source.http_status = status
            source.check_error = error
            source.last_checked_at = checked_at
            source.save(update_fields=("http_status", "check_error", "last_checked_at"))
            failures += int(source.has_link_issue)
        self.stdout.write(
            f"Checked {len(sources)} source record(s) across {len(urls)} URL(s); "
            f"{failures} need attention."
        )
