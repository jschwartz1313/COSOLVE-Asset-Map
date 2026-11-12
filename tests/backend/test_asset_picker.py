from urllib.parse import parse_qs, urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.assets.models import Asset
from apps.catalog.models import Region


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class AssetPickerTests(TestCase):
    url = "/compare/options/"

    @classmethod
    def create_asset(cls, name, **overrides):
        fields = {
            "name": name,
            "record_type": Asset.RecordType.FACILITY,
            "status": Asset.Status.SOURCE_BACKED,
            "visibility": Asset.Visibility.PUBLIC,
            "short_description": "Public research facility",
            "unmanned_systems_relevance": "Prototype evaluation",
        }
        fields.update(overrides)
        return Asset.objects.create(**fields)

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hampton Roads")
        cls.other_region = Region.objects.create(name="New River Valley")
        cls.private_region = Region.objects.create(name="Restricted Inventory")
        Region.objects.create(name="Unused Region")
        cls.center = cls.create_asset(
            "REaKTOR Technology Innovation Center", display_name="Alpha Innovationworks Campus",
            search_aliases="REaKTOR\nExamplepartner", region=cls.region, city="Hampton", state="VA",
            contact_email="private-picker@example.com", contact_phone="555-010-9876",
            contact_text="PrivatePickerContact", internal_notes="ConfidentialEditorialMarker",
            review_notes="PrivatePickerReview",
        )
        cls.program = cls.create_asset(
            "Alpha catalog identity", display_name="beta Test Program",
            record_type=Asset.RecordType.PROGRAM, region=cls.other_region,
            city="Blacksburg", state="VA",
        )
        cls.fallback = cls.create_asset(
            "Fallback Workshop", record_type=Asset.RecordType.ORGANIZATION,
        )
        cls.published = cls.create_asset(
            "Research Laboratory", display_name="Delta Research Laboratory", region=cls.region,
            status=Asset.Status.PUBLISHED, reviewed_at=timezone.now(),
            last_verified_at=timezone.localdate(),
        )
        cls.public_assets = [cls.center, cls.program, cls.published, cls.fallback]
        hidden_fields = [
            {"status": status} for status in (
                Asset.Status.DRAFT, Asset.Status.NEEDS_REVIEW,
                Asset.Status.VERIFIED, Asset.Status.ARCHIVED,
            )
        ] + [
            {"visibility": Asset.Visibility.PARTNER},
            {"visibility": Asset.Visibility.INTERNAL},
        ]
        cls.hidden_assets = [
            cls.create_asset(
                f"Confidential inventory {index}", region=cls.private_region,
                search_aliases="Examplepartner", **fields,
            )
            for index, fields in enumerate(hidden_fields)
        ]
        cls.hidden_assets.append(cls.create_asset(
            "Edward Via College of Osteopathic Medicine", record_type=Asset.RecordType.UNIVERSITY,
            region=cls.private_region, search_aliases="Examplepartner",
        ))

    def options(self, params=None):
        response = self.client.get(self.url, params or {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"].split(";")[0], "application/json")
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        payload = response.json()
        self.assertEqual(set(payload), {"assets", "count", "page", "pages"})
        self.assertIsInstance(payload["assets"], list)
        for key in ("count", "page", "pages"):
            self.assertIsInstance(payload[key], int)
        for asset in payload["assets"]:
            self.assertEqual(set(asset), {
                "slug", "name", "url", "record_type", "record_type_label", "location",
            })
        return payload

    def assert_bad_filter(self, params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers["Content-Type"].split(";")[0], "application/json")
        self.assertIsInstance(response.json(), dict)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")

    def paginated_assets(self):
        extras = [
            self.create_asset(
                f"Reverse catalog identity {24 - index:02d}",
                display_name=f"Catalog facility {index:02d}", region=self.region,
            )
            for index in range(25)
        ]
        return sorted(self.public_assets + extras, key=lambda asset: asset.public_name.casefold())

    def test_empty_search_has_public_display_names_in_alphabetical_pages(self):
        assets = self.paginated_assets()
        first = self.options()
        self.assertEqual((first["count"], first["page"], first["pages"]), (29, 1, 2))
        self.assertEqual(len(first["assets"]), 24)
        self.assertEqual([row["slug"] for row in first["assets"]],
                         [asset.slug for asset in assets[:24]])
        self.assertEqual(first["assets"][0], {
            "slug": self.center.slug,
            "name": "Alpha Innovationworks Campus",
            "url": self.center.get_absolute_url(),
            "record_type": Asset.RecordType.FACILITY,
            "record_type_label": "Facility",
            "location": "Hampton, VA",
        })
        for query in ("", "   "):
            with self.subTest(query=query):
                self.assertEqual(self.options({"q": query}), first)
        last = self.options({"page": "2"})
        self.assertEqual((last["count"], last["page"], last["pages"]), (29, 2, 2))
        self.assertEqual([row["slug"] for row in last["assets"]],
                         [asset.slug for asset in assets[24:]])
        self.assertEqual(last["assets"][-1]["name"], self.fallback.name)

    def test_page_numbers_follow_paginator_first_and_last_page_fallbacks(self):
        self.paginated_assets()
        first = self.options()
        last = self.options({"page": "2"})
        for page in ("not-a-number", "1.5", ""):
            with self.subTest(page=page):
                self.assertEqual(self.options({"page": page}), first)
        for page in ("0", "-1", "3", "999999"):
            with self.subTest(page=page):
                self.assertEqual(self.options({"page": page}), last)

    def test_single_record_type_and_region_filters_and_unknown_region(self):
        for record_type, _label in Asset.RecordType.choices:
            expected = [asset.slug for asset in self.public_assets
                        if asset.record_type == record_type]
            with self.subTest(record_type=record_type):
                payload = self.options({"record_type": record_type})
                self.assertEqual([row["slug"] for row in payload["assets"]], expected)
                self.assertEqual(payload["count"], len(expected))
        self.assertEqual(self.options({"record_type": "", "region": ""}), self.options())
        payload = self.options({"region": self.other_region.slug})
        self.assertEqual([row["slug"] for row in payload["assets"]], [self.program.slug])
        payload = self.options({"record_type": "facility", "region": self.region.slug})
        self.assertEqual([row["slug"] for row in payload["assets"]],
                         [self.center.slug, self.published.slug])
        for params in (
            {"record_type": "program", "region": self.region.slug},
            {"region": "unknown-but-valid-region", "page": "999"},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.options(params), {
                    "assets": [], "count": 0, "page": 1, "pages": 1,
                })

    def test_search_preserves_fuzzy_display_names_aliases_ranking_and_filters(self):
        exact = self.create_asset("Reactor", region=self.other_region)
        payload = self.options({"q": "reactor"})
        self.assertEqual([row["slug"] for row in payload["assets"]],
                         [exact.slug, self.center.slug])
        payload = self.options({"q": "REaKTOR"})
        self.assertEqual([row["slug"] for row in payload["assets"]],
                         [self.center.slug, exact.slug])
        for query in ("innovationwroks", "exampleparnter"):
            with self.subTest(query=query):
                payload = self.options({"q": query})
                self.assertEqual([row["slug"] for row in payload["assets"]], [self.center.slug])
                self.assertEqual(payload["count"], 1)
        for filters in ({"record_type": "program"}, {"region": self.other_region.slug}):
            with self.subTest(filters=filters):
                self.assertEqual(self.options({"q": "exampleparnter", **filters})["count"], 0)

    def test_malformed_filters_return_json_bad_requests(self):
        for params in (
            {"record_type": "not-a-type"},
            {"record_type": "Facility"},
            {"record_type": "facility,program"},
            {"region": "hampton roads"},
            {"region": "../../hampton-roads"},
            {"region": "hampton-roads,new-river-valley"},
        ):
            with self.subTest(params=params):
                self.assert_bad_filter(params)

    def test_publication_scope_and_minimal_payload_never_expose_private_data(self):
        payload = self.options()
        self.assertEqual([row["slug"] for row in payload["assets"]],
                         [asset.slug for asset in self.public_assets])
        response = self.client.get(self.url)
        for hidden in self.hidden_assets:
            self.assertNotContains(response, hidden.name)
            self.assertNotContains(response, hidden.slug)
        for value in (
            self.center.contact_email, self.center.contact_phone, self.center.contact_text,
            self.center.internal_notes, self.center.review_notes,
        ):
            self.assertNotContains(response, value)
        self.assertEqual(self.options({"q": "ConfidentialEditorialMarker"})["assets"], [])
        with override_settings(PUBLIC_REGION_SLUG=self.region.slug):
            allowed = {self.center.slug, self.published.slug}
            payload = self.options()
            self.assertEqual({row["slug"] for row in payload["assets"]}, allowed)
            self.assertEqual(payload["count"], 2)
            self.assertEqual(self.options({"q": "exampleparnter"})["count"], 1)
            for params in ({"region": self.other_region.slug}, {"q": self.program.public_name}):
                with self.subTest(params=params):
                    payload = self.options(params)
                    self.assertTrue({row["slug"] for row in payload["assets"]} <= allowed)

    def test_request_length_limits_reject_overlong_values_without_truncation(self):
        for key, limit in (("q", 200), ("region", 80), ("record_type", 30)):
            with self.subTest(key=key):
                self.assert_bad_filter({key: "x" * (limit + 1)})
        for params in ({"q": "x" * 200}, {"region": "x" * 80}):
            with self.subTest(params=params):
                self.assertEqual(self.options(params), {
                    "assets": [], "count": 0, "page": 1, "pages": 1,
                })

    def test_picker_accepts_get_only(self):
        self.options()
        for method in ("post", "put", "patch", "delete", "head", "options"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.url)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.headers["Allow"], "GET")

    @override_settings(REQUIRE_SITE_LOGIN=True)
    def test_login_middleware_gates_picker_and_authenticated_requests_remain_public(self):
        path = f"{self.url}?q=exampleparnter"
        self.assertRedirects(
            self.client.get(path), f"/login/?{urlencode({'next': path})}",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get("/compare/").status_code, 302)
        user = get_user_model().objects.create_user("picker-viewer", password=None)
        self.client.force_login(user)
        payload = self.options({"q": "exampleparnter"})
        self.assertEqual([row["slug"] for row in payload["assets"]], [self.center.slug])

    def test_compare_keeps_server_search_and_public_picker_context(self):
        response = self.client.get("/compare/", {
            "q": "exampleparnter", "asset": self.program.slug,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assets"], [self.program])
        self.assertEqual([row["asset"] for row in response.context["candidates"]], [self.center])
        candidate = response.context["candidates"][0]
        self.assertEqual(parse_qs(candidate["query"]), {
            "asset": [self.program.slug, self.center.slug],
        })
        self.assertContains(response, f'Add {self.center.public_name}')
        self.assertEqual(response.context["picker_record_types"], Asset.RecordType.choices)
        self.assertIsInstance(response.context["picker_regions"], list)
        self.assertCountEqual(response.context["picker_regions"], [
            {"slug": region.slug, "name": region.name}
            for region in (self.region, self.other_region)
        ])
        with override_settings(PUBLIC_REGION_SLUG=self.region.slug):
            response = self.client.get("/compare/")
            self.assertEqual(response.context["picker_regions"], [
                {"slug": self.region.slug, "name": self.region.name},
            ])
