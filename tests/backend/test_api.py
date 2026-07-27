from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.assets.models import Asset, Relationship
from apps.catalog.models import MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source


class PublicApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hampton Roads")
        cls.other_region = Region.objects.create(name="Greater Richmond")
        cls.test_category = StrategicCategory.objects.create(name="Test environments")
        cls.research_category = StrategicCategory.objects.create(name="Research depth")
        cls.maritime = PlatformDomain.objects.create(name="Maritime")
        cls.survey = MissionArea.objects.create(name="Surveying and mapping")
        cls.public = Asset.objects.create(
            name="Demo Public Range",
            record_type=Asset.RecordType.OPERATING_ENVIRONMENT,
            short_description="A representative public range.",
            unmanned_systems_relevance="Supports maritime test activity.",
            city="Norfolk",
            address_line="100 Range Road",
            postal_code="23510",
            latitude=36.850000,
            longitude=-76.280000,
            location_precision=Asset.LocationPrecision.SITE,
            region=cls.region,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
            last_verified_at=date(2026, 7, 1),
            internal_notes="Never serialize this value.",
        )
        cls.public.strategic_categories.add(cls.test_category)
        cls.public.platform_domains.add(cls.maritime)
        cls.public.missions.add(cls.survey)
        Source.objects.create(
            asset=cls.public,
            title="Fixture source",
            url="https://example.org/source",
            notes="Private source note",
        )
        cls.internal = Asset.objects.create(
            name="Restricted Asset",
            record_type=Asset.RecordType.FACILITY,
            short_description="Not public.",
            unmanned_systems_relevance="Internal only.",
            city="Norfolk",
            status=Asset.Status.VERIFIED,
            visibility=Asset.Visibility.INTERNAL,
        )
        cls.partner = Asset.objects.create(
            name="Demo Partner Organization",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A public partner.",
            unmanned_systems_relevance="Supports test activity.",
            city="Norfolk",
            region=cls.region,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Relationship.objects.create(
            from_asset=cls.partner,
            to_asset=cls.public,
            relationship_type=Relationship.RelationshipType.SUPPORTS,
        )

    def test_geojson_returns_only_public_records(self):
        response = self.client.get(reverse("api:asset-geojson"))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result_count"], 2)
        public_feature = next(
            feature
            for feature in body["features"]
            if feature["properties"]["name"] == self.public.name
        )
        self.assertEqual(public_feature["geometry"]["type"], "Point")
        self.assertEqual(
            public_feature["properties"]["location"]["address_line"],
            "100 Range Road",
        )
        self.assertEqual(
            public_feature["properties"]["location"]["precision_label"],
            "Site or campus",
        )
        self.assertFalse(body["truncated"])
        self.assertEqual(body["returned_count"], 2)

    def test_geojson_reports_when_limit_truncates_results(self):
        body = self.client.get(reverse("api:asset-geojson"), {"limit": 1}).json()
        self.assertEqual(body["result_count"], 2)
        self.assertEqual(body["returned_count"], 1)
        self.assertTrue(body["truncated"])

    def test_detail_excludes_internal_fields(self):
        response = self.client.get(reverse("api:asset-detail", args=[self.public.slug]))
        text = response.content.decode()
        self.assertNotIn("internal_notes", text)
        self.assertNotIn("Never serialize", text)
        self.assertNotIn("Private source note", text)

    def test_detail_includes_public_incoming_relationships(self):
        response = self.client.get(reverse("api:asset-detail", args=[self.public.slug]))
        related = response.json()["related_entities"]
        self.assertIn(self.partner.name, [item["name"] for item in related])
        self.assertEqual(related[0]["direction"], "incoming")

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

    def test_keyword_search_includes_taxonomy_and_related_organizations(self):
        self.assertEqual(
            self.client.get(reverse("api:asset-list"), {"q": "Surveying"}).json()["result_count"],
            1,
        )
        relationship_search = self.client.get(
            reverse("api:asset-list"), {"q": "Partner Organization"}
        ).json()
        self.assertIn(self.public.name, [item["name"] for item in relationship_search["results"]])

    def test_region_summary_honors_active_filters(self):
        response = self.client.get(
            reverse("api:region-summary", args=[self.region.slug]),
            {"record_type": Asset.RecordType.OPERATING_ENVIRONMENT},
        )
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(
            response.json()["active_filters"]["record_type"],
            [Asset.RecordType.OPERATING_ENVIRONMENT],
        )

    def test_internal_detail_is_not_found(self):
        response = self.client.get(reverse("api:asset-detail", args=[self.internal.slug]))
        self.assertEqual(response.status_code, 404)


@override_settings(PUBLIC_REGION_SLUG="hampton-roads", PUBLIC_SCOPE_NAME="Hampton Roads")
class ScopedPublicApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hampton_roads = Region.objects.create(name="Hampton Roads")
        cls.greater_richmond = Region.objects.create(name="Greater Richmond")
        cls.center = Asset.objects.create(
            name="Scoped Center",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A scoped public center.",
            unmanned_systems_relevance="Supports autonomous systems.",
            region=cls.hampton_roads,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        cls.regional_partner = Asset.objects.create(
            name="Scoped Regional Partner",
            record_type=Asset.RecordType.UNIVERSITY,
            short_description="A scoped public partner.",
            unmanned_systems_relevance="Supports autonomous systems.",
            region=cls.hampton_roads,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        cls.outside = Asset.objects.create(
            name="Outside Regional Partner",
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="An out-of-scope public partner.",
            unmanned_systems_relevance="Supports autonomous systems.",
            region=cls.greater_richmond,
            status=Asset.Status.SOURCE_BACKED,
            visibility=Asset.Visibility.PUBLIC,
        )
        Relationship.objects.create(
            from_asset=cls.regional_partner,
            to_asset=cls.center,
            relationship_type=Relationship.RelationshipType.SUPPORTS,
        )
        Relationship.objects.create(
            from_asset=cls.center,
            to_asset=cls.outside,
            relationship_type=Relationship.RelationshipType.PARTNERS_WITH,
        )

    def test_region_query_cannot_override_deployment_scope(self):
        response = self.client.get(
            reverse("api:asset-geojson"),
            {"region": self.greater_richmond.slug},
        )

        body = response.json()
        self.assertEqual(body["result_count"], 2)
        self.assertNotIn("region", body["active_filters"])
        self.assertNotIn(
            self.outside.name,
            [feature["properties"]["name"] for feature in body["features"]],
        )

    def test_out_of_scope_detail_and_region_summary_are_not_found(self):
        self.assertEqual(
            self.client.get(reverse("api:asset-detail", args=[self.outside.slug])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("api:region-summary", args=[self.greater_richmond.slug])
            ).status_code,
            404,
        )

    def test_detail_relationships_exclude_out_of_scope_assets(self):
        related = self.client.get(reverse("api:asset-detail", args=[self.center.slug])).json()[
            "related_entities"
        ]
        names = [item["name"] for item in related]
        self.assertIn(self.regional_partner.name, names)
        self.assertNotIn(self.outside.name, names)

    def test_filter_metadata_only_advertises_active_region(self):
        regions = self.client.get(reverse("api:filter-values")).json()["regions"]
        self.assertEqual(regions, [{"name": "Hampton Roads", "slug": "hampton-roads"}])
