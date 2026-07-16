from django.db import models


class Source(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-source_date", "title")

    def __str__(self):
        return self.title
