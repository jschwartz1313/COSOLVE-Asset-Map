from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords


class Source(models.Model):
    class LinkReviewStatus(models.TextChoices):
        AUTOMATIC = "automatic", "Use automated result"
        ACCEPTED = "accepted", "Accepted after manual review"
        NEEDS_REPLACEMENT = "needs-replacement", "Needs replacement"

    asset = models.ForeignKey("assets.Asset", on_delete=models.CASCADE, related_name="sources")
    title = models.CharField(max_length=240)
    url = models.URLField(blank=True)
    source_date = models.DateField(null=True, blank=True)
    last_verified_at = models.DateField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=20,
        choices=(
            ("unreviewed", "Unreviewed"),
            ("verified", "Verified"),
            ("stale", "Stale"),
            ("rejected", "Rejected"),
        ),
        default="unreviewed",
    )
    notes = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    check_error = models.CharField(max_length=240, blank=True)
    link_review_status = models.CharField(
        max_length=20, choices=LinkReviewStatus.choices, default=LinkReviewStatus.AUTOMATIC
    )
    link_review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-source_date", "title")

    def __str__(self):
        return self.title

    def clean(self):
        errors = {}
        if self.is_public and not self.url:
            errors["url"] = "Public sources require a URL."
        if self.verification_status == "verified":
            if not self.url:
                errors["url"] = "Verified sources require a URL."
            if not self.last_verified_at:
                errors["last_verified_at"] = "Verified sources require a verification date."
        if (
            self.link_review_status != self.LinkReviewStatus.AUTOMATIC
            and not self.link_review_notes
        ):
            errors["link_review_notes"] = "Document the reason for a manual link decision."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def has_link_issue(self):
        if self.link_review_status == self.LinkReviewStatus.ACCEPTED:
            return False
        return bool(
            self.link_review_status == self.LinkReviewStatus.NEEDS_REPLACEMENT
            or self.check_error
            or (self.http_status is not None and self.http_status >= 400)
        )
