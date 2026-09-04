"""Import dated URL-availability observations without changing editorial decisions."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.sources.models import Source

CLASSIFICATION_MESSAGES = {
    "reachable": "",
    "http_not_found": "Source returned HTTP 404/410; replacement requires review.",
    "access_blocked_or_rate_limited": (
        "Automated access blocked or rate-limited; availability is inconclusive."
    ),
    "network_or_tls_error": "Network or TLS check failed; availability is inconclusive.",
    "server_error": "Source server returned an error; retry before treating it as a stale link.",
    "http_error": "Source returned an HTTP error; manual review is required.",
    "suspected_soft_404": (
        "Successful HTTP response appears to be a missing-page response; review required."
    ),
    "api_error_in_success_response": (
        "API returned an error inside a successful HTTP response; review required."
    ),
    "redirected_to_homepage_review": (
        "Deep source link redirects to a homepage; verify that specific evidence remains."
    ),
    "unexpected_error": "Unexpected automated check failure; availability is inconclusive.",
}


def load_results(path):
    """Validate the entire ledger before starting any database writes."""
    try:
        document = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CommandError(f"Could not read source audit: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("urls"), list):
        raise CommandError("The source audit must contain a urls list.")
    results = {}
    for index, entry in enumerate(document["urls"], start=1):
        if not isinstance(entry, dict):
            raise CommandError(f"URL observation {index} must be an object.")
        url = entry.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise CommandError(f"URL observation {index} has no public HTTP(S) URL.")
        if url in results:
            raise CommandError(f"Source audit repeats a URL: {url}")
        checked_value = entry.get("checked_at")
        try:
            checked_at = parse_datetime(checked_value) if isinstance(checked_value, str) else None
        except ValueError as error:
            raise CommandError(f"Invalid check timestamp for {url}") from error
        if checked_at is None or timezone.is_naive(checked_at):
            raise CommandError(f"Check timestamp must include a timezone for {url}")
        classification = entry.get("classification")
        if classification not in CLASSIFICATION_MESSAGES:
            raise CommandError(f"Unknown source check classification for {url}")
        status = entry.get("http_status")
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            raise CommandError(f"Invalid HTTP status for {url}")
        if classification == "reachable" and (status is None or not 200 <= status < 400):
            raise CommandError(f"Reachable observation must have a successful HTTP status: {url}")
        error = entry.get("error", "")
        if not isinstance(error, str):
            raise CommandError(f"Invalid check error for {url}")
        message = CLASSIFICATION_MESSAGES[classification]
        if error and classification in {"network_or_tls_error", "unexpected_error"}:
            message = f"{message} {error}"
        results[url] = (checked_at, status, message[:240])
    return results


class Command(BaseCommand):
    help = "Import newer public source HTTP observations while preserving manual source decisions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=Path,
            default=settings.BASE_DIR / "data" / "source_audit_2026_09_04.json",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        results = load_results(options["path"])
        updated = skipped = 0
        matched_urls = set()
        with transaction.atomic():
            sources = Source.objects.select_for_update().filter(is_public=True, url__in=results)
            for source in sources:
                matched_urls.add(source.url)
                checked_at, status, error = results[source.url]
                if source.last_checked_at is not None and source.last_checked_at >= checked_at:
                    skipped += 1
                    continue
                source.last_checked_at = checked_at
                source.http_status = status
                source.check_error = error
                if not options["dry_run"]:
                    source.save(update_fields=("last_checked_at", "http_status", "check_error"))
                updated += 1
        verb = "Would update" if options["dry_run"] else "Updated"
        self.stdout.write(
            f"{verb} {updated} source record(s); skipped {skipped} equal/newer checks; "
            f"matched {len(matched_urls)} of {len(results)} audited URLs. "
            "Editorial verification and manual link decisions were preserved."
        )
