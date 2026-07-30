import uuid
from datetime import timedelta
from decimal import Decimal
from math import isfinite
from urllib.parse import parse_qsl

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from simple_history.models import HistoricalRecords

from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory

from .scoping import apply_public_scope


class PublicAssetManager(models.Manager):
    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(status__in=Asset.public_status_values(), visibility=Asset.Visibility.PUBLIC)
        )
        return apply_public_scope(queryset)


class Asset(models.Model):
    class RecordType(models.TextChoices):
        UNIVERSITY = "university", "University"
        ORGANIZATION = "organization", "Organization"
        FACILITY = "facility", "Facility"
        PROGRAM = "program", "Program"
        INFRASTRUCTURE = "infrastructure", "Infrastructure"
        OPERATING_ENVIRONMENT = "operating-environment", "Operating environment"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        NEEDS_REVIEW = "needs-review", "Needs source review"
        SOURCE_BACKED = "source-backed", "Source-backed listing"
        VERIFIED = "verified", "Verified"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        PARTNER = "partner", "Partner only"
        INTERNAL = "internal", "Internal"

    class LocationPrecision(models.TextChoices):
        EXACT = "exact", "Exact"
        SITE = "site", "Site or campus"
        APPROXIMATE = "approximate", "Approximate"
        LOCALITY = "locality", "Locality only"
        REGIONAL = "regional", "Regional; no single site"
        HIDDEN = "hidden", "Hidden"

    class ReviewPriority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

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
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_assets",
    )
    review_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_asset_reviews",
    )
    review_due_at = models.DateField(null=True, blank=True)
    review_priority = models.CharField(
        max_length=12,
        choices=ReviewPriority.choices,
        default=ReviewPriority.NORMAL,
    )
    review_notes = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    public = PublicAssetManager()
    history = HistoricalRecords(
        m2m_fields=["strategic_categories", "platform_domains", "capabilities", "missions"]
    )

    class Meta:
        ordering = ("name",)
        permissions = [
            ("can_verify_asset", "Can verify asset records"),
            ("can_publish_asset", "Can publish or archive asset records"),
            ("can_export_asset", "Can export asset records"),
        ]
        constraints = [
            models.UniqueConstraint(fields=("name", "city"), name="unique_asset_name_city")
        ]
        indexes = [
            models.Index(fields=("status", "visibility")),
            models.Index(fields=("record_type", "region")),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def public_status_values(cls):
        return (cls.Status.SOURCE_BACKED, cls.Status.PUBLISHED)

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
        if self.status == self.Status.PUBLISHED and not self.is_editorially_reviewed:
            errors["status"] = "Published records require a completed editorial review."
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
    def is_editorially_reviewed(self):
        return self.reviewed_at is not None and self.last_verified_at is not None

    @property
    def verification_label(self):
        if self.is_editorially_reviewed:
            return "Editorially reviewed"
        return "Source-backed; editorial review pending"

    @property
    def verification_state(self):
        if not self.is_editorially_reviewed:
            return "source-backed"
        stale_after = timezone.localdate() - timedelta(days=settings.STALE_VERIFICATION_DAYS)
        if self.last_verified_at < stale_after:
            return "stale"
        return "reviewed"

    @property
    def verification_state_label(self):
        return {
            "reviewed": "Editorially reviewed",
            "stale": "Review is out of date",
            "source-backed": "Source-backed; review pending",
        }[self.verification_state]

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
    history = HistoricalRecords()

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


class AssetReviewComment(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="review_comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="asset_review_comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Comment on {self.asset}"


class DuplicateCandidate(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Needs review"
        NOT_DUPLICATE = "not-duplicate", "Confirmed distinct"
        MERGED = "merged", "Merged or archived"

    left_asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="duplicate_candidates_left"
    )
    right_asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="duplicate_candidates_right"
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    match_reasons = models.JSONField(default=list)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_duplicate_candidates",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-score", "left_asset__name", "right_asset__name")
        constraints = [
            models.UniqueConstraint(
                fields=("left_asset", "right_asset"),
                name="unique_asset_duplicate_candidate",
            )
        ]

    def clean(self):
        if self.left_asset_id == self.right_asset_id:
            raise ValidationError("A record cannot be a duplicate of itself.")

    def save(self, *args, **kwargs):
        if (
            self.left_asset_id
            and self.right_asset_id
            and str(self.left_asset_id) > str(self.right_asset_id)
        ):
            self.left_asset_id, self.right_asset_id = self.right_asset_id, self.left_asset_id
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.left_asset} / {self.right_asset}"


class UpdateSubmission(models.Model):
    class Kind(models.TextChoices):
        CORRECTION = "correction", "Correct an existing record"
        ADDITION = "addition", "Suggest a new asset"
        GENERAL = "general", "General feedback"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_REVIEW = "in-review", "In review"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="update_submissions",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    subject = models.CharField(max_length=220)
    details = models.TextField(max_length=5000)
    source_url = models.URLField(blank=True)
    submitter_name = models.CharField(max_length=120)
    submitter_organization = models.CharField(max_length=180, blank=True)
    submitter_email = models.EmailField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.subject


class SavedView(models.Model):
    class ViewType(models.TextChoices):
        MAP = "map", "Map"
        DIRECTORY = "directory", "Directory"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_asset_views"
    )
    name = models.CharField(max_length=120)
    view_type = models.CharField(max_length=12, choices=ViewType.choices)
    query_string = models.CharField(max_length=4000, blank=True)
    is_shared = models.BooleanField(default=False)
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ("-updated_at", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name", "view_type"), name="unique_saved_view_name"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_view_type_display()})"

    def clean(self):
        allowed = {
            "q",
            "record_type",
            "category",
            "domain",
            "capability",
            "mission",
            "region",
            "sort",
            "page",
            "map_lat",
            "map_lon",
            "map_zoom",
            "map_layers",
            "map_layers_v",
            "map_basemap",
            "map_analysis",
        }
        pairs = parse_qsl(self.query_string, keep_blank_values=True)
        unexpected = {key for key, _value in pairs} - allowed
        if unexpected:
            raise ValidationError(
                {"query_string": f"Unsupported filter(s): {', '.join(sorted(unexpected))}"}
            )
        params = dict(pairs)
        numeric_map_values = {
            "map_lat": (-90, 90),
            "map_lon": (-180, 180),
            "map_zoom": (1, 19),
        }
        for key, (minimum, maximum) in numeric_map_values.items():
            if key not in params:
                continue
            try:
                value = float(params[key])
            except ValueError as error:
                raise ValidationError({"query_string": f"Invalid {key} value."}) from error
            if not isfinite(value) or value < minimum or value > maximum:
                raise ValidationError({"query_string": f"Invalid {key} value."})
        if "map_layers" in params:
            allowed_layers = {
                "assets",
                "state",
                "regions",
                "mpz",
                "counties",
                "verification",
                "precision",
                "relationships",
            }
            layers = {value for value in params["map_layers"].split(",") if value}
            if layers - allowed_layers:
                raise ValidationError({"query_string": "Unsupported map layer selection."})
        if params.get("map_basemap", "street") not in {"street", "light", "imagery"}:
            raise ValidationError({"query_string": "Unsupported map basemap selection."})
        if "map_analysis" in params:
            analysis_type, separator, payload = params["map_analysis"].partition("|")
            try:
                if analysis_type == "rectangle" and separator:
                    values = [float(value) for value in payload.split(",")]
                    valid = (
                        len(values) == 4
                        and -90 <= values[0] <= values[2] <= 90
                        and -180 <= values[1] <= values[3] <= 180
                    )
                elif analysis_type == "polygon" and separator:
                    vertices = [
                        [float(value) for value in vertex.split(",")]
                        for vertex in payload.split(";")
                    ]
                    valid = len(vertices) >= 3 and all(
                        len(vertex) == 2
                        and -90 <= vertex[0] <= 90
                        and -180 <= vertex[1] <= 180
                        for vertex in vertices
                    )
                else:
                    valid = False
            except ValueError:
                valid = False
            if not valid:
                raise ValidationError({"query_string": "Invalid saved map analysis."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def destination_url_name(self):
        return "core:map" if self.view_type == self.ViewType.MAP else "core:directory"
