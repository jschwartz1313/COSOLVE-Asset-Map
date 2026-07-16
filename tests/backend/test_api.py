from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.assets.models import Asset
from apps.catalog.models import PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source


class PublicApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hampton Roads")
        cls.other_region = Region.objects.create(name="Greater Richmond")
        cls.test_category = StrategicCategory.objects.create(name="Test environments")
        cls.research_category = StrategicCategory.objects.create(name="Research depth")
        cls.maritime = PlatformDomain.objects.create(name="Maritime")
        cls.public = Asset.objects.create(
            name="Demo Public Range",
            record_type=Asset.RecordType.OPERATING_ENVIRONMENT,
            short_description="A representative public range.",
            unmanned_systems_relevance="Supports maritime test activity.",
            city="Norfolk",
            latitude=36.850000,
            longitude=-76.280000,
            region=cls.region,
            status=Asset.Status.PUBLISHED,
            visibility=Asset.Visibility.PUBLIC,
            last_verified_at=date(2026, 7, 1),
            internal_notes="Never serialize this value.",
        )
        cls.public.strategic_categories.add(cls.test_category)
        cls.public.platform_domains.add(cls.maritime)
        Source.objects.create(asset=cls.public, title="Fixture source", notes="Private source note")
        cls.internal = Asset.objects.create(
            name="Restricted Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="Not public.",
            unmanned_systems_relevance="Internal only.",
            city="Norfolk",
            status=Asset.Status.VERIFIED,
            visibility=Asset.Visibility.INTERNAL,
        )

    def test_geojson_returns_only_public_records(self):
        response = self.client.get(reverse("api:asset-geojson"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result_count"], 1)
        self.assertEqual(body["features"][0]["properties"]["name"], self.public.name)
        self.assertEqual(body["features"][0]["geometry"]["type"], "Point")

    def test_detail_excludes_internal_fields(self):
        response = self.client.get(reverse("api:asset-detail", args=[self.public.slug]))
        text = response.content.decode()
        self.assertNotIn("internal_notes", text)
        self.assertNotIn("Never serialize", text)
        self.assertNotIn("Private source note", text)

    def test_repeated_values_within_facet_use_or_logic(self):
        response = self.client.get(
            reverse("api:asset-geojson"),
            {"category": [self.test_category.slug, self.research_category.slug]},
        )
        self.assertEqual(response.json()["result_count"], 1)

    def test_different_facets_use_and_logic(self):
        response = self.client.get(
            reverse("api:asset-geojson"),
            {"category": self.test_category.slug, "region": self.other_region.slug},
        )
        self.assertEqual(response.json()["result_count"], 0)

    def test_keyword_search(self):
        self.assertEqual(
            self.client.get(reverse("api:asset-list"), {"q": "maritime"}).json()["result_count"], 1
        )
        self.assertEqual(
            self.client.get(reverse("api:asset-list"), {"q": "aviation"}).json()["result_count"], 0
        )

    def test_internal_detail_is_not_found(self):
        response = self.client.get(reverse("api:asset-detail", args=[self.internal.slug]))
        self.assertEqual(response.status_code, 404)
