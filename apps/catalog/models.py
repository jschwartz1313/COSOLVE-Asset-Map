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
