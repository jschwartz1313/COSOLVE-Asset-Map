"""Operator proposals; imported at the bottom of assets.models by the integrator."""

import json
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import EmailValidator, URLValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

PUBLIC_FIELD_LIMITS = {
    "use_cases": 3000,
    "access_notes": 3000,
    "contact_text": 240,
    "contact_phone": 40,
    "contact_email": 254,
    "contact_url": 1000,
}
BASELINE_FIELDS = (
    "name", "display_name", "slug", "record_type", "short_description", "overview",
    "unmanned_systems_relevance", "website_url", "contact_text", "contact_phone",
    "contact_email", "contact_url", "activity_status", "current_activity",
    "partnership_opportunities", "activity_source_url", "owner_operator",
    "available_acreage", "development_status", "development_notes", "infrastructure_access",
    "development_source_url", "test_aircraft", "test_dimensions", "test_runway_length_ft",
    "test_access", "test_source_url", "test_max_weight_lb", "test_max_span_ft",
    "test_max_weight_exclusive", "test_launch_methods", "test_activities", "test_access_types",
    "test_suitability_source_url", "address_line", "city", "state", "postal_code",
    "latitude", "longitude", "location_precision", "location_role", "location_method",
    "location_notes", "location_source_url", "region_id", "status", "visibility",
)


class OperatorReviewUnavailable(ValidationError):
    def __init__(self):
        super().__init__("This invitation is no longer available.")


class OperatorReviewConflict(ValidationError):
    def __init__(self):
        super().__init__(
            "The asset or accepted operator details changed after this invitation was created. "
            "Create a fresh invitation; nothing was approved or overwritten."
        )


def can_manage_operator_reviews(user):
    return bool(
        user.is_authenticated and user.is_active and user.is_staff
        and user.has_perms(("assets.change_asset", "assets.change_operatorreview"))
    )


def require_operator_review_staff(user):
    if not can_manage_operator_reviews(user):
        raise PermissionDenied


def validate_public_url(value):
    URLValidator(schemes=("http", "https"))(value)
    parts = urlsplit(value)
    if parts.username is not None or parts.password is not None or any(
        ord(character) <= 32 or ord(character) == 127 for character in value
    ):
        raise ValidationError("Enter a public HTTP or HTTPS URL without credentials.")


def normalize_proposal(proposal):
    """Allowlist the publication payload, never submitter or invitation metadata."""
    if not isinstance(proposal, dict) or set(proposal) - PUBLIC_FIELD_LIMITS.keys():
        raise ValidationError("Unsupported public proposal fields.")
    normalized = {}
    for key, limit in PUBLIC_FIELD_LIMITS.items():
        value = proposal.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValidationError(f"Invalid value for {key} (maximum {limit} characters).")
        value = value.strip()
        if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
            raise ValidationError("Public details contain unsupported characters.")
        normalized[key] = value
    if not any(normalized.values()):
        raise ValidationError("Provide at least one public detail for review.")
    if normalized["contact_email"]:
        EmailValidator()(normalized["contact_email"])
    if normalized["contact_url"]:
        validate_public_url(normalized["contact_url"])
    return normalized


def invitation_expiry():
    return timezone.now() + timedelta(days=14)


class OperatorReview(models.Model):
    asset = models.ForeignKey(
        "assets.Asset", on_delete=models.CASCADE, related_name="operator_reviews",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="created_operator_reviews", editable=False,
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    baseline = models.JSONField(default=dict, editable=False)
    proposal = models.JSONField(default=dict, blank=True, editable=False)
    submitter_name = models.CharField(max_length=120, blank=True, editable=False)
    submitter_email = models.EmailField(max_length=254, blank=True, editable=False)
    publication_consent = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=invitation_expiry)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_operator_reviews", editable=False,
    )
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes = [
            models.Index(fields=("asset", "approved_at"), name="operator_asset_approved_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approved_at__isnull=True) | (
                    models.Q(submitted_at__isnull=False) & models.Q(publication_consent=True)
                ),
                name="operator_approval_needs_consent",
            ),
            models.CheckConstraint(
                condition=models.Q(submitted_at__isnull=True) | models.Q(publication_consent=True),
                name="operator_submit_needs_consent",
            ),
        ]

    def __str__(self):
        return f"Operator review for {self.asset}"

    @property
    def is_available(self):
        return bool(
            self.expires_at > timezone.now() and not self.submitted_at
            and not self.revoked_at and not self.approved_at
        )

    def get_absolute_url(self):
        return reverse("core:operator-review", kwargs={"token": self.token})

    @classmethod
    def _accepted(cls, asset):
        return cls.objects.filter(
            asset=asset, approved_at__isnull=False, submitted_at__isnull=False,
            publication_consent=True, revoked_at__isnull=True,
        ).order_by("-approved_at", "-pk")

    @classmethod
    def snapshot(cls, asset):
        values = {field: getattr(asset, field) for field in BASELINE_FIELDS}
        for field in ("strategic_categories", "platform_domains", "capabilities", "missions"):
            values[field] = sorted(
                str(pk) for pk in getattr(asset, field).values_list("pk", flat=True)
            )
        accepted = cls._accepted(asset).first()
        snapshot = {
            "asset": values,
            "accepted_review": str(accepted.pk) if accepted else None,
            "accepted_proposal": accepted.proposal if accepted else {},
        }
        return json.loads(json.dumps(snapshot, cls=DjangoJSONEncoder))

    def clean(self):
        super().clean()
        if self.submitted_at:
            if not self.publication_consent or not self.submitter_name.strip():
                raise ValidationError(
                    "A private submitter name and publication consent are required."
                )
            if not self.submitter_email:
                raise ValidationError("A private submitter email is required.")
            self.proposal = normalize_proposal(self.proposal)
        elif any((self.proposal, self.publication_consent,
                  self.submitter_name, self.submitter_email)):
            raise ValidationError("Unsubmitted invitations cannot contain a proposal or identity.")
        if self.approved_at and not self.submitted_at:
            raise ValidationError("Only submitted proposals may be approved.")

    @classmethod
    def issue(cls, *, asset, created_by, expires_at=None):
        from .models import Asset

        require_operator_review_staff(created_by)
        with transaction.atomic():
            asset = Asset.objects.select_for_update().get(pk=asset.pk)
            if not Asset.public.filter(pk=asset.pk).exists():
                raise ValidationError("Invitations are only available for public assets.")
            expires_at = expires_at if expires_at is not None else invitation_expiry()
            if expires_at <= timezone.now():
                raise ValidationError("The invitation expiry must be in the future.")
            review = cls(
                asset=asset, created_by=created_by, expires_at=expires_at,
                baseline=cls.snapshot(asset),
            )
            review.full_clean()
            review.save()
            return review

    def _lock(self):
        from .models import Asset

        # All transitions lock the asset first, serializing sibling invitation approvals.
        asset = Asset.objects.select_for_update().get(pk=self.asset_id)
        review = type(self).objects.select_for_update().get(pk=self.pk)
        return asset, review

    def submit(self, *, proposal, submitter_name, submitter_email, publication_consent):
        from .models import Asset

        with transaction.atomic():
            asset, review = self._lock()
            if not review.is_available or not Asset.public.filter(pk=asset.pk).exists():
                raise OperatorReviewUnavailable
            if publication_consent is not True:
                raise ValidationError("Explicit publication consent is required.")
            review.proposal = normalize_proposal(proposal)
            review.submitter_name = submitter_name.strip()
            review.submitter_email = submitter_email.strip()
            review.publication_consent = True
            review.submitted_at = timezone.now()
            review.full_clean()
            changed = type(self).objects.filter(
                pk=review.pk, submitted_at__isnull=True, revoked_at__isnull=True,
                approved_at__isnull=True, expires_at__gt=review.submitted_at,
            ).update(
                proposal=review.proposal, submitter_name=review.submitter_name,
                submitter_email=review.submitter_email, publication_consent=True,
                submitted_at=review.submitted_at,
            )
            if changed != 1:
                raise OperatorReviewUnavailable
            self.refresh_from_db()

    def approve(self, *, user):
        from .models import Asset

        require_operator_review_staff(user)
        with transaction.atomic():
            asset, review = self._lock()
            if (
                not review.submitted_at or review.approved_at or review.revoked_at
                or review.expires_at <= timezone.now()
                or not Asset.public.filter(pk=asset.pk).exists()
            ):
                raise OperatorReviewUnavailable
            if review.baseline != type(self).snapshot(asset):
                raise OperatorReviewConflict
            review.approved_at = timezone.now()
            review.approved_by = user
            review.full_clean()
            review.save(update_fields=("approved_at", "approved_by"))
            self.refresh_from_db()

    def revoke(self, *, user):
        require_operator_review_staff(user)
        with transaction.atomic():
            _asset, review = self._lock()
            if not review.revoked_at:
                review.revoked_at = timezone.now()
                review.save(update_fields=("revoked_at",))
            self.refresh_from_db()


def get_public_operator_details(asset):
    """Profile integration: only consented public strings, never the review object."""
    from .models import Asset

    if not Asset.public.filter(pk=asset.pk).exists():
        return {}
    review = OperatorReview._accepted(asset).first()
    if not review:
        return {}
    current_asset = Asset.objects.get(pk=asset.pk)
    if review.baseline.get("asset") != OperatorReview.snapshot(current_asset)["asset"]:
        return {}
    try:
        return normalize_proposal(review.proposal)
    except ValidationError:
        return {}
