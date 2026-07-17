# Data dictionary

## Asset

The public-facing ecosystem record. `record_type` distinguishes organizations, facilities, programs, infrastructure, and operating environments. `unmanned_systems_relevance` is required and explains why the record belongs in the system.

Lifecycle values are `draft`, `needs-review`, `verified`, `published`, and `archived`. Visibility values are `public`, `partner`, and `internal`. Unauthenticated queries require both `published` status and `public` visibility.

Location uses WGS84 decimal latitude and longitude. `location_precision` is `exact`, `approximate`, `locality`, or `hidden`. The MVP public API suppresses geometry when coordinates are absent. Hidden locations cannot be public.

Internal-only fields such as `internal_notes`, workflow status, and source notes are never emitted by public serializers.

Catalog-loaded records include an internal provenance marker. The public source list provides the evidence URL and verification date; it does not expose internal curation notes.

## Taxonomy

`StrategicCategory`, `PlatformDomain`, `Capability`, and `MissionArea` are independent many-to-many dimensions. Each has a stable slug, display order, active flag, and optional description. `Region` is a geographic grouping and a direct asset relationship for the MVP.

## Source

A source belongs to one asset and records title, URL, source date, verification date, verification status, notes, and public visibility. Bulk publication in the admin skips records without at least one public source.

## Relationship

A directed typed connection between two assets. Supported types are operates, located at, partners with, funds, supports, and participates in. Only public relationships between public records appear in the public API and profile.

The checked-in real-data catalog also contains a reviewed set of public relationships. The seed command creates or updates these links without deleting relationships maintained manually in the admin.
