from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class TaxonomyBase(models.Model):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ("display_order", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class StrategicCategory(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name_plural = "strategic categories"


class PlatformDomain(TaxonomyBase):
    pass


class Capability(TaxonomyBase):
    class Meta(TaxonomyBase.Meta):
        verbose_name_plural = "capabilities"


class MissionArea(TaxonomyBase):
    pass


class Region(TaxonomyBase):
    region_type = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=2, default="VA", db_index=True)

    def clean(self):
        self.state = (self.state or "").strip().upper()
        if self.pk and self.assets.exclude(state=self.state).exists():
            raise ValidationError({"state": "This region has assets from another state."})

    def save(self, *args, **kwargs):
        self.state = self.state.strip().upper()
        super().save(*args, **kwargs)
