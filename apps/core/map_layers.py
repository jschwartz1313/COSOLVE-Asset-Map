"""Display the dates of shipped reference data, never the deployment date."""

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import timezone

REFERENCE_LAYERS = {
    "heliports": ("virginia-heliports.geojson", 28),
    "controlled_airspace": ("virginia-surface-controlled-airspace.geojson", 7),
    "uas_facility_map": ("virginia-uas-facility-map.geojson", 7),
    "flight_constraints": ("virginia-flight-constraints.geojson", 7),
    "uas_test_sites": ("virginia-uas-test-sites.geojson", 90),
}


@lru_cache(maxsize=16)
def snapshot_date(path, modified_at):
    try:
        value = json.loads(Path(path).read_text())["metadata"]["generated_at"]
        return date.fromisoformat(value)
    except (OSError, ValueError, TypeError, KeyError):
        return None


def layer_freshness(today=None):
    today = today or timezone.localdate()
    result = {}
    for key, (filename, interval) in REFERENCE_LAYERS.items():
        path = settings.BASE_DIR / "static" / "data" / filename
        try:
            retrieved = snapshot_date(str(path), path.stat().st_mtime_ns)
        except OSError:
            retrieved = None
        if retrieved and retrieved > today:
            retrieved = None
        due = retrieved + timedelta(days=interval) if retrieved else None
        result[key] = {
            "snapshot_date": retrieved,
            "due_date": due,
            "review_due": due is None or due <= today,
            "version": retrieved.isoformat() if retrieved else "unknown",
            "interval_days": interval,
        }
    return result
