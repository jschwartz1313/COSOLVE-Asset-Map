"""Benchmark geography and request-local inventory scope."""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    code: str
    name: str
    slug: str
    lat: float
    lon: float
    zoom: int

    @property
    def prefix(self):
        return "" if self.code == "VA" else f"/states/{self.slug}"


# Scope confirmed against the UXS Benchmark's November 10 working workbook.
STATES = (
    State("VA", "Virginia", "virginia", 37.5, -78.7, 7),
    State("AZ", "Arizona", "arizona", 34.2, -111.7, 6),
    State("CA", "California", "california", 37.0, -119.5, 6),
    State("CO", "Colorado", "colorado", 39.0, -105.5, 7),
    State("FL", "Florida", "florida", 28.0, -82.0, 6),
    State("MI", "Michigan", "michigan", 44.3, -85.5, 6),
    State("NY", "New York", "new-york", 43.0, -75.5, 7),
    State("NC", "North Carolina", "north-carolina", 35.5, -79.8, 7),
    State("ND", "North Dakota", "north-dakota", 47.4, -100.5, 7),
    State("OH", "Ohio", "ohio", 40.3, -82.8, 7),
    State("OK", "Oklahoma", "oklahoma", 35.5, -98.0, 7),
    State("PA", "Pennsylvania", "pennsylvania", 40.9, -77.8, 7),
    State("TX", "Texas", "texas", 31.0, -99.0, 6),
    State("UT", "Utah", "utah", 39.3, -111.7, 7),
)
BY_CODE = {state.code: state for state in STATES}
BY_SLUG = {state.slug: state for state in STATES}
current_state = ContextVar("asset_inventory_state", default=None)
internal_preview = ContextVar("asset_inventory_internal_preview", default=False)


def scoped_regions():
    from apps.catalog.models import Region

    regions = Region.objects.filter(is_active=True)
    state = current_state.get()
    if state:
        regions = regions.filter(state=state.code)
    if state and state.code != "VA":
        # No Virginia analytical regions are silently assigned to a peer state.
        from apps.assets.models import Asset

        regions = regions.filter(assets__in=Asset.public.all()).distinct()
    return regions
