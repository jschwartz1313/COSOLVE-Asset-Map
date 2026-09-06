# Interview-Informed Asset Map Update

## Implemented

- **Find resources:** shortcuts for testing, projects/programs, workforce, business support,
  counter-UAS, airspace integration, and manufacturing. These reuse existing classifications;
  they do not introduce competing taxonomy definitions or automatically certify suitability.
- **Project and site details:** activity status, published test-site specifications, and minimum
  published runway length filters. Unknown runway lengths never match a minimum-length query.
  Map, directory, active-filter chips, saved views, and filtered staff CSV exports retain them.
- **Visible lifecycle:** documented activity status now appears in map results, popups, and
  directory listings. Missing status remains unknown; a proposed project is not implicitly active.
- **Testing and access:** editable aircraft/testing scope, dimensions, runway length, and access
  constraints on asset profiles. Evidence URL and source-review date are required for claims.
  Fields are included in history, the detail API, and CSV import/export.
  Out-of-date specifications also enter the existing staff data-quality review queue.
- **Get connected:** public referral routes that distinguish VIPC ecosystem/commercialization,
  VEDP business location support, DOAV aviation integration, VSGC workforce, and NASA research
  partnerships. Existing strategies and program pages are linked instead of copied into new guidance.
- **Workforce specificity:** CSIIP and STEM Takes Flight added as source-backed supporting programs,
  not generic university dots. Both serve Virginia statewide and are coordinated from Hampton;
  no artificial training-site pins are shown. Their regional classification identifies coordination,
  not exclusive service coverage. New records await editorial review.

## Public Evidence

- [Virginia Spaceport Authority facilities](https://www.vaspace.org/our-facilities): MARS runway,
  hangar, VTOL pad, airspace footprint, and operator coordination.
- [Virginia Tech Drone Park](https://ictas.vt.edu/Facilities/ictas-drone-park.html): netted enclosure
  dimensions, research/education scope, scheduling, and commercial-use requirements.
- [NASA range opening announcement](https://www.nasa.gov/centers-and-facilities/langley/nasa-langley-drone-flying-site-open-for-testing/):
  historical range size and access process. The profile explicitly identifies this as a July 2015
  source, not confirmation of present-day operating limits or authorizations.
- [NASA Langley Front Door](https://www.nasa.gov/langley/frontdoor/): public partnership and
  technology-transfer routes, replacing the generic NASA contact link.
- [DOAV AAM program](https://doav.virginia.gov/advanced_air_mobility/): direct agency entry point
  for program contacts, projects, strategy, VA-FIX, and infrastructure resources.
- [CSIIP](https://vsgc.odu.edu/csiip/) and
  [STEM Takes Flight](https://vsgc.odu.edu/STEMtakesFlight/): program purposes, public contacts,
  and participation routes. The latter's 2026 deadlines have passed; no new intake is claimed.
- [VSGC](https://vsgc.odu.edu/about-us/): coordinating organization and Hampton office.

## Boundaries

Interview notes guided priorities, not factual verification. Private remarks, personal details not
publicly listed, internal spreadsheets, restricted test requirements, and unpublished project
proposals were not published. No access privileges changed.

The map is not a flight-authorization service. Aircraft-specific suitability, BVLOS approvals,
counter-UAS authorities, availability, pricing, and booking require operator or agency confirmation.
Proposed corridors, future innovation districts, funding commitments, and employment/impact claims
need current public evidence before they become records or operational layers.

## Deployment and Maintenance

The migration adds optional fields without deleting existing data. Catalog additions use
`seed_real_data --add-missing`; profile enrichment fills blanks and preserves staff-managed records.
Test specifications and their evidence are filled as a group, never mixed with existing specs.
Three website/contact corrections use baseline checks and preserve later edits. No source or asset
was automatically promoted to editorially reviewed in this update.

The standard Render build applies the migration, additions, guarded corrections, and enrichment.
Public program pages should be revisited periodically, especially application cycles and site access.
