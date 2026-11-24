# Peer-State Research and UI Pass

All new maps now start on Street, including Virginia. Explicitly saved basemap
choices remain valid. Grey, Topographic and Aerial remain selectable.

## Research Scope

Added 14 internal records across 11 peer states and expanded 17 existing profiles
across all 13 peer states. Virginia's public inventory and permissions are unchanged.
The peer catalog now contains 4,988 records. These are documented inventory counts,
not a ranking or a completed operator/editorial verification.

New records cover PADT, Parallel Systems, ADVANCED Motion Controls, Fotokite,
FLYMOTION, Michigan Aerospace, ULC Technologies, CRP USA, Eclipse Composites,
Parallax's mobile test laboratory, OU's Sooner Advanced Manufacturing Lab and
Innovation Hub fabrication resources, Aerotech, and FusionFlight. Related
Aerotech production addresses are represented as one campus, not inflated into
two assets. Parallax's mobile laboratory has no fixed map point.

`data/multistate/expansion_2026_11_24_starter.json` contains claim-level official
sources. `profiles_2026_11_24.json` contains exact before/after values, use cases,
access requirements and contact evidence. The insert-only import and guarded
enrichment command preserve staff changes, archived/deleted identities, rejected
or removed sources, visibility and verification decisions. Repeated enrichment
runs make no further changes. The release runs both through the existing pipeline.

Ten newly published addresses received exact Census address matches and are
marked as approximate address-range positions, not surveyed coordinates. Two OU
addresses did not meet the strict match rule and remain locality references with
their published street addresses retained. Existing cached geocodes were not
rechecked or overwritten.

## Evidence Decisions

- Fotokite's current official North American contact is Boulder. An old Syracuse
  address was not imported as an additional current office.
- Michigan Aerospace's current contact is Ypsilanti, not the Ann Arbor address in
  old brochures. Historical project timelines are not described as current trials.
- Eclipse's current official contact is Mooresville; no separate Utah factory was
  inferred from older references or its telephone area code.
- FusionFlight's Axion is described as under development, not a certified product
  or an available commercial heavy-lift service.
- A broken OU fabrication checklist was removed from the proposed source set.
  Current official resource/contact pages support the narrower description.
- Mcity, OSU Skyway and Army source pages blocked the automated HTTP client but
  were readable in the normal browser and through the web research tool. A 403
  automated-client response is not classified as a broken source.
- Bolder Flight's state/location and a proposed NDSU prototyping-center URL were
  not established by current primary evidence, so neither was added.
- No aircraft-weight envelope, mitigation authority, unrestricted test access or
  site-specific certification was inferred from marketing text or a general waiver.

## Checks

The focused alignment pass covers every state in Current and 2.0 at desktop,
tablet and mobile widths. It checks Street defaults, preserved explicit Grey
choices, column alignment and visible text overflow. Broader map, loading,
comparison, export and profile checks are run after importing the new data into
a separate QA database. Catalog consistency checks cover stable identities,
geography, core/supporting roles and source presence; staff-preservation tests
exercise preview, repeat runs, baseline conflicts and protected source decisions.

Results: 136 backend checks, 40 frontend unit checks and 205 browser checks passed
(two inapplicable browser cases skipped). The browser pass includes both layouts
at 1440, 1024 and 390 pixels, plus all 31 new/expanded profiles. The initial catalog
import and preservation pass also passed its 49 focused checks. No alignment or
text-overflow defect was found in the checked controls and profile content.
