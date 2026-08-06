# Data dictionary

## Asset

The public-facing ecosystem record. `record_type` distinguishes universities, organizations, facilities, programs, infrastructure, and operating environments. `short_description` supports compact directory and map displays, `overview` explains what the asset is, and `unmanned_systems_relevance` separately explains why the record belongs in the system.

Public contact data is structured as `contact_text`, `contact_phone`, `contact_email`, and `contact_url`. `contact_text` identifies the scope of the contact, such as an airport manager, institution-level inquiries, or a parent organization. Phone and email remain blank when an official source does not publish a reliable value; `contact_url` provides the source-backed public route instead.

Current work and collaboration use `activity_status`, `current_activity`, `partnership_opportunities`, `activity_source_url`, and `activity_last_verified_at`. These fields are optional, but a public source and review date are required whenever an activity or partnership claim is populated. They describe publicly documented activity and a contact route, not an open solicitation or guaranteed opportunity.

Economic-development and site-readiness data use `owner_operator`, `available_acreage`, `development_status`, `development_notes`, `infrastructure_access`, `development_source_url`, and `development_last_verified_at`. Published acreage is contextual site information and does not guarantee that land or space is currently available. Populated development claims also require a public source and review date.

Lifecycle values are `draft`, `needs-review`, `verified`, `published`, and `archived`. Visibility values are `public`, `partner`, and `internal`. Unauthenticated queries require both `published` status and `public` visibility.

Location uses WGS84 decimal latitude and longitude. `location_precision` is `exact`, `site`, `approximate`, `locality`, `regional`, or `hidden`. The public API suppresses geometry when coordinates are absent. Regional records identify a service area without asserting a point; hidden locations cannot be public.

Internal-only fields such as `internal_notes` and source notes are never emitted by public serializers.

Catalog-loaded records include an internal provenance marker. The public source list provides the evidence URL and verification date; it does not expose internal curation notes.

## Taxonomy

`StrategicCategory`, `PlatformDomain`, `Capability`, and `MissionArea` are independent many-to-many dimensions. Each has a stable slug, display order, active flag, and optional description. `Region` is a geographic grouping and a direct asset relationship for the MVP.

`Advanced Air Mobility` is a platform domain applied only where a public source documents AAM, eVTOL, enabling airspace integration, or an AAM-specific program. It is not applied automatically to every airport or UAS record.

## Source

A source belongs to one asset and records title, URL, source date, verification date, verification status, notes, and public visibility. Bulk publication in the admin skips records without at least one public source.

## Relationship

A directed typed connection between two assets. Supported types are operates, located at, partners with, funds, supports, and participates in. Only public relationships between public records appear in the public API and profile.

The checked-in real-data catalog also contains a reviewed set of public relationships. The seed command creates or updates these links without deleting relationships maintained manually in the admin.
