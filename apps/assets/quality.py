import re
from difflib import SequenceMatcher
from itertools import combinations
from math import asin, cos, radians, sin, sqrt
from urllib.parse import urlsplit

from django.db import transaction

from .models import Asset, DuplicateCandidate


def _normalized_text(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalized_url(value):
    if not value:
        return ""
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/").lower()
    return f"{host}{path}" if host else ""


def _distance_miles(first, second):
    if None in (first.latitude, first.longitude, second.latitude, second.longitude):
        return None
    lat1 = radians(float(first.latitude))
    lat2 = radians(float(second.latitude))
    delta_lat = lat2 - lat1
    delta_lon = radians(float(second.longitude) - float(first.longitude))
    value = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    return 3958.8 * 2 * asin(sqrt(value))


def _candidate_details(first, second):
    first_name = _normalized_text(first.name)
    second_name = _normalized_text(second.name)
    name_similarity = SequenceMatcher(None, first_name, second_name).ratio()
    same_city = bool(first.city and _normalized_text(first.city) == _normalized_text(second.city))
    first_address = _normalized_text(first.address_line)
    second_address = _normalized_text(second.address_line)
    first_url = _normalized_url(first.website_url)
    second_url = _normalized_url(second.website_url)
    distance = _distance_miles(first, second)

    reasons = []
    scores = []
    if first_name == second_name:
        reasons.append("Same normalized name")
        scores.append(100)
    if first_url and first_url == second_url and name_similarity >= 0.75:
        reasons.append(f"Same website URL with related names ({name_similarity:.0%})")
        scores.append(round(90 + name_similarity * 8))
    if (
        first_address
        and first_address == second_address
        and same_city
        and name_similarity >= 0.55
    ):
        reasons.append(f"Same street address and related names ({name_similarity:.0%})")
        scores.append(round(88 + name_similarity * 8))
    if same_city and name_similarity >= 0.9:
        reasons.append(f"Similar names in the same city ({name_similarity:.0%})")
        scores.append(round(86 + name_similarity * 10))
    if distance is not None and distance <= 0.05 and name_similarity >= 0.75:
        reasons.append(f"Locations within {distance:.2f} miles with related names")
        scores.append(round(82 + name_similarity * 10))

    if not reasons:
        return None
    return {"score": min(max(scores), 100), "match_reasons": reasons}


def discover_duplicate_candidates(queryset=None):
    assets = list(
        (queryset or Asset.objects.exclude(status=Asset.Status.ARCHIVED))
        .only(
            "id",
            "name",
            "city",
            "address_line",
            "website_url",
            "latitude",
            "longitude",
        )
        .order_by("name")
    )
    candidates = []
    for first, second in combinations(assets, 2):
        details = _candidate_details(first, second)
        if details:
            candidates.append({"left_asset": first, "right_asset": second, **details})
    return candidates


@transaction.atomic
def sync_duplicate_candidates(queryset=None):
    discoveries = discover_duplicate_candidates(queryset)
    detected_pairs = set()
    created = 0
    updated = 0
    for discovery in discoveries:
        first = discovery["left_asset"]
        second = discovery["right_asset"]
        if str(first.pk) > str(second.pk):
            first, second = second, first
        pair = (first.pk, second.pk)
        detected_pairs.add(pair)
        candidate, was_created = DuplicateCandidate.objects.get_or_create(
            left_asset=first,
            right_asset=second,
            defaults={
                "score": discovery["score"],
                "match_reasons": discovery["match_reasons"],
            },
        )
        if was_created:
            created += 1
            continue
        changed = (
            candidate.score != discovery["score"]
            or candidate.match_reasons != discovery["match_reasons"]
        )
        if changed:
            candidate.score = discovery["score"]
            candidate.match_reasons = discovery["match_reasons"]
            candidate.save(update_fields=["score", "match_reasons", "updated_at"])
            updated += 1

    stale_open = DuplicateCandidate.objects.filter(status=DuplicateCandidate.Status.OPEN)
    stale_ids = [
        candidate.pk
        for candidate in stale_open.only("pk", "left_asset_id", "right_asset_id")
        if (candidate.left_asset_id, candidate.right_asset_id) not in detected_pairs
    ]
    removed = DuplicateCandidate.objects.filter(pk__in=stale_ids).delete()[0]
    return {
        "detected": len(discoveries),
        "created": created,
        "updated": updated,
        "removed": removed,
    }
