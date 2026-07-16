import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory


class PublicAssetManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(status=Asset.Status.PUBLISHED, visibility=Asset.Visibility.PUBLIC)
        )


class Asset(models.Model):
    class RecordType(models.TextChoices):
        ORGANIZATION = "organization", "Organization"
        FACILITY = "facility", "Facility"
        PROGRAM = "program", "Program"
        INFRASTRUCTURE = "infrastructure", "Infrastructure"
        OPERATING_ENVIRONMENT = "operating-environment", "Operating environment"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        NEEDS_REVIEW = "needs-review", "Needs source review"
        VERIFIED = "verified", "Verified"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PARTNER = "partner", "Partner only"
        INTERNAL = "internal", "Internal"

    class LocationPrecision(models.TextChoices):
        EXACT = "exact", "Exact"
        APPROXIMATE = "approximate", "Approximate"
        LOCALITY = "locality", "Locality only"
        HIDDEN = "hidden", "Hidden"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    record_type = models.CharField(max_length=30, choices=RecordType.choices)
    short_description = models.CharField(max_length=320)
    unmanned_systems_relevance = models.TextField()
    website_url = models.URLField(blank=True)
    contact_text = models.CharField(max_length=240, blank=True)

    address_line = models.CharField(max_length=240, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, default="VA")
    postal_code = models.CharField(max_length=12, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    location_precision = models.CharField(
        max_length=20, choices=LocationPrecision.choices, default=LocationPrecision.APPROXIMATE
    )
    region = models.ForeignKey(
        Region, on_delete=models.SET_NULL, null=True, blank=True, related_name="assets"
    )

    strategic_categories = models.ManyToManyField(
        StrategicCategory, blank=True, related_name="assets"
    )
    platform_domains = models.ManyToManyField(PlatformDomain, blank=True, related_name="assets")
    capabilities = models.ManyToManyField(Capability, blank=True, related_name="assets")
    missions = models.ManyToManyField(MissionArea, blank=True, related_name="assets")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    visibility = models.CharField(
        max_length=12, choices=Visibility.choices, default=Visibility.INTERNAL
    )
    last_verified_at = models.DateField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    public = PublicAssetManager()

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("name", "city"), name="unique_asset_name_city")
        ]
        indexes = [
            models.Index(fields=("status", "visibility")),
            models.Index(fields=("record_type", "region")),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        if bool(self.latitude is None) != bool(self.longitude is None):
            errors["latitude"] = "Latitude and longitude must be provided together."
        if (
            self.location_precision == self.LocationPrecision.HIDDEN
            and self.visibility == self.Visibility.PUBLIC
        ):
            errors["location_precision"] = "Public records cannot expose a hidden location."
        if self.status == self.Status.PUBLISHED and self.visibility != self.Visibility.PUBLIC:
            errors["visibility"] = "Published records must use public visibility."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.latitude is not None and not isinstance(self.latitude, Decimal):
            self.latitude = Decimal(str(self.latitude))
        if self.longitude is not None and not isinstance(self.longitude, Decimal):
            self.longitude = Decimal(str(self.longitude))
        if not self.slug:
            base = slugify(self.name)
            slug = base
            suffix = 2
            while Asset.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{suffix}"
                suffix += 1
            self.slug = slug
        if self.status == self.Status.PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("core:asset-detail", kwargs={"slug": self.slug})

    @property
    def has_public_coordinates(self):
        return (
            self.latitude is not None
            and self.longitude is not None
            and self.location_precision != self.LocationPrecision.HIDDEN
        )


class Relationship(models.Model):
    class RelationshipType(models.TextChoices):
        OPERATES = "operates", "Operates"
        LOCATED_AT = "located-at", "Located at"
        PARTNERS_WITH = "partners-with", "Partners with"
        FUNDS = "funds", "Funds"
        SUPPORTS = "supports", "Supports"
        PARTICIPATES_IN = "participates-in", "Participates in"

    from_asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="outgoing_relationships"
    )
    to_asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="incoming_relationships"
    )
    relationship_type = models.CharField(max_length=24, choices=RelationshipType.choices)
    description = models.CharField(max_length=320, blank=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ("relationship_type", "to_asset__name")
        constraints = [
            models.UniqueConstraint(
                fields=("from_asset", "to_asset", "relationship_type"),
                name="unique_asset_relationship",
            )
        ]

    def clean(self):
        if self.from_asset_id == self.to_asset_id:
            raise ValidationError("An asset cannot relate to itself.")

    def __str__(self):
        return f"{self.from_asset} {self.get_relationship_type_display()} {self.to_asset}"
