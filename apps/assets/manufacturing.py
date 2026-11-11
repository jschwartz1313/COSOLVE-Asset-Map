"""Source-backed manufacturing attributes and conservative planning comparisons."""

from datetime import date, datetime

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .testing import ACCESS_CHOICES, evidence_usable

PROCESS_CHOICES = (
    ("cnc-machining", "CNC machining"),
    ("metrology", "Dimensional metrology / inspection"),
    ("pcb-assembly", "Printed circuit board assembly"),
    ("electronics-assembly", "Electronics / final assembly"),
    ("motor-manufacturing", "Motor manufacturing"),
    ("actuator-manufacturing", "Actuator manufacturing"),
    ("textile-fabrication", "Engineered textile fabrication"),
    ("additive-manufacturing", "Additive manufacturing"),
    ("reverse-engineering", "Reverse engineering"),
)
MATERIAL_CHOICES = (
    ("aluminum", "Aluminum"),
    ("steel", "Carbon / alloy steel"),
    ("stainless-steel", "Stainless steel"),
    ("copper-nickel", "Copper-nickel alloys"),
    ("nickel-aluminum-bronze", "Nickel-aluminum bronze"),
    ("nickel-alloys", "Nickel alloys"),
    ("titanium", "Titanium"),
    ("polymers", "Polymers"),
    ("composites", "Composites"),
    ("textiles", "Textiles"),
)
SERVICE_MODE_CHOICES = (
    ("contract-manufacturing", "Contract manufacturing"),
    ("prototyping", "Prototyping"),
    ("process-development", "Process development"),
    ("inspection-services", "Contract inspection"),
    ("custom-products", "Customer-specific products"),
    ("product-manufacturing", "Own-product manufacturing"),
)
PROFILE_CHOICES = {
    "processes": PROCESS_CHOICES,
    "materials": MATERIAL_CHOICES,
    "service_modes": SERVICE_MODE_CHOICES,
    "access_types": ACCESS_CHOICES,
}
PUBLIC_SOURCE_URL = URLValidator(schemes=("https", "http"))


def valid_choices(values, choices):
    return (
        isinstance(values, list)
        and all(isinstance(value, str) and value in dict(choices) for value in values)
        and len(values) == len(set(values))
    )


class ManufacturingProfile(models.Model):
    asset = models.OneToOneField(
        "assets.Asset", on_delete=models.CASCADE, related_name="manufacturing_profile"
    )
    processes = models.JSONField(default=list, blank=True)
    materials = models.JSONField(default=list, blank=True)
    service_modes = models.JSONField(default=list, blank=True)
    access_types = models.JSONField(default=list, blank=True)
    source_url = models.URLField(max_length=2048, validators=[PUBLIC_SOURCE_URL])
    reviewed_at = models.DateField(help_text="Internal source-review date; not for public display.")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Manufacturing: {self.asset}"

    def clean(self):
        super().clean()
        errors = {}
        for field, choices in PROFILE_CHOICES.items():
            if not valid_choices(getattr(self, field), choices):
                errors[field] = "Use a list of unique documented choices; use [] for unknown."
        if not isinstance(self.reviewed_at, date) or isinstance(self.reviewed_at, datetime):
            errors["reviewed_at"] = "A source-review date is required."
        elif self.reviewed_at > timezone.localdate():
            errors["reviewed_at"] = "The source-review date cannot be in the future."
        try:
            PUBLIC_SOURCE_URL(self.source_url)
        except ValidationError:
            errors["source_url"] = "A valid public HTTP(S) source URL is required."
        if self.asset_id and not errors:
            try:
                supported = evidence_usable(self.asset, self.source_url, self.reviewed_at)
            except ObjectDoesNotExist:
                supported = False
            if not supported:
                errors["source_url"] = "Attach a usable matching public source to this asset first."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


def manufacturing_candidates(queryset):
    # The existing catalog calls this category manufacturing-facilities.
    return queryset.filter(
        Q(strategic_categories__slug__in=("manufacturing-sites", "manufacturing-facilities"))
        | Q(manufacturing_profile__isnull=False)
    ).exclude(activity_status="historical").distinct()


def manufacturing_evidence_usable(asset, profile):
    if (
        profile is None
        or not isinstance(profile.reviewed_at, date)
        or isinstance(profile.reviewed_at, datetime)
    ):
        return False
    try:
        PUBLIC_SOURCE_URL(profile.source_url)
    except ValidationError:
        return False
    return evidence_usable(asset, profile.source_url, profile.reviewed_at)


def compare_manufacturing(asset, requirements):
    try:
        profile = asset.manufacturing_profile
    except ObjectDoesNotExist:
        profile = None
    supported = manufacturing_evidence_usable(asset, profile)
    documented = {
        field: getattr(profile, field)
        if supported and valid_choices(getattr(profile, field), choices)
        else []
        for field, choices in PROFILE_CHOICES.items()
    }
    checks = []
    for key, field, label in (
        ("process", "processes", "Process"),
        ("material", "materials", "Material"),
        ("mode", "service_modes", "Service mode"),
        ("access", "access_types", "Access"),
    ):
        requested = requirements.get(key)
        if not requested:
            continue
        present = requested in documented[field]
        checks.append({
            "label": label,
            "status": "match" if present else "unknown",
            "text": dict(PROFILE_CHOICES[field]).get(requested, "Unknown requirement")
            if present else "Requested condition not documented",
        })
    if checks and asset.activity_status in {"planned", "developing", "pilot"}:
        checks.append({
            "label": "Current availability",
            "status": "unknown",
            "text": f"{asset.get_activity_status_display()}; confirm with operator",
        })
    state = "reference" if not checks else (
        "unknown" if any(check["status"] == "unknown" for check in checks) else "match"
    )
    return {
        "asset": asset,
        "state": state,
        "label": {
            "reference": "Review documented capabilities",
            "unknown": "Needs confirmation",
            "match": "Documented criteria match",
        }[state],
        "checks": checks,
        "evidence_usable": supported,
        "source_url": profile.source_url if supported else "",
        "notes": profile.notes if supported else "",
        **{
            key: [label for value, label in PROFILE_CHOICES[field] if value in documented[field]]
            for key, field in (
                ("process_labels", "processes"),
                ("material_labels", "materials"),
                ("service_mode_labels", "service_modes"),
                ("access_labels", "access_types"),
            )
        },
    }
