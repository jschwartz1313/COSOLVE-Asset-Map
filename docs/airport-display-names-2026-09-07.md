# Clear Airport Names - September 7, 2026

## Scope

All 64 FAA public-aviation records have descriptive public names. The September 6
profile pass already expanded labels such as Accomack County Airport, Norfolk
International Airport, and Roanoke-Blacksburg Regional Airport. This pass completes
Campbell Field Airport and Ingalls Field Airport. Bridgewater Air Park and
McLaughlin Seaplane Base retain their meaningful facility types.

Naming evidence for the two additions:

- [Virginia Tourism Corporation: Campbell Field Airport (9VG)](https://www.virginia.org/listing/campbell-field-airport/11334/amp/).
- [Bath County Airport Authority: Ingalls Field Airport](https://bathco.hosted.civiclive.com/government/boards___commissions/airport_authority).

These sources establish the labels, not current flight permissions or operational readiness.

## Existing Reviewed Records

The hosted Accomack County record still showed its raw catalog name. The prior
general correction command intentionally skips staff-managed records, which also
prevented a missing presentation label from being populated.

`fill_airport_display_names` now fills only blank display names for uniquely matched,
public, catalog-origin FAA airport records. It may fill a reviewed record's blank
label, but changes no other asset field, including its updated date. It preserves
custom names, aliases, stable names/slugs, staff descriptions, sources, coordinates,
publication state and review decisions. A history entry and internal review-log
note record the naming change. The marker prevents a later deliberate clearing
from being filled again on a subsequent deploy. Ambiguous or nonpublic records
are skipped.

The two existing Field labels use the usual baseline-guarded correction mechanism;
that mechanism's staff-edit protections have not been relaxed.

## Display Consistency

Admin asset lists, relation pickers, record headings and data-quality queues now use
the same public name as the map and directory. Searches continue to support the
canonical name and existing aliases. Admin CSVs intentionally retain the original
`name` plus `display_name` columns for lossless re-import; public map exports already
use the public label. No assets are added, merged, relocated, published or verified.
