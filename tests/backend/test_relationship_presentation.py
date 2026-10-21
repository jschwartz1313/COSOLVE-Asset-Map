from django.test import SimpleTestCase, TestCase, override_settings

from apps.assets.models import Asset, Relationship
from apps.catalog.models import Region

INCOMING_LABELS = {
    "operates": "Operated by",
    "located-at": "Location of",
    "partners-with": "Partners with",
    "funds": "Funded by",
    "supports": "Supported by",
    "participates-in": "Participants include",
    "hosts": "Hosted by",
    "manufactures-for": "Receives manufacturing from",
}


class IncomingRelationshipLabelTests(SimpleTestCase):
    def test_every_supported_direction_has_a_readable_incoming_label(self):
        self.assertEqual(set(INCOMING_LABELS), set(Relationship.RelationshipType.values))
        for relationship_type, label in INCOMING_LABELS.items():
            with self.subTest(relationship_type=relationship_type):
                relationship = Relationship(relationship_type=relationship_type)
                self.assertEqual(relationship.incoming_label, label)

    def test_unexpected_legacy_type_uses_a_neutral_incoming_label(self):
        self.assertEqual(
            Relationship(relationship_type="legacy-link").incoming_label, "Related from",
        )


@override_settings(REQUIRE_SITE_LOGIN=False, PUBLIC_REGION_SLUG="")
class RelationshipProfileDirectionTests(TestCase):
    @staticmethod
    def asset(name, **kwargs):
        return Asset.objects.create(
            name=name,
            record_type=Asset.RecordType.ORGANIZATION,
            short_description="A relationship presentation test listing.",
            unmanned_systems_relevance="Supports autonomous systems.",
            **{"status": Asset.Status.SOURCE_BACKED, "visibility": Asset.Visibility.PUBLIC,
               **kwargs},
        )

    def test_profiles_reverse_wording_and_keep_stored_edges_and_api_contract(self):
        pairs = []
        for relationship_type in INCOMING_LABELS:
            source = self.asset(f"Catalog source {relationship_type}",
                                display_name=f"Public source {relationship_type}")
            target = self.asset(f"Public target {relationship_type}")
            edge = Relationship.objects.create(
                from_asset=source, to_asset=target, relationship_type=relationship_type,
            )
            pairs.append((source, target, edge))
        before = list(Relationship.objects.order_by("pk").values())
        history_before = list(Relationship.history.order_by("history_id").values())

        for source, target, edge in pairs:
            with self.subTest(relationship_type=edge.relationship_type):
                outward_label = edge.get_relationship_type_display()
                outgoing = self.client.get(source.get_absolute_url())
                incoming = self.client.get(target.get_absolute_url())
                self.assertContains(outgoing, (
                    f'<a href="{target.get_absolute_url()}"><span>{outward_label}</span>'
                    f'<strong>{target.public_name}</strong></a>'
                ), html=True)
                self.assertContains(incoming, (
                    f'<a href="{source.get_absolute_url()}">'
                    f'<span>{INCOMING_LABELS[edge.relationship_type]}</span>'
                    f'<strong>{source.public_name}</strong></a>'
                ), html=True)
                self.assertNotContains(incoming, source.name)
                for asset, related, direction in (
                    (source, target, "outgoing"), (target, source, "incoming"),
                ):
                    payload = self.client.get(f"/api/assets/{asset.slug}/").json()
                    self.assertEqual(payload["related_entities"], [{
                        "name": related.public_name,
                        "relationship": outward_label,
                        "direction": direction,
                        "url": related.get_absolute_url(),
                    }])

        self.assertEqual(list(Relationship.objects.order_by("pk").values()), before)
        self.assertEqual(list(Relationship.history.order_by("history_id").values()), history_before)

    def test_incoming_labels_do_not_expose_private_or_nonpublic_sources(self):
        target = self.asset("Visible target")
        public = self.asset("Visible source")
        Relationship.objects.create(
            from_asset=public, to_asset=target, relationship_type="hosts",
        )
        excluded = [
            self.asset("Private edge source"),
            self.asset("Internal source", visibility=Asset.Visibility.INTERNAL),
            self.asset("Partner source", visibility=Asset.Visibility.PARTNER),
            self.asset("Archived source", status=Asset.Status.ARCHIVED),
            self.asset("Draft source", status=Asset.Status.DRAFT),
        ]
        for index, source in enumerate(excluded):
            Relationship.objects.create(
                from_asset=source, to_asset=target, relationship_type="hosts",
                is_public=index != 0,
            )

        response = self.client.get(target.get_absolute_url())
        self.assertContains(response, '<span>Hosted by</span>', html=True, count=1)
        self.assertContains(response, public.public_name)
        for source in excluded:
            self.assertNotContains(response, source.public_name)
            self.assertNotContains(response, source.get_absolute_url())
        related = self.client.get(f"/api/assets/{target.slug}/").json()["related_entities"]
        self.assertEqual([item["name"] for item in related], [public.public_name])

    @override_settings(PUBLIC_REGION_SLUG="hampton-roads")
    def test_incoming_labels_preserve_regional_scope(self):
        region = Region.objects.create(name="Hampton Roads", slug="hampton-roads")
        other_region = Region.objects.create(name="Outside region", slug="outside-region")
        target = self.asset("Regional target", region=region)
        source = self.asset("Out of scope source", region=other_region)
        Relationship.objects.create(
            from_asset=source, to_asset=target, relationship_type="hosts",
        )
        response = self.client.get(target.get_absolute_url())
        self.assertNotContains(response, "Connected organizations and programs")
        self.assertNotContains(response, source.public_name)
        self.assertEqual(
            self.client.get(f"/api/assets/{target.slug}/").json()["related_entities"], [],
        )
