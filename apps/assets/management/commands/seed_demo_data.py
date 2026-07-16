from datetime import date

from django.core.management.base import BaseCommand

from apps.assets.models import Asset, Relationship
from apps.catalog.models import Capability, MissionArea, PlatformDomain, Region, StrategicCategory
from apps.sources.models import Source

CATEGORIES = [
    "Test and operational environments",
    "Research and technical depth",
    "Federal and defense customer access",
    "Commercialization and capital",
    "Manufacturing and supply chain",
    "State strategy and coordination",
    "Workforce and talent",
    "Multi-domain missions",
    "Digital, data, energy, and communications infrastructure",
    "Companies and solution providers",
    "Physical infrastructure and logistics",
    "Programs and initiatives",
]
DOMAINS = [
    "Unmanned aircraft systems",
    "Maritime surface systems",
    "Undersea systems",
    "Ground vehicles and robotics",
    "Counter-UAS",
    "Cross-domain autonomy",
    "Space-enabled services",
]
CAPABILITIES = [
    "Autonomy and artificial intelligence",
    "Perception, sensing, and sensor fusion",
    "Command, control, and communications",
    "Navigation and positioning",
    "Cybersecurity and resilient systems",
    "Simulation, digital twins, and synthetic environments",
    "Testing, evaluation, verification, and validation",
    "Systems engineering and integration",
    "Payloads and mission systems",
    "Propulsion, batteries, fuels, and energy systems",
    "Manufacturing, materials, and prototyping",
    "Operations, maintenance, and sustainment",
    "Data engineering, analytics, and edge computing",
    "Safety, policy, regulatory, and airspace integration",
]
MISSIONS = [
    "Intelligence, surveillance, and reconnaissance",
    "Logistics and contested logistics",
    "Maritime domain awareness",
    "Infrastructure inspection",
    "Search and rescue",
    "Environmental monitoring",
    "Public safety and emergency response",
    "Force protection and installation security",
    "Counter-UAS",
    "Mine countermeasures",
    "Surveying and mapping",
    "Agriculture and natural resources",
    "Communications relay",
    "Training and experimentation",
]
REGIONS = [
    ("Hampton Roads", "Planning district"),
    ("Greater Richmond", "Metro region"),
    ("Northern Virginia", "Metro region"),
    ("New River Valley", "Planning district"),
    ("Shenandoah Valley", "Regional cluster"),
    ("Southside Virginia", "Regional cluster"),
]

RECORDS = [
    (
        "Demo Coastal Autonomy Test Basin",
        "facility",
        "Norfolk",
        36.8529,
        -76.2870,
        "Hampton Roads",
        [0, 1],
        [1, 2],
        [0, 6],
        [2, 13],
    ),
    (
        "Demo Maritime Robotics Integration Lab",
        "facility",
        "Virginia Beach",
        36.8529,
        -75.9780,
        "Hampton Roads",
        [1, 9],
        [1, 2],
        [0, 7],
        [2, 9],
    ),
    (
        "Demo Advanced Composites Workshop",
        "facility",
        "Chesapeake",
        36.7682,
        -76.2875,
        "Hampton Roads",
        [4, 9],
        [0, 1],
        [9, 10],
        [1, 3],
    ),
    (
        "Demo Autonomous Systems Research Institute",
        "organization",
        "Hampton",
        37.0299,
        -76.3452,
        "Hampton Roads",
        [1, 7],
        [0, 5],
        [0, 1],
        [0, 13],
    ),
    (
        "Demo Resilient Communications Range",
        "operating-environment",
        "Suffolk",
        36.7282,
        -76.5836,
        "Hampton Roads",
        [0, 8],
        [0, 5],
        [2, 4],
        [12, 13],
    ),
    (
        "Demo Blue Economy Venture Studio",
        "organization",
        "Norfolk",
        36.8508,
        -76.2859,
        "Hampton Roads",
        [3, 9],
        [1, 2],
        [7, 12],
        [2, 5],
    ),
    (
        "Demo Unmanned Systems Technician Certificate",
        "program",
        "Portsmouth",
        36.8354,
        -76.2983,
        "Hampton Roads",
        [6, 11],
        [5],
        [7, 11],
        [1, 13],
    ),
    (
        "Demo Port Logistics Innovation Yard",
        "infrastructure",
        "Newport News",
        37.0871,
        -76.4730,
        "Hampton Roads",
        [4, 10],
        [1, 3],
        [10, 11],
        [1, 3],
    ),
    (
        "Demo Virginia Autonomy Coordination Office",
        "organization",
        "Richmond",
        37.5407,
        -77.4360,
        "Greater Richmond",
        [5, 11],
        [5],
        [7, 13],
        [6, 13],
    ),
    (
        "Demo Robotics Commercialization Accelerator",
        "program",
        "Richmond",
        37.5538,
        -77.4603,
        "Greater Richmond",
        [3, 11],
        [3, 5],
        [0, 7],
        [3, 13],
    ),
    (
        "Demo Edge Analytics Test Center",
        "facility",
        "Ashburn",
        39.0438,
        -77.4874,
        "Northern Virginia",
        [1, 8],
        [0, 6],
        [4, 12],
        [0, 12],
    ),
    (
        "Demo Counter-UAS Evaluation Range",
        "operating-environment",
        "Manassas",
        38.7509,
        -77.4753,
        "Northern Virginia",
        [0, 2],
        [0, 4],
        [1, 6],
        [7, 8],
    ),
    (
        "Demo Space-Enabled Navigation Lab",
        "facility",
        "Herndon",
        38.9696,
        -77.3861,
        "Northern Virginia",
        [1, 8],
        [0, 6],
        [3, 4],
        [0, 12],
    ),
    (
        "Demo Applied Autonomy Graduate Program",
        "program",
        "Blacksburg",
        37.2296,
        -80.4139,
        "New River Valley",
        [1, 6],
        [3, 5],
        [0, 5],
        [3, 13],
    ),
    (
        "Demo Rural Flight Test Corridor",
        "operating-environment",
        "Christiansburg",
        37.1299,
        -80.4089,
        "New River Valley",
        [0, 7],
        [0],
        [6, 13],
        [5, 10],
    ),
    (
        "Demo Precision Agriculture Robotics Hub",
        "organization",
        "Harrisonburg",
        38.4496,
        -78.8689,
        "Shenandoah Valley",
        [1, 9],
        [0, 3],
        [0, 1],
        [5, 11],
    ),
    (
        "Demo Sensor Manufacturing Cooperative",
        "organization",
        "Staunton",
        38.1496,
        -79.0717,
        "Shenandoah Valley",
        [4, 9],
        [0, 3],
        [1, 10],
        [3, 10],
    ),
    (
        "Demo Emergency Robotics Training Center",
        "facility",
        "Danville",
        36.5859,
        -79.3950,
        "Southside Virginia",
        [0, 6],
        [0, 3],
        [7, 11],
        [4, 6],
    ),
    (
        "Demo Battery Systems Prototyping Plant",
        "infrastructure",
        "South Boston",
        36.6988,
        -78.9014,
        "Southside Virginia",
        [4, 8],
        [3, 5],
        [9, 10],
        [1, 3],
    ),
    (
        "Demo Multi-Domain Field Exercise",
        "program",
        "Martinsville",
        36.6915,
        -79.8725,
        "Southside Virginia",
        [7, 11],
        [0, 1, 3],
        [0, 2, 7],
        [1, 13],
    ),
]


class Command(BaseCommand):
    help = "Seed taxonomy values and 20 clearly fictional development records."

    def handle(self, *args, **options):
        category_objects = [
            StrategicCategory.objects.get_or_create(name=name)[0] for name in CATEGORIES
        ]
        domain_objects = [PlatformDomain.objects.get_or_create(name=name)[0] for name in DOMAINS]
        capability_objects = [
            Capability.objects.get_or_create(name=name)[0] for name in CAPABILITIES
        ]
        mission_objects = [MissionArea.objects.get_or_create(name=name)[0] for name in MISSIONS]
        region_objects = {}
        for name, region_type in REGIONS:
            region, _ = Region.objects.update_or_create(
                name=name, defaults={"region_type": region_type}
            )
            region_objects[name] = region

        assets = []
        for record in RECORDS:
            (
                name,
                record_type,
                city,
                latitude,
                longitude,
                region_name,
                categories,
                domains,
                capabilities,
                missions,
            ) = record
            asset, _ = Asset.objects.update_or_create(
                name=name,
                city=city,
                defaults={
                    "record_type": record_type,
                    "short_description": (
                        "Representative development record for interface and workflow testing."
                    ),
                    "unmanned_systems_relevance": (
                        "Demonstrates how a publicly releasable ecosystem asset can support "
                        "unmanned systems research, testing, commercialization, operations, "
                        "or workforce development."
                    ),
                    "state": "VA",
                    "latitude": latitude,
                    "longitude": longitude,
                    "location_precision": Asset.LocationPrecision.APPROXIMATE,
                    "region": region_objects[region_name],
                    "status": Asset.Status.PUBLISHED,
                    "visibility": Asset.Visibility.PUBLIC,
                    "last_verified_at": date(2026, 7, 1),
                    "internal_notes": (
                        "Fictional development fixture. Do not treat as a real-world claim."
                    ),
                },
            )
            asset.strategic_categories.set(category_objects[item] for item in categories)
            asset.platform_domains.set(domain_objects[item] for item in domains)
            asset.capabilities.set(capability_objects[item] for item in capabilities)
            asset.missions.set(mission_objects[item] for item in missions)
            Source.objects.update_or_create(
                asset=asset,
                title="Development fixture - no factual claim",
                defaults={
                    "verification_status": "verified",
                    "last_verified_at": date(2026, 7, 1),
                    "is_public": True,
                },
            )
            assets.append(asset)

        for source, target in zip(assets[::2], assets[1::2], strict=False):
            Relationship.objects.get_or_create(
                from_asset=source,
                to_asset=target,
                relationship_type=Relationship.RelationshipType.PARTNERS_WITH,
                defaults={
                    "description": "Representative development relationship.",
                    "is_public": True,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(assets)} fictional demo assets."))
