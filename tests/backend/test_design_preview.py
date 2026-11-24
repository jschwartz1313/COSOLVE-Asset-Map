from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.assets.models import Asset


@override_settings(REQUIRE_SITE_LOGIN=False, MULTISTATE_PUBLIC=False,
                   MULTISTATE_PREVIEW_USERS=("jschwartz",))
class DesignPreviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser("jschwartz", "", None)
        cls.others = [get_user_model().objects.create_superuser(name, "", None)
                      for name in ("Ale", "Chelsea", "OtherAdmin")]
        cls.guest = get_user_model().objects.create_user("Guest")
        base = dict(record_type="facility", short_description="Documented site",
                    unmanned_systems_relevance="Testing", status="source-backed")
        cls.va = Asset.objects.create(name="Virginia facility", state="VA",
                                      visibility="public", **base)
        cls.oh = Asset.objects.create(name="Ohio facility", state="OH", visibility="internal",
                                      benchmark_starter=True, **base)

    def test_current_version_is_unchanged_by_default(self):
        self.client.force_login(self.owner)
        page = self.client.get("/map/")
        self.assertNotContains(page, "is-v2")
        self.assertNotContains(page, "experience-v2.css")
        self.assertContains(page, 'title="2.0 design preview"')

    def test_owner_can_toggle_both_ways_without_changing_inventory(self):
        self.client.force_login(self.owner)
        before = self.client.get("/api/assets.geojson").json()
        response = self.client.post("/design-preview/", {
            "experience": "2.0", "next": "/map/?q=facility&map_basemap=street",
        })
        self.assertEqual(response.url, "/map/?q=facility&map_basemap=street")
        for path in ("/map/", "/directory/", self.va.get_absolute_url(), "/test-sites/",
                     "/manufacturing/", "/compare/", "/states/ohio/map/"):
            self.assertContains(self.client.get(path), "experience-v2.css")
        self.assertEqual(before, self.client.get("/api/assets.geojson").json())
        self.assertEqual(Asset.objects.count(), 2)
        response = self.client.post("/states/ohio/design-preview/", {
            "experience": "standard", "next": "/states/ohio/map/?q=facility",
        })
        self.assertEqual(response.url, "/states/ohio/map/?q=facility")
        self.assertNotContains(self.client.get(response.url), "experience-v2.css")

    def test_others_cannot_enable_preview_even_with_old_session_or_admin_access(self):
        for user in (*self.others, self.guest):
            self.client.force_login(user)
            session = self.client.session
            session["design_preview"] = "2.0"
            session.save()
            self.assertNotContains(self.client.get("/map/"), "experience-v2.css")
            self.assertNotContains(self.client.get("/map/"), "Site version")
            self.assertEqual(self.client.post("/design-preview/", {
                "experience": "2.0", "next": "/map/",
            }).status_code, 404)
            self.assertEqual(self.client.get("/states/ohio/map/").status_code, 404)

    def test_preview_requires_post_and_does_not_redirect_to_another_site(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/design-preview/").status_code, 405)
        for destination in ("https://example.org/", "//example.org/", "javascript:alert(1)"):
            response = self.client.post("/design-preview/", {
                "experience": "2.0", "next": destination,
            })
            self.assertEqual(response.url, "/map/")
        response = self.client.post("/design-preview/", {"experience": "unknown"})
        self.assertEqual(response.status_code, 400)
