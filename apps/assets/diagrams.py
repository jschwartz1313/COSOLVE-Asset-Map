"""Staff-approved public site illustrations, without server-side image retrieval."""

import ipaddress
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def validate_public_image_url(value):
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
    except ValueError as error:
        raise ValidationError("Use a valid public HTTPS image URL.") from error
    if (parts.scheme != "https" or parts.username or parts.password or parts.query
            or parts.fragment or port not in (None, 443)
            or "." not in host or host.endswith((".local", ".localhost", ".internal"))):
        raise ValidationError("Use a public HTTPS image URL without credentials or a query string.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValidationError("The image must be on a public host.")
    if not parts.path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise ValidationError(
            "Use a PNG, JPEG or WebP image, not a document or private sharing link."
        )


class SiteDiagram(models.Model):
    asset = models.ForeignKey("assets.Asset", on_delete=models.CASCADE,
                              related_name="site_diagrams")
    title = models.CharField(max_length=180)
    image_url = models.URLField(max_length=1000, validators=[validate_public_image_url])
    alt_text = models.CharField(max_length=400)
    caption = models.TextField(max_length=2000, blank=True)
    credit = models.CharField(max_length=240)
    source_url = models.URLField(max_length=1000)
    publication_approved = models.BooleanField(default=False, help_text=(
        "Confirm permission to publish and that the diagram contains no sensitive details."
    ))
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, editable=False)

    class Meta:
        ordering = ("title", "pk")

    def __str__(self):
        return f"{self.asset}: {self.title}"

    def clean(self):
        super().clean()
        try:
            validate_public_image_url(self.image_url)
        except (ValueError, ValidationError) as error:
            raise ValidationError({"image_url": str(error)}) from error
        if self.publication_approved and not all(
            value.strip() for value in (self.alt_text, self.credit, self.source_url)
        ):
            raise ValidationError(
                "Approved diagrams require alternative text, credit and a source."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
