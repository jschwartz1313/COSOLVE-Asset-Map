"""Task-oriented shortcuts over the existing asset classifications."""

from django.db.models import Q

RESOURCE_CHOICES = (
    ("testing", "Test sites and environments"),
    ("projects", "Projects and programs"),
    ("workforce", "Workforce and training"),
    ("business", "Business support and partnerships"),
    ("counter-uas", "Counter-UAS"),
    ("airspace", "Airspace integration"),
    ("manufacturing", "Manufacturing facilities"),
)

RESOURCE_QUERIES = {
    "testing": Q(strategic_categories__slug="test-and-operational-environments"),
    "projects": Q(record_type="program"),
    "workforce": Q(strategic_categories__slug="workforce-and-talent"),
    "business": Q(
        strategic_categories__slug__in=(
            "commercialization-and-capital",
            "state-strategy-and-coordination",
        )
    ),
    "counter-uas": Q(missions__slug="counter-uas"),
    "airspace": Q(capabilities__slug="safety-policy-regulatory-and-airspace-integration"),
    "manufacturing": Q(strategic_categories__slug="manufacturing-facilities"),
}

TEST_SPEC_FIELDS = (
    "test_aircraft",
    "test_dimensions",
    "test_runway_length_ft",
    "test_access",
    "test_source_url",
    "test_last_verified_at",
)
