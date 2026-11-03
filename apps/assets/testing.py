"""Evidence-based comparison of published criteria, never flight authorization."""

from django.db.models import Q
from django.utils import timezone

ACCESS_CHOICES = (
    ("commercial", "Commercial inquiries"),
    ("research", "Research access"),
    ("partnership", "Partner approval required"),
    ("restricted", "Restricted / sponsored access"),
)
LAUNCH_CHOICES = (
    ("runway", "Runway takeoff / landing"),
    ("vertical", "Vertical takeoff / landing"),
    ("catapult", "Catapult launch / assisted recovery"),
)
ACTIVITY_CHOICES = (
    ("flight", "Flight testing"),
    ("autonomy", "Autonomy / sensor research"),
    ("counter-uas", "Counter-UAS evaluation"),
    ("enclosed", "Enclosed / netted testing"),
    ("multi-aircraft", "Multi-aircraft testing"),
)
STRUCTURED_TEST_FIELDS = (
    "test_max_weight_lb",
    "test_max_span_ft",
    "test_launch_methods",
    "test_activities",
    "test_access_types",
    "test_suitability_source_url",
    "test_suitability_reviewed_at",
    "test_max_weight_exclusive",
)


def evidence_usable(asset, url, reviewed):
    matching = [source for source in asset.sources.all() if source.url == url]
    return bool(
        url
        and reviewed
        and reviewed <= timezone.localdate()
        and matching
        and all(
            source.is_public
            and source.verification_status not in {"stale", "rejected"}
            and source.link_review_status != "needs-replacement"
            for source in matching
        )
    )


def access_labels(asset):
    if not evidence_usable(
        asset, asset.test_suitability_source_url, asset.test_suitability_reviewed_at
    ):
        return []
    return [label for value, label in ACCESS_CHOICES if value in asset.test_access_types]


def testing_candidates(queryset):
    return (
        queryset.filter(
            record_type__in=("facility", "infrastructure", "operating-environment"),
        )
        .filter(
            Q(strategic_categories__slug="test-and-operational-environments")
            | Q(test_source_url__gt="")
            | Q(test_suitability_source_url__gt=""),
        )
        .filter(
            Q(platform_domains__slug__in=("unmanned-aircraft-systems", "advanced-air-mobility"))
            | Q(test_suitability_source_url__gt=""),
        )
        .exclude(activity_status="historical")
        .distinct()
    )


def filter_access(queryset, value):
    if value not in {"undocumented", *dict(ACCESS_CHOICES)}:
        return queryset.none()
    matches = []
    for asset in testing_candidates(queryset).prefetch_related("sources"):
        known = bool(access_labels(asset))
        if (value == "undocumented" and not known) or (
            value != "undocumented" and known and value in asset.test_access_types
        ):
            matches.append(asset.pk)
    return queryset.filter(pk__in=matches)


def compare_site(asset, requirements):
    checks = []
    supported = evidence_usable(
        asset, asset.test_suitability_source_url, asset.test_suitability_reviewed_at
    )

    def check(
        label, actual, requested, *, maximum=False, unit="", usable=supported, exclusive=False
    ):
        if requested is None:
            return
        if actual is None or not usable:
            checks.append({"label": label, "status": "unknown", "text": "Not documented"})
            return
        passes = requested < actual if exclusive else requested <= actual
        qualifier = "limit: under" if exclusive else "maximum:" if maximum else "length:"
        checks.append(
            {
                "label": label,
                "status": "match" if passes else "conflict",
                "text": f"Published {qualifier} {actual:g} {unit}",
            }
        )

    check(
        "Aircraft weight",
        asset.test_max_weight_lb,
        requirements.get("weight"),
        maximum=True,
        unit="lb",
        exclusive=asset.test_max_weight_exclusive,
    )
    check(
        "Aircraft span / width",
        asset.test_max_span_ft,
        requirements.get("span"),
        maximum=True,
        unit="ft",
    )
    check(
        "Runway length",
        asset.test_runway_length_ft,
        requirements.get("runway"),
        unit="ft",
        usable=evidence_usable(asset, asset.test_source_url, asset.test_last_verified_at),
    )
    for key, field, choices, label in (
        ("launch", "test_launch_methods", LAUNCH_CHOICES, "Launch / recovery"),
        ("activity", "test_activities", ACTIVITY_CHOICES, "Testing activity"),
        ("access", "test_access_types", ACCESS_CHOICES, "Access"),
    ):
        requested = requirements.get(key)
        if not requested or requested == "undocumented":
            continue
        present = supported and requested in getattr(asset, field)
        checks.append(
            {
                "label": label,
                "status": "match" if present else "unknown",
                "text": dict(choices)[requested]
                if present
                else "Requested condition not documented",
            }
        )
    if checks and asset.activity_status in {"planned", "developing", "pilot"}:
        checks.append(
            {
                "label": "Current availability",
                "status": "unknown",
                "text": f"{asset.get_activity_status_display()}; confirm with operator",
            }
        )
    state = (
        "reference"
        if not checks
        else "conflict"
        if any(c["status"] == "conflict" for c in checks)
        else "unknown"
        if any(c["status"] == "unknown" for c in checks)
        else "match"
    )
    return {
        "asset": asset,
        "checks": checks,
        "state": state,
        "label": {
            "reference": "Review specifications",
            "conflict": "Published limit conflict",
            "unknown": "Needs confirmation",
            "match": "Documented criteria match",
        }[state],
        "access_labels": access_labels(asset),
        "evidence_usable": supported,
    }
