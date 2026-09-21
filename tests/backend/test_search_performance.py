import json
from unittest.mock import patch

from django.http import QueryDict
from django.test import RequestFactory, TestCase, override_settings

from apps.api.query import filter_public_assets
from apps.api.views import asset_geojson, asset_list, limited_assets
from apps.assets.models import Asset, Relationship
from apps.catalog.models import Capability, MissionArea, PlatformDomain, StrategicCategory
from apps.sources.models import Source


@override_settings(PUBLIC_REGION_SLUG="", REQUIRE_SITE_LOGIN=False)
class SearchPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.asset = Asset.objects.create(
            name="Alpha Airport",
            record_type="infrastructure",
            short_description="A public facility",
            unmanned_systems_relevance="Aviation research",
            status="source-backed",
            visibility="public",
        )
        cls.partner = Asset.objects.create(
            name="Beta Partner",
            record_type="organization",
            short_description="An operator",
            unmanned_systems_relevance="Aviation research",
            status="source-backed",
            visibility="public",
        )

    def results(self, query, **filters):
        params = QueryDict(mutable=True)
        params.update({"q": query, **filters})
        return list(filter_public_assets(params).values_list("pk", flat=True))

    def test_terms_can_match_different_rows_in_each_taxonomy(self):
        for relation, model in (
            ("strategic_categories", StrategicCategory),
            ("platform_domains", PlatformDomain),
            ("capabilities", Capability),
            ("missions", MissionArea),
        ):
            with self.subTest(relation=relation):
                first = model.objects.create(name=f"{relation} firstword")
                second = model.objects.create(name=f"{relation} secondword")
                getattr(self.asset, relation).add(first, second)
                self.assertEqual(self.results(f"{relation} firstword secondword"), [self.asset.pk])
                self.assertEqual(self.results('"firstword secondword"'), [])

    def test_synonyms_apply_to_sources_tags_and_both_relationship_directions(self):
        self.asset.capabilities.add(Capability.objects.create(name="UAV operations"))
        Source.objects.create(
            asset=self.partner, title="UAS program", url="https://example.org/program"
        )
        self.assertEqual(set(self.results("drone")), {self.asset.pk, self.partner.pk})
        self.assertEqual(self.results('"drone"'), [])

        self.partner.display_name = "Uncrewed center"
        self.partner.save()
        self.asset.capabilities.clear()
        self.partner.sources.all().delete()
        for origin, target in ((self.asset, self.partner), (self.partner, self.asset)):
            with self.subTest(direction=origin.name):
                relationship = Relationship.objects.create(
                    from_asset=origin, to_asset=target, relationship_type="supports"
                )
                self.assertEqual(set(self.results("drone")), {self.asset.pk, self.partner.pk})
                relationship.is_public = False
                relationship.save()
                self.assertEqual(self.results("drone"), [self.partner.pk])
                relationship.delete()

    def test_facet_filters_do_not_restrict_which_related_rows_search_can_match(self):
        chosen = Capability.objects.create(name="Selected category")
        other = Capability.objects.create(name="Separate searchable term")
        self.asset.capabilities.add(chosen, other)
        self.assertEqual(
            self.results("searchable", capability=chosen.slug), [self.asset.pk]
        )
        self.assertEqual(self.results("searchable", capability="nonexistent"), [])

    def test_limit_below_equal_and_above_total(self):
        for limit, expected_queries in ((1, 2), (2, 1), (3, 1)):
            with self.subTest(limit=limit), self.assertNumQueries(expected_queries):
                assets, count = limited_assets(Asset.public.order_by("name"), limit)
                self.assertEqual(count, 2)
                self.assertEqual(len(assets), min(limit, 2))

    def test_empty_results_need_only_one_query(self):
        with self.assertNumQueries(1):
            assets, count = limited_assets(Asset.public.filter(name="Missing"), 100)
        self.assertEqual(assets, [])
        self.assertEqual(count, 0)

    def test_api_does_not_recount_complete_search_results(self):
        factory = RequestFactory()
        for view in (asset_list, asset_geojson):
            for query in ("", "airport", "Missing"):
                with self.subTest(view=view.__name__, query=query), patch(
                    "django.db.models.query.QuerySet.count",
                    side_effect=AssertionError("Complete results must not be counted twice"),
                ):
                    response = view(factory.get("/", {"q": query, "limit": 2}))
                    self.assertEqual(response.status_code, 200)

    def test_api_keeps_exact_total_when_results_are_truncated(self):
        factory = RequestFactory()
        for view in (asset_list, asset_geojson):
            with self.subTest(view=view.__name__):
                body = json.loads(view(factory.get("/", {"limit": 1})).content)
                self.assertEqual(body["result_count"], 2)
                self.assertEqual(body["returned_count"], 1)
                self.assertTrue(body["truncated"])
