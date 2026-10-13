from django.http import QueryDict
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.api.query import filter_public_assets
from apps.assets.models import Asset
from apps.catalog.models import Region
from apps.sources.models import Source


@override_settings(PUBLIC_REGION_SLUG="", REQUIRE_SITE_LOGIN=False)
class TypoSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hampton Roads")
        cls.other_region = Region.objects.create(name="New River Valley")
        cls.center = cls.create_asset(
            "REaKTOR Technology Innovation Center", region=cls.region,
            city="Hampton", search_aliases="REaKTOR\nExamplepartner",
        )

    @classmethod
    def create_asset(cls, name, **fields):
        return Asset.objects.create(
            name=name, record_type="organization", short_description="Public technology center",
            unmanned_systems_relevance="Supports public research", status="source-backed",
            visibility="public", **fields,
        )

    def results(self, query, **filters):
        params = QueryDict(mutable=True)
        params.update({"q": query, **filters})
        return list(filter_public_assets(params).values_list("pk", flat=True))

    def test_reactor_and_common_typos_find_the_named_center(self):
        for query in ("reactor", "REACTOR", "reakotr", "reakto", "reactor technology"):
            with self.subTest(query=query):
                self.assertEqual(self.results(query), [self.center.pk])

    def test_display_names_and_approved_aliases_are_searchable(self):
        self.center.display_name = "Innovationworks Research Campus"
        self.center.save()
        self.assertEqual(self.results("innovationwroks"), [self.center.pk])
        self.assertEqual(self.results("exampleparnter"), [self.center.pk])

    def test_normal_matches_rank_before_typo_only_matches(self):
        exact = self.create_asset("Reactor")
        mention = self.create_asset("Zeta Company", overview="Provides reactor research")
        self.assertEqual(self.results("reactor"), [exact.pk, mention.pk, self.center.pk])
        self.center.overview = "A reactor technology center"
        self.center.save()
        self.assertEqual(self.results("reactor"), [exact.pk, self.center.pk, mention.pk])

    def test_quoted_phrases_short_codes_and_unrelated_terms_are_not_fuzzy(self):
        for query in ('"reactor"', '"reactor technology"', "rekr", "REKT", "zzzzzzzz"):
            with self.subTest(query=query):
                self.assertEqual(self.results(query), [])
        self.assertEqual(self.results('"reaktor technology"'), [self.center.pk])
        self.assertEqual(self.results("reaktor"), [self.center.pk])

    def test_every_term_and_active_filter_still_has_to_match(self):
        self.assertEqual(self.results("reactor Hampton"), [self.center.pk])
        self.assertEqual(self.results("reactor Richmond"), [])
        self.assertEqual(self.results("reactor", region=self.region.slug), [self.center.pk])
        self.assertEqual(self.results("reactor", region=self.other_region.slug), [])
        self.assertEqual(self.results("reactor", record_type="university"), [])

    def test_private_fields_and_sources_do_not_supply_fuzzy_matches(self):
        internal = self.create_asset("Secretive Facility")
        internal.visibility = "internal"
        internal.save()
        self.center.internal_notes = "Confidential"
        self.center.save()
        Source.objects.create(
            asset=self.center, title="RestrictedEvidence", url="https://example.org/private",
            is_public=False,
        )
        for query in ("secretiwe", "confidentail", "restrictedevidnce"):
            with self.subTest(query=query):
                self.assertEqual(self.results(query), [])

    @override_settings(PUBLIC_REGION_SLUG="new-river-valley")
    def test_fuzzy_matches_do_not_bypass_regional_publication_scope(self):
        self.assertEqual(self.results("reactor"), [])

    def test_staff_name_changes_are_immediately_searchable(self):
        self.assertEqual(self.results("reactor"), [self.center.pk])
        self.center.name = "Newbrand Innovation Center"
        self.center.search_aliases = ""
        self.center.save()
        self.assertEqual(self.results("reactor"), [])
        self.assertEqual(self.results("newbrnad"), [self.center.pk])

    def test_typo_matching_uses_one_lightweight_name_query(self):
        with self.assertNumQueries(2):
            self.assertEqual(self.results("reactor"), [self.center.pk])
        for query in ('"reaktor"', "uas", "x" * 501):
            expected_queries = 0 if len(query) > 500 else 1
            with self.subTest(query=query), self.assertNumQueries(expected_queries):
                self.results(query)

    def test_directory_list_and_map_api_share_the_same_matches(self):
        page = self.client.get(reverse("core:directory"), {"q": "reactor"})
        self.assertEqual([a.pk for a in page.context["page_obj"]], [self.center.pk])
        self.assertEqual(page.context["sort_key"], "relevance")
        for endpoint, results_key in (
            ("api:asset-list", "results"), ("api:asset-geojson", "features"),
        ):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(reverse(endpoint), {"q": "reactor"}).json()
                self.assertEqual(response["result_count"], 1)
                self.assertEqual(len(response[results_key]), 1)
                self.assertEqual(response["active_filters"]["q"], "reactor")
